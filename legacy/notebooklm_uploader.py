import os
import subprocess
import requests
import json
import argparse
from dotenv import load_dotenv
import google.auth
import google.auth.transport.requests

def get_access_token():
    """Gets the access token using google-auth (works locally with ADC and in Cloud Run)."""
    try:
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    except Exception as e:
        print(f"Error getting access token: {e}")
        return None

def create_notebook(project_number, location, title, token):
    """Creates a new notebook in NotebookLM Enterprise."""
    endpoint = f"https://{location}-discoveryengine.googleapis.com/v1alpha/projects/{project_number}/locations/{location}/notebooks"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "title": title
    }
    
    print(f"Creating notebook '{title}'...")
    response = requests.post(endpoint, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        resp_json = response.json()
        print(f"SUCCESS: Notebook created. ID: {resp_json['notebookId']}")
        return resp_json['notebookId']
    else:
        print(f"ERROR: Failed to create notebook. Status: {response.status_code}")
        print(response.text)
        return None

def add_text_source(project_number, location, notebook_id, source_title, content_text, token):
    """Adds a raw text source to the notebook."""
    endpoint = f"https://{location}-discoveryengine.googleapis.com/v1alpha/projects/{project_number}/locations/{location}/notebooks/{notebook_id}/sources:batchCreate"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "userContents": [
            {
                "textContent": {
                    "sourceName": source_title,
                    "content": content_text
                }
            }
        ]
    }
    
    print(f"Adding text source '{source_title}' to notebook...")
    response = requests.post(endpoint, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        print(f"SUCCESS: Added text source '{source_title}'.")
        return True
    else:
        print(f"ERROR: Failed to add text source. Status: {response.status_code}")
        print(response.text)
        return False

def upload_file_source(project_number, location, notebook_id, file_path, display_name, token):
    """Uploads a file as a source to the notebook."""
    endpoint = f"https://{location}-discoveryengine.googleapis.com/upload/v1alpha/projects/{project_number}/locations/{location}/notebooks/{notebook_id}/sources:uploadFile"
    
    # Determine content type based on extension
    content_type = "text/plain"
    if file_path.endswith('.pdf'):
        content_type = "application/pdf"
    elif file_path.endswith('.md'):
        content_type = "text/markdown"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Goog-Upload-File-Name": display_name,
        "X-Goog-Upload-Protocol": "raw",
        "Content-Type": content_type
    }
    
    print(f"Uploading file '{file_path}' as source '{display_name}'...")
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()
            
        response = requests.post(endpoint, headers=headers, data=file_data)
        
        if response.status_code == 200:
            print(f"SUCCESS: Uploaded file source '{display_name}'.")
            return True
        else:
            print(f"ERROR: Failed to upload file. Status: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Error reading or uploading file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="NotebookLM Enterprise Uploader")
    parser.add_argument('--brand', required=True, help="Brand name for the notebook title")
    parser.add_argument('--file', help="Path to a specific file to upload as source")
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    project_number = os.getenv("GCP_PROJECT_NUMBER")
    location = os.getenv("GCP_LOCATION", "global")
    
    if not project_number:
        print("CRITICAL ERROR: GCP_PROJECT_NUMBER not set in .env")
        return
        
    token = get_access_token()
    if not token:
        print("CRITICAL ERROR: Could not get access token. If running locally, run 'gcloud auth application-default login' first.")
        return
        
    # 1. Create Notebook
    notebook_title = f"YouTube Analysis - {args.brand}"
    notebook_id = create_notebook(project_number, location, notebook_title, token)
    
    if not notebook_id:
        return
        
    # 2. Upload sources if requested
    if args.file and os.path.exists(args.file):
        upload_file_source(project_number, location, notebook_id, args.file, os.path.basename(args.file), token)
        
    print(f"\nFull process complete! You can access your notebook at:")
    print(f"https://notebooklm.cloud.google.com/{location}/notebook/{notebook_id}?project={project_number}")

if __name__ == "__main__":
    main()
