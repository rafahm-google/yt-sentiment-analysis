import os
from PIL import Image
import re
import configparser
from dotenv import load_dotenv

def main():
    load_dotenv()
    config = configparser.ConfigParser()
    config.read('config.ini')
    brand_name = config.get('Crawler', 'search_terms')
    safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
    
    img_dir = f"outputs/{safe_brand_name}/presentation_structured/images_full"
    output_pdf = f"outputs/{safe_brand_name}/{safe_brand_name}_presentation.pdf"
    
    if not os.path.exists(img_dir):
        print(f"Directory not found: {img_dir}")
        return
        
    # Find and sort images
    img_files = [f for f in os.listdir(img_dir) if f.endswith('.png') and 'full' in f]
    # Sort numerically by slide number
    img_files.sort(key=lambda x: int(re.search(r'slide_(\d+)', x).group(1)))
    
    if not img_files:
        print("No images found to combine.")
        return
        
    print(f"Combining {len(img_files)} images into PDF...")
    
    images = [Image.open(os.path.join(img_dir, f)) for f in img_files]
    
    # Convert RGBA to RGB if needed (PDF doesn't support transparency)
    rgb_images = []
    for img in images:
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            rgb_images.append(background)
        else:
            rgb_images.append(img.convert('RGB'))
            
    # Save as PDF
    rgb_images[0].save(output_pdf, save_all=True, append_images=rgb_images[1:])
    print(f"SUCCESS: Saved PDF to {output_pdf}")

if __name__ == "__main__":
    main()
