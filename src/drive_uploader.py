import os
from googleapiclient.discovery import build
import google.auth
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

def get_drive_service():
    """Gets the Google Drive service using ADC."""
    credentials, project = google.auth.default(
        scopes=[
            'https://www.googleapis.com/auth/cloud-platform',
            'https://www.googleapis.com/auth/drive'
        ]
    )
    if not credentials.valid:
        credentials.refresh(Request())
    return build('drive', 'v3', credentials=credentials)

def upload_file_to_drive(file_path, folder_id, mime_type, resource_key=None):
    """Uploads a file to a specific folder in Google Drive."""
    try:
        service = get_drive_service()
        
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(file_path, mimetype=mime_type)
        
        print(f"Uploading '{file_path}' to Google Drive folder '{folder_id}'...")
        
        kwargs = {
            'body': file_metadata,
            'media_body': media,
            'fields': 'id',
            'supportsAllDrives': True
        }
        
        request = service.files().create(**kwargs)
        
        if resource_key:
            request.headers['X-Goog-Drive-Resource-Keys'] = f"{folder_id}/{resource_key}"
            
        file = request.execute()
        
        print(f"SUCCESS: File uploaded to Drive. ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        print(f"Error uploading file to Drive: {e}")
        return None

def verify_file_in_drive(file_name, folder_id, resource_key=None):
    """Verifies if a file exists in a specific Google Drive folder."""
    try:
        service = get_drive_service()
        
        query = f"'{folder_id}' in parents and name = '{file_name}' and trashed = false"
        
        kwargs = {
            'q': query,
            'fields': 'files(id, name)',
            'supportsAllDrives': True,
            'includeItemsFromAllDrives': True
        }
        
        request = service.files().list(**kwargs)
        
        if resource_key:
            request.headers['X-Goog-Drive-Resource-Keys'] = f"{folder_id}/{resource_key}"
            
        results = request.execute()
        items = results.get('files', [])
        
        if items:
            print(f"SUCCESS: Verification passed. File '{file_name}' found in Drive.")
            return True
        else:
            print(f"WARNING: Verification failed. File '{file_name}' NOT found in Drive.")
            return False
    except Exception as e:
        print(f"Error verifying file in Drive: {e}")
        return False

def create_folder_in_drive(folder_name, parent_folder_id, resource_key=None):
    """Creates a new folder in a specific Google Drive folder."""
    try:
        service = get_drive_service()
        
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        
        kwargs = {
            'body': file_metadata,
            'fields': 'id',
            'supportsAllDrives': True
        }
        
        request = service.files().create(**kwargs)
        
        if resource_key:
            request.headers['X-Goog-Drive-Resource-Keys'] = f"{parent_folder_id}/{resource_key}"
            
        file = request.execute()
        
        print(f"SUCCESS: Folder '{folder_name}' created in Drive. ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        print(f"Error creating folder in Drive: {e}")
        return None

def list_folders_in_drive(parent_folder_id, resource_key=None):
    """Lists subfolders in a specific Google Drive folder."""
    try:
        service = get_drive_service()
        
        # We restore the mimeType restriction as we want only folders
        query = f"'{parent_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        print(f"Listing folders with query: {query}", flush=True)
        
        kwargs = {
            'q': query,
            'fields': 'files(id, name)',
            'supportsAllDrives': True,
            'includeItemsFromAllDrives': True
        }
        
        request = service.files().list(**kwargs)
        
        if resource_key:
            request.headers['X-Goog-Drive-Resource-Keys'] = f"{parent_folder_id}/{resource_key}"
            print(f"Using resource key header: {parent_folder_id}/{resource_key}", flush=True)
            
        results = request.execute()
        files = results.get('files', [])
        print(f"Found {len(files)} folders in Drive.", flush=True)
        return files
    except Exception as e:
        print(f"Error listing folders in Drive: {e}", flush=True)
        return []

def download_file_from_drive(file_id, resource_key=None):
    """Downloads a file from Google Drive and returns its bytes."""
    try:
        service = get_drive_service()
        
        request = service.files().get_media(fileId=file_id)
        
        if resource_key:
            request.headers['X-Goog-Drive-Resource-Keys'] = f"{file_id}/{resource_key}"
            
        import io
        from googleapiclient.http import MediaIoBaseDownload
        
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            
        return fh.getvalue()
    except Exception as e:
        print(f"Error downloading file from Drive: {e}")
        return None

def find_pdf_in_folder(folder_id, resource_key=None):
    """Finds the first PDF file in a specific Google Drive folder."""
    try:
        service = get_drive_service()
        
        query = f"'{folder_id}' in parents and mimeType = 'application/pdf' and trashed = false"
        
        kwargs = {
            'q': query,
            'fields': 'files(id, name)',
            'supportsAllDrives': True,
            'includeItemsFromAllDrives': True
        }
        
        request = service.files().list(**kwargs)
        
        if resource_key:
            request.headers['X-Goog-Drive-Resource-Keys'] = f"{folder_id}/{resource_key}"
            
        results = request.execute()
        files = results.get('files', [])
        if files:
            return files[0]
        return None
    except Exception as e:
        print(f"Error finding PDF in Drive: {e}")
        return None

def find_file_by_name_in_folder(folder_id, name_substring, resource_key=None):
    """Finds a file containing a specific substring in its name within a specific Google Drive folder."""
    try:
        service = get_drive_service()
        
        query = f"'{folder_id}' in parents and name contains '{name_substring}' and trashed = false"
        
        kwargs = {
            'q': query,
            'fields': 'files(id, name)',
            'supportsAllDrives': True,
            'includeItemsFromAllDrives': True
        }
        
        request = service.files().list(**kwargs)
        
        if resource_key:
            request.headers['X-Goog-Drive-Resource-Keys'] = f"{folder_id}/{resource_key}"
            
        results = request.execute()
        files = results.get('files', [])
        if files:
            return files[0]
        return None
    except Exception as e:
        print(f"Error finding file with name '{name_substring}' in Drive: {e}")
        return None

def upload_run_outputs_to_drive(config_path="config.ini"):
    """
    Uploads all generated output files (HTML/Markdown reports, CSV datasets, PDF slides)
    from a run directory securely to Google Drive.
    """
    import configparser
    import re
    from datetime import datetime

    print("\n--- Enviando Arquivos para o Google Drive ---", flush=True)
    try:
        config = configparser.ConfigParser(interpolation=None)
        config.read(config_path)
        
        brand_name = config.get('Crawler', 'search_terms', fallback='Analysis')
        safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
        run_id = config.get('General', 'run_id', fallback=safe_brand_name)
        
        folder_id = os.getenv('DRIVE_FOLDER_ID', config.get('Drive', 'folder_id', fallback=None))
        resource_key = os.getenv('DRIVE_RESOURCE_KEY', config.get('Drive', 'resource_key', fallback=None))
        
        if not folder_id:
            print("Warning: Drive folder_id not set in configuration. Skipping upload.", flush=True)
            return

        run_dir = os.path.join("outputs", run_id)
        if not os.path.exists(run_dir):
            print(f"Warning: Output directory '{run_dir}' does not exist. Skipping upload.", flush=True)
            return

        # Create subfolder in Drive for this run
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_name = f"{safe_brand_name}_{timestamp}"
        print(f"Criando pasta '{folder_name}' no Google Drive...", flush=True)
        
        subfolder_id = create_folder_in_drive(folder_name, folder_id, resource_key=resource_key)
        target_folder_id = subfolder_id if subfolder_id else folder_id

        # List all files in run output directory
        files_to_upload = []
        for root, _, files in os.walk(run_dir):
            for file in files:
                # Exclude internal cache/json files
                if file.endswith(('.html', '.md', '.csv', '.pdf')) and not file.startswith('.'):
                    files_to_upload.append(os.path.join(root, file))

        for file_path in files_to_upload:
            file_name = os.path.basename(file_path)
            mime_type = 'text/plain'
            if file_name.endswith('.html'):
                mime_type = 'text/html'
            elif file_name.endswith('.md'):
                mime_type = 'text/markdown'
            elif file_name.endswith('.csv'):
                mime_type = 'text/csv'
            elif file_name.endswith('.pdf'):
                mime_type = 'application/pdf'

            print(f"Uploading {file_name} to Drive...", flush=True)
            upload_file_to_drive(file_path, target_folder_id, mime_type, resource_key=resource_key)

        print("\n--- Validando Uploads no Google Drive ---", flush=True)
        for file_path in files_to_upload:
            verify_file_in_drive(os.path.basename(file_path), target_folder_id, resource_key=resource_key)

    except Exception as e:
        print(f"Error in Drive upload step: {e}", flush=True)
        return None

