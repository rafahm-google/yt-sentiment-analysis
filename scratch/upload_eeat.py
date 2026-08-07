import os
import sys

# Add src to python path so we can import drive_uploader
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from drive_uploader import upload_file_to_drive, verify_file_in_drive, create_folder_in_drive

# Configuration for Drive
folder_id = "1MsXuPKrR6MM6o02NXt-yPE-Hwj7caiCT"
resource_key = "0-X26e-T0YzerdpL_8vA-uRg"

# Target file paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
report_path = os.path.join(project_root, "outputs", "espaco_malas_aviao_eeat", "espaço_de_malas_no_avião_strategic_report.html")
videos_csv_path = os.path.join(project_root, "outputs", "espaco_malas_aviao_eeat", "espaço_de_malas_no_avião_discovered_videos.csv")
comments_csv_path = os.path.join(project_root, "outputs", "espaco_malas_aviao_eeat", "espaço_de_malas_no_avião_raw_comments.csv")

if not os.path.exists(report_path):
    print(f"Error: Report not found at {report_path}")
    sys.exit(1)

print("Creating folder in Drive...")
from datetime import datetime
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
folder_name = f"espaco_malas_aviao_eeat_{timestamp}"
subfolder_id = create_folder_in_drive(folder_name, folder_id, resource_key=resource_key)

target_folder_id = subfolder_id if subfolder_id else folder_id

print(f"Uploading HTML report and CSVs to folder: {folder_name} ({target_folder_id})")
upload_file_to_drive(report_path, target_folder_id, 'text/html', resource_key=resource_key)

if os.path.exists(videos_csv_path):
    upload_file_to_drive(videos_csv_path, target_folder_id, 'text/csv', resource_key=resource_key)
if os.path.exists(comments_csv_path):
    upload_file_to_drive(comments_csv_path, target_folder_id, 'text/csv', resource_key=resource_key)

print("Verifying uploads...")
verify_file_in_drive(os.path.basename(report_path), target_folder_id, resource_key=resource_key)
