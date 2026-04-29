import os
import re
import configparser
import base64
from dotenv import load_dotenv

def main():
    load_dotenv()
    config = configparser.ConfigParser()
    config.read('config.ini')
    brand_name = config.get('Crawler', 'search_terms')
    safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
    
    img_dir = f"outputs/{safe_brand_name}/presentation_structured/images_full"
    output_html = f"outputs/{safe_brand_name}/{safe_brand_name}_deck.html"
    
    if not os.path.exists(img_dir):
        print(f"Directory not found: {img_dir}")
        return
        
    # Find and sort images
    img_files = [f for f in os.listdir(img_dir) if f.endswith('.png') and 'full' in f]
    img_files.sort(key=lambda x: int(re.search(r'slide_(\d+)', x).group(1)))
    
    if not img_files:
        print("No images found.")
        return
        
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
    
    for img_file in img_files:
        img_path = os.path.join(img_dir, img_file)
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
    print(f"SUCCESS: Saved Static HTML Deck to {output_html}")

if __name__ == "__main__":
    main()
