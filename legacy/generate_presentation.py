import os
from google import genai
from google.genai import types
import argparse
from dotenv import load_dotenv

def call_gemini(prompt, model_name):
    """Calls the Gemini API with a specific prompt and model."""
    load_dotenv()
    client = genai.Client()
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API ({model_name}): {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Multi-Persona Presentation Generator")
    parser.add_argument('--input', required=True, help="Input text or path to file containing the content to analyze")
    
    args = parser.parse_args()
    
    content = args.input
    if os.path.exists(args.input):
        with open(args.input, 'r', encoding='utf-8') as f:
            content = f.read()
            
    # Step 1: Slider Buddy (Content)
    slider_buddy_prompt_path = 'templates/prompts/slider_buddy.txt'
    if not os.path.exists(slider_buddy_prompt_path):
        print(f"Error: Prompt file not found at {slider_buddy_prompt_path}")
        return
        
    with open(slider_buddy_prompt_path, 'r', encoding='utf-8') as f:
        slider_buddy_prompt = f.read()
        
    prompt_step1 = f"{slider_buddy_prompt}\n\nInput Content:\n{content}"
    
    print("Calling Slider Buddy (Gemini 3 Flash)...")
    slide_content = call_gemini(prompt_step1, 'gemini-3-flash-preview')
    
    if not slide_content:
        print("Failed to generate slide content with Gemini 3 Flash.")
        return
        
    print("\n--- Slider Buddy Output ---")
    print(slide_content)
    
    # Step 2: Designer (Style & Prompts)
    designer_prompt_path = 'templates/prompts/designer_prompt.txt'
    if not os.path.exists(designer_prompt_path):
        print(f"Error: Prompt file not found at {designer_prompt_path}")
        return
        
    with open(designer_prompt_path, 'r', encoding='utf-8') as f:
        designer_prompt = f.read()
        
    prompt_step2 = f"{designer_prompt}\n\nContent from Slider Buddy:\n{slide_content}"
    
    print("\nCalling Designer (Gemini 3 Flash)...")
    design_spec = call_gemini(prompt_step2, 'gemini-3-flash-preview')
    
    if not design_spec:
        print("Failed to generate design specification.")
        return
        
    print("\n--- Designer Output ---")
    print(design_spec)
    
    # Read config to get brand name
    import configparser
    import re
    config = configparser.ConfigParser()
    config.read('config.ini')
    brand_name = config.get('Crawler', 'search_terms')
    safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
    
    # Save outputs
    output_dir = os.path.join("outputs", safe_brand_name, "presentation")
    os.makedirs(output_dir, exist_ok=True)
    
    with open(os.path.join(output_dir, "slider_buddy_content.txt"), 'w', encoding='utf-8') as f:
        f.write(slide_content)
        
    with open(os.path.join(output_dir, "designer_spec.txt"), 'w', encoding='utf-8') as f:
        f.write(design_spec)
        
    print(f"\nSaved outputs to '{output_dir}'")

if __name__ == "__main__":
    main()
