import re

file_path = "/usr/local/google/home/rafahm/Documents/yt-sentiment-analysis/src/generate_slides_final.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate from "# STEP 5: Create PDF" to the end of run_slide_generation
# In generate_slides_final.py, the function ends at:
#             else:
#                 print("Warning: Drive folder_id not set in config.ini. Skipping upload.", flush=True)
#         except Exception as e:
#             print(f"Error in Drive upload step: {e}", flush=True)

# Let's target the exact block of text starting with # STEP 5: Create PDF
pattern = r"    # STEP 5: Create PDF \(Bypassed\).*?            print\(f\"Error in Drive upload step: \{e\}\", flush=True\)"

replacement = """    # STEP 5: Create PDF (Bypassed by user request)
    # print("\\n--- Criando PDF da Apresentação ---", flush=True)
    # output_pdf = os.path.join("outputs", run_id, f"{safe_brand_name}_presentation.pdf")
    
    # images = [Image.open(os.path.join(images_dir, f)) for f in img_files]
    # rgb_images = []
    # for img in images:
    #     if img.mode == 'RGBA':
    #         background = Image.new('RGB', img.size, (255, 255, 255))
    #         background.paste(img, mask=img.split()[3])
    #         rgb_images.append(background)
    #     else:
    #         rgb_images.append(img.convert('RGB'))
            
    # if rgb_images:
    #     rgb_images[0].save(output_pdf, save_all=True, append_images=rgb_images[1:])
    #     print(f"SUCCESS: Saved PDF to {output_pdf}", flush=True)
        
    # STEP 6: Upload to Google Drive (Un-nested and running unconditionally for HTML files)
    print("\\n--- Enviando Arquivos para o Google Drive ---", flush=True)
    try:
        from datetime import datetime
        folder_id = os.getenv('DRIVE_FOLDER_ID', config.get('Drive', 'folder_id', fallback=None))
        resource_key = os.getenv('DRIVE_RESOURCE_KEY', config.get('Drive', 'resource_key', fallback=None))
        if folder_id:
            from drive_uploader import upload_file_to_drive, verify_file_in_drive, create_folder_in_drive
            
            # Create a subfolder for this report
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            folder_name = f"{safe_brand_name}_{timestamp}"
            print(f"Criando pasta '{folder_name}' no Google Drive...", flush=True)
            
            subfolder_id = create_folder_in_drive(folder_name, folder_id, resource_key=resource_key)
            
            target_folder_id = subfolder_id if subfolder_id else folder_id
            
            # Upload HTML files
            upload_file_to_drive(output_html, target_folder_id, 'text/html', resource_key=resource_key)
            
            if os.path.exists(report_file):
                upload_file_to_drive(report_file, target_folder_id, 'text/html', resource_key=resource_key)
            
            # Upload CSV files if they exist
            videos_csv_path = os.path.join("outputs", run_id, f"{safe_brand_name}_discovered_videos.csv")
            comments_csv_path = os.path.join("outputs", run_id, f"{safe_brand_name}_raw_comments.csv")
            
            if os.path.exists(videos_csv_path):
                upload_file_to_drive(videos_csv_path, target_folder_id, 'text/csv', resource_key=resource_key)
            if os.path.exists(comments_csv_path):
                upload_file_to_drive(comments_csv_path, target_folder_id, 'text/csv', resource_key=resource_key)
            
            # Verification
            print("\\n--- Validando Uploads no Google Drive ---", flush=True)
            verify_file_in_drive(os.path.basename(output_html), target_folder_id, resource_key=resource_key)
            if os.path.exists(report_file):
                verify_file_in_drive(os.path.basename(report_file), target_folder_id, resource_key=resource_key)
        else:
            print("Warning: Drive folder_id not set in config.ini. Skipping upload.", flush=True)
    except Exception as e:
        print(f"Error in Drive upload step: {e}", flush=True)"""

modified_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)
if count > 0:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(modified_content)
    print(f"SUCCESS: Replaced {count} occurrences.")
else:
    print("FAILED: No occurrences replaced.")
