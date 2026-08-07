import os
import json
import configparser
import re
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

def call_gemini(prompt, model_name):
    """Calls the Gemini API with retry logic for 503 errors."""
    load_dotenv()
    client = genai.Client()
    
    for attempt in range(3):
        try:
            print(f"Calling {model_name} (Attempt {attempt + 1})...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                print(f"Model overloaded (503). Waiting 5 seconds to retry...")
                time.sleep(5)
            else:
                print(f"Error calling Gemini API ({model_name}): {e}")
                return None
    print(f"Failed after 3 attempts with {model_name}.")
    return None

def call_gemini_json(prompt, model_name):
    """Calls Gemini and forces JSON output."""
    load_dotenv()
    client = genai.Client()
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        return response.text
    except Exception as e:
        print(f"Error getting JSON from Gemini: {e}")
        return None

def main():
    # Read config to get brand name
    load_dotenv()
    config = configparser.ConfigParser()
    config.read('config.ini')
    brand_name = config.get('Crawler', 'search_terms')
    safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
    
    report_file = os.path.join("outputs", safe_brand_name, f"{safe_brand_name}_strategic_report.html")
    
    if not os.path.exists(report_file):
        print(f"Error: Report file not found at {report_file}")
        return
        
    with open(report_file, 'r', encoding='utf-8') as f:
        report_content = f.read()
        
    # STEP 1: Designer Agent - Generates the Template/Design System
    designer_prompt = f"""
    Você é o Designer Agent. Com base no conteúdo do relatório abaixo sobre '{brand_name}', 
    gere um Design System completo para uma apresentação executiva.
    
    O output deve ser no formato YAML ou Markdown estruturado, contendo:
    - Paleta de Cores (Hex codes para surface, primary, secondary, background, etc.)
    - Tipografia (Fontes e tamanhos para h1, h2, body)
    - Descrição do Estilo Visual (ex: "Infográfico Executivo Tech", "Clean Culinário", etc.)
    
    Adapte o estilo ao tema do relatório! Não use o estilo tecnológico se o tema for culinária ou esportes.
    
    Relatório:
    {report_content[:5000]} # Truncating to avoid token limits in prompt if large
    """
    
    print("\n=== Passo 1: Designer Agent ===")
    design_template = call_gemini(designer_prompt, 'gemini-3.1-pro-preview')
    if not design_template:
        return
    print("Design System / Template gerado com sucesso.")
    
    # STEP 2: Slider Buddy - Generates content for 10 slides
    slider_buddy_prompt_path = 'templates/prompts/slider_buddy.txt'
    if not os.path.exists(slider_buddy_prompt_path):
        print(f"Error: Prompt file not found at {slider_buddy_prompt_path}")
        return
        
    with open(slider_buddy_prompt_path, 'r', encoding='utf-8') as f:
        slider_buddy_prompt_base = f.read()
        
    # Enforce 5 slides in prompt
    prompt_step2 = f"""
    {slider_buddy_prompt_base}
    
    Instrução Específica: Gere o conteúdo exatamente para 5 slides.
    
    Conteúdo do Relatório:
    {report_content[:5000]}
    """
    
    print("\n=== Passo 2: Slider Buddy ===")
    slides_content = call_gemini(prompt_step2, 'gemini-3.1-pro-preview')
    if not slides_content:
        return
    print("Conteúdo dos 10 slides gerado com sucesso.")
    
    # Parse slides content to separate them (using Gemini Flash for robust parsing)
    parse_prompt = f"""
    Leia o conteúdo gerado pelo Slider Buddy para os slides.
    Extraia o conteúdo de cada slide e retorne APENAS como um JSON list de objetos.
    Cada objeto deve ter: 'slide' (número), 'headline', 'body' (ou bullets).
    
    Conteúdo:
    {slides_content}
    """
    print("\n=== Extraindo Estrutura dos Slides ===")
    parsed_slides_json = call_gemini_json(parse_prompt, 'gemini-3-flash-preview')
    if not parsed_slides_json:
        print("Falha ao extrair estrutura dos slides.")
        return
        
    try:
        parsed_slides = json.loads(parsed_slides_json)
    except Exception as e:
        print(f"Erro ao fazer parse do JSON dos slides: {e}")
        return

    # STEP 3: Loop (Nano Banana Agent)
    print("\n=== Passo 3: Loop do Nano Banana Agent ===")
    output_dir = os.path.join("outputs", safe_brand_name, "presentation_structured")
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    # Save the template and content for reference
    with open(os.path.join(output_dir, "template.yaml"), 'w', encoding='utf-8') as f:
        f.write(design_template)
    with open(os.path.join(output_dir, "slides_content.txt"), 'w', encoding='utf-8') as f:
        f.write(slides_content)

    client = genai.Client()

    for item in parsed_slides:
        slide_num = item.get('slide')
        headline = item.get('headline')
        body = item.get('body')
        
        print(f"\nProcessando Slide {slide_num}...")
        
        # Ask Gemini to generate a prompt for this specific slide using the template
        prompt_generator = f"""
        Com base no seguinte Design System (Template) e no conteúdo do Slide {slide_num},
        gere um prompt detalhado e em INGLÊS para o gerador de imagens (Nano Banana).
        O prompt deve descrever o **slide inteiro como uma imagem completa**, incluindo o título e o conteúdo textual fornecido abaixo, seguindo o estilo do template.
        Instrua o gerador de imagens a renderizar os textos claramente em português.
        
        Design System (Template):
        {design_template}
        
        Conteúdo do Slide {slide_num}:
        Título: {headline}
        Conteúdo: {body}
        
        Retorne APENAS o texto do prompt.
        """
        
        image_prompt = call_gemini(prompt_generator, 'gemini-3-flash-preview')
        
        if not image_prompt:
            print(f"Falha ao gerar prompt para o Slide {slide_num}")
            continue
            
        print(f"Prompt gerado: {image_prompt[:50]}...")
        
        # Call Nano Banana to generate image
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-image-preview",
                contents=[image_prompt],
            )
            
            for part in response.parts:
                if part.inline_data is not None:
                    image = part.as_image()
                    output_path = os.path.join(images_dir, f"slide_{slide_num}_asset.png")
                    image.save(output_path)
                    print(f"Sucesso! Imagem salva em {output_path}")
                    break
        except Exception as e:
            print(f"Erro ao gerar imagem para o Slide {slide_num}: {e}")

    print(f"\nProcesso concluído! Arquivos salvos em '{output_dir}'")

if __name__ == "__main__":
    main()
