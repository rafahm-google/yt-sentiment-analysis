import os
import json
import configparser
import re
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image

def call_gemini(prompt, model_name, config=None):
    """Calls the Gemini API with retry logic for 503 errors."""
    load_dotenv()
    client = genai.Client()
    
    for attempt in range(3):
        try:
            print(f"Calling {model_name} (Attempt {attempt + 1})...", flush=True)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                print(f"Model overloaded (503). Waiting 5 seconds to retry...", flush=True)
                time.sleep(5)
            else:
                print(f"Error calling Gemini API ({model_name}): {e}", flush=True)
                return None
    print(f"Failed after 3 attempts with {model_name}.", flush=True)
    return None

def generate_image(prompt, output_path):
    """Calls Gemini Image API (Nano Banana) to generate an image."""
    load_dotenv()
    client = genai.Client()
    
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=[prompt],
        )
        
        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(output_path)
                return True
        return False
    except Exception as e:
        print(f"Error generating image: {e}", flush=True)
        return False

def run_slide_generation(config_path="config.ini"):
    """Full workflow to generate slides content as JSON, images and HTML viewer."""
    load_dotenv()
    
    config = configparser.ConfigParser()
    config.read(config_path)
    brand_name = config.get('Crawler', 'search_terms')
    safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
    additional_context = config.get('Analysis', 'additional_context', fallback='')
    output_language = config.get('Analysis', 'output_language', fallback='Portuguese')
    
    report_file = os.path.join("outputs", safe_brand_name, f"{safe_brand_name}_strategic_report.html")
    output_dir = os.path.join("outputs", safe_brand_name, "presentation_structured")
    images_dir = os.path.join(output_dir, "images_full")
    os.makedirs(images_dir, exist_ok=True)
    
    if not os.path.exists(report_file):
        print(f"Error: Report file not found at {report_file}", flush=True)
        return
        
    with open(report_file, 'r', encoding='utf-8') as f:
        report_content = f.read()
        
    # STEP 1: Designer Agent - Generates the Template/Design System
    designer_prompt = f"""
    Você é o Designer Agent. Com base no conteúdo do relatório abaixo sobre '{brand_name}', 
    gere um Design System completo para uma apresentação executiva.
    
    O output deve ser no formato YAML ou Markdown estruturado, contendo:
    - Paleta de Cores (Hex codes)
    - Tipografia (Fontes e tamanhos)
    - Descrição do Estilo Visual
    
    Adapte o estilo ao tema do relatório!
    
    Relatório:
    {report_content[:5000]}
    """
    
    print("\n--- Gerando Template de Design ---", flush=True)
    design_template = call_gemini(designer_prompt, 'gemini-3-flash-preview') # Using Flash to avoid 503s
    if not design_template:
        return
    print("SUCCESS: Template de Design gerado.", flush=True)
        
    # STEP 2: Slider Buddy - Generates content for EXACTLY 8 slides in JSON
    slider_buddy_prompt_path = 'templates/prompts/slider_buddy.txt'
    with open(slider_buddy_prompt_path, 'r', encoding='utf-8') as f:
        slider_buddy_prompt_base = f.read()
        
    prompt_step2 = f"""
    {slider_buddy_prompt_base}
    
    Instrução Específica: Gere o conteúdo para EXATAMENTE 8 slides.
    Slide 1 deve ser sempre a Capa (Cover).
    
    Retorne o resultado APENAS como um JSON list de objetos. Não inclua markdown ou explicações fora do JSON.
    Cada objeto deve ter a seguinte estrutura:
    {{
      "slide": 1,
      "headline": "Título do slide",
      "subtitle": "Subtítulo (opcional)",
      "bullets": ["Tópico 1", "Tópico 2", ...],
      "visual_description": "Descrição detalhada do visual e layout para este slide"
    }}
    
    Conteúdo do Relatório:
    {report_content[:5000]}
    """
    
    if additional_context:
        prompt_step2 += f"\n\nInformações/Diretrizes Adicionais do Usuário (PRIORIDADE MÁXIMA):\n{additional_context}"
        prompt_step2 += "\nIMPORTANTE: Priorize as diretrizes adicionais do usuário acima sobre as regras do prompt original se houver conflito."
        
    prompt_step2 += f"\n\nIDIOMA DE SAÍDA: Toda a apresentação e textos devem ser gerados no idioma: {output_language}."
    
    print("\n--- Gerando Conteúdo dos Slides (JSON) ---", flush=True)
    # Using JSON mode in config
    json_config = types.GenerateContentConfig(
        response_mime_type="application/json",
    )
    
    slides_json = call_gemini(prompt_step2, 'gemini-3-flash-preview', config=json_config)
    if not slides_json:
        return
        
    try:
        slides_list = json.loads(slides_json)
        print("SUCCESS: Conteúdo dos slides gerado em JSON.", flush=True)
    except Exception as e:
        print(f"Error parsing JSON from Gemini: {e}", flush=True)
        print(slides_json)
        return
        
    # Save intermediate files
    with open(os.path.join(output_dir, "template.yaml"), 'w', encoding='utf-8') as f:
        f.write(design_template)
    with open(os.path.join(output_dir, "slides_content.json"), 'w', encoding='utf-8') as f:
        f.write(slides_json)
        
    # STEP 3: Loop to generate images (Parallel)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    print(f"\n--- Gerando Imagens para {len(slides_list)} slides (Paralelo) ---", flush=True)
    
    def process_slide(item):
        slide_num = item.get('slide')
        headline = item.get('headline')
        bullets = item.get('bullets', [])
        visual = item.get('visual_description')
        
        print(f"Processando Slide {slide_num}...", flush=True)
        
        # Construct prompt combining content and style
        bullets_text = "\n".join([f"- {b}" for b in bullets])
        
        prompt_generator = f"""
        Com base no seguinte Design System (Template) e no conteúdo deste slide,
        gere um prompt detalhado e em INGLÊS para o gerador de imagens (Nano Banana).
        O prompt deve descrever o slide inteiro como uma imagem completa, incluindo o título, subtítulo e bullets, seguindo o estilo do template.
        Instrua o gerador de imagens a renderizar os textos claramente no idioma: {output_language}.
        
        Design System (Template):
        {design_template}
        
        Conteúdo do Slide:
        Título: {headline}
        Texto: {bullets_text}
        Descrição Visual: {visual}
        
        Retorne APENAS o texto do prompt.
        """
        
        image_prompt = call_gemini(prompt_generator, 'gemini-3-flash-preview')
        if not image_prompt:
            print(f"Falha ao gerar prompt para o Slide {slide_num}", flush=True)
            return
            
        print(f"Prompt gerado para Slide {slide_num}: {image_prompt[:50]}...", flush=True)
        
        output_path = os.path.join(images_dir, f"slide_{slide_num}_full.png")
        generate_image(image_prompt, output_path)
        
    # Use 3 workers to avoid overwhelming image rate limits
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_slide, item) for item in slides_list]
        for future in as_completed(futures):
            future.result()
        
    # STEP 4: Create HTML Viewer
    print("\n--- Criando Visualizador HTML ---", flush=True)
    output_html = os.path.join("outputs", safe_brand_name, f"{safe_brand_name}_deck.html")
    
    img_files = [f for f in os.listdir(images_dir) if f.endswith('.png')]
    img_files.sort(key=lambda x: int(re.search(r'slide_(\d+)', x).group(1)) if re.search(r'slide_(\d+)', x) else 0)
    
    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Deck - {safe_brand_name}</title>
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #08132a;
            color: #d9e2ff;
            margin: 0;
            padding: 20px;
            text-align: center;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        .slide {{
            margin-bottom: 40px;
            border: 1px solid #44474d;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        h1 {{
            color: #b9c7e4;
            margin-bottom: 30px;
            font-size: 2rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Apresentação de Slides (Rolagem Vertical)</h1>
    """
    
    import base64
    for img_file in img_files:
        img_path = os.path.join(images_dir, img_file)
        with open(img_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        html_content += f"""
        <div class="slide">
            <img src="data:image/png;base64,{encoded_string}" alt="Slide">
        </div>
        """
        
    html_content += """
    </div>
</body>
</html>
    """
    
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"SUCCESS: Saved HTML Deck to {output_html}", flush=True)
    
    # STEP 5: Create PDF
    print("\n--- Criando PDF da Apresentação ---", flush=True)
    output_pdf = os.path.join("outputs", safe_brand_name, f"{safe_brand_name}_presentation.pdf")
    
    images = [Image.open(os.path.join(images_dir, f)) for f in img_files]
    rgb_images = []
    for img in images:
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            rgb_images.append(background)
        else:
            rgb_images.append(img.convert('RGB'))
            
    if rgb_images:
        rgb_images[0].save(output_pdf, save_all=True, append_images=rgb_images[1:])
        print(f"SUCCESS: Saved PDF to {output_pdf}", flush=True)

if __name__ == "__main__":
    run_slide_generation()
