import os
from google import genai
from google.genai import types
import argparse
from dotenv import load_dotenv

def generate_slide(content_input, prompt_template_path):
    """Calls Gemini 3.1 Pro with the Slider Buddy prompt to generate slide content."""
    load_dotenv()
    client = genai.Client()
    
    if not os.path.exists(prompt_template_path):
        raise FileNotFoundError(f"Prompt template not found at {prompt_template_path}")
        
    with open(prompt_template_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
        
    # Combine prompt and input
    prompt = f"{prompt_template}\n\nInput Content:\n{content_input}"
    
    print("Calling Slider Buddy (Gemini 3.1 Pro)...")
    try:
        response = client.models.generate_content(
            model='gemini-3.1-pro-preview',
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Slider Buddy - Presentation Content Generator")
    parser.add_argument('--input', required=True, help="Input text or path to file containing the content to analyze")
    parser.add_argument('--prompt', default='templates/prompts/slider_buddy.txt', help="Path to prompt template")
    
    args = parser.parse_args()
    
    content = args.input
    if os.path.exists(args.input):
        with open(args.input, 'r', encoding='utf-8') as f:
            content = f.read()
            
    slide_content = generate_slide(content, args.prompt)
    
    if slide_content:
        print("\nGenerated Slide Content:")
        print(slide_content)
        
        # Save to file for next steps
        output_path = "outputs/generated_slide_content.txt"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(slide_content)
        print(f"\nSaved generated content to '{output_path}'")

if __name__ == "__main__":
    main()
