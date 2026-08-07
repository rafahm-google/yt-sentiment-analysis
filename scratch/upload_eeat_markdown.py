import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from drive_uploader import upload_file_to_drive, verify_file_in_drive, create_folder_in_drive

# Configuration for Drive
folder_id = "1MsXuPKrR6MM6o02NXt-yPE-Hwj7caiCT"
resource_key = "0-X26e-T0YzerdpL_8vA-uRg"

# Target file paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
folder_name = f"eeat_reports_markdown_{timestamp}"

print("Creating folder in Drive...")
subfolder_id = create_folder_in_drive(folder_name, folder_id, resource_key=resource_key)
target_folder_id = subfolder_id if subfolder_id else folder_id

# 1. Luggage Space Report
report_path_1 = os.path.join(project_root, "outputs", "espaco_malas_aviao_eeat", "espaço_de_malas_no_avião_strategic_report.md")
videos_csv_path_1 = os.path.join(project_root, "outputs", "espaco_malas_aviao_eeat", "espaço_de_malas_no_avião_discovered_videos.csv")
comments_csv_path_1 = os.path.join(project_root, "outputs", "espaco_malas_aviao_eeat", "espaço_de_malas_no_avião_raw_comments.csv")

print(f"Uploading Report 1: {report_path_1}")
upload_file_to_drive(report_path_1, target_folder_id, 'text/markdown', resource_key=resource_key)
if os.path.exists(videos_csv_path_1):
    upload_file_to_drive(videos_csv_path_1, target_folder_id, 'text/csv', resource_key=resource_key)
if os.path.exists(comments_csv_path_1):
    upload_file_to_drive(comments_csv_path_1, target_folder_id, 'text/csv', resource_key=resource_key)

# 2. VIP Lounges Report
report_path_2 = os.path.join(project_root, "outputs", "melhores_salas_vip_eeat", "melhores_salas_vip_strategic_report.md")
videos_csv_path_2 = os.path.join(project_root, "outputs", "melhores_salas_vip_eeat", "melhores_salas_vip_discovered_videos.csv")
comments_csv_path_2 = os.path.join(project_root, "outputs", "melhores_salas_vip_eeat", "melhores_salas_vip_raw_comments.csv")

print(f"Uploading Report 2: {report_path_2}")
upload_file_to_drive(report_path_2, target_folder_id, 'text/markdown', resource_key=resource_key)
if os.path.exists(videos_csv_path_2):
    upload_file_to_drive(videos_csv_path_2, target_folder_id, 'text/csv', resource_key=resource_key)
if os.path.exists(comments_csv_path_2):
    upload_file_to_drive(comments_csv_path_2, target_folder_id, 'text/csv', resource_key=resource_key)

print("Verifying uploads...")
verify_file_in_drive(os.path.basename(report_path_1), target_folder_id, resource_key=resource_key)
verify_file_in_drive(os.path.basename(report_path_2), target_folder_id, resource_key=resource_key)
