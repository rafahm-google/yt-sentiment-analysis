import os
import re
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

def extract_prompts_with_gemini(file_path):
    """Uses Gemini to extract prompts from the designer spec file as JSON."""
    load_dotenv()
    client = genai.Client()
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return []
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    prompt = f"""
    Read the following design specification for a presentation.
    Extract all the prompts intended for 'Nano Banana' or image generation.
    Return the result ONLY as a JSON list of objects, where each object has 'slide' and 'prompt' keys.
    Example:
    [
      {{"slide": 3, "prompt": "A prompt here..."}},
      {{"slide": 6, "prompt": "Another prompt..."}}
    ]
    
    Design Specification:
    {content}
    """
    
    print("Extracting prompts using Gemini...")
    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    
    try:
        return json.loads(response.text)
    except Exception as e:
        print(f"Error parsing JSON from Gemini: {e}")
        print(response.text)
        return []

def generate_image(prompt, output_path):
    """Calls Gemini Image API (Nano Banana) to generate an image."""
    load_dotenv()
    client = genai.Client()
    
    print(f"Generating image for prompt: '{prompt[:50]}...'")
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=[prompt],
        )
        
        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(output_path)
                print(f"SUCCESS: Saved image to {output_path}")
                return True
        print("ERROR: No image data returned by the API.")
        return False
    except Exception as e:
        print(f"Error generating image: {e}")
        return False

def main():
    # Read config to get brand name
    import configparser
    import re
    config = configparser.ConfigParser()
    config.read('config.ini')
    brand_name = config.get('Crawler', 'search_terms')
    safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
    
    spec_file = os.path.join("outputs", safe_brand_name, "presentation", "designer_spec.txt")
    output_dir = os.path.join("outputs", safe_brand_name, "presentation", "images")
    os.makedirs(output_dir, exist_ok=True)
    
    prompts = extract_prompts_with_gemini(spec_file)
    
    if not prompts:
        print("No prompts found to generate.")
        return
        
    print(f"Found {len(prompts)} prompts to generate.")
    
    for item in prompts:
        slide_num = item.get('slide')
        prompt_text = item.get('prompt')
        
        if not prompt_text:
            continue
            
        output_path = os.path.join(output_dir, f"slide_{slide_num}_asset.png")
        generate_image(prompt_text, output_path)

if __name__ == "__main__":
    main()
