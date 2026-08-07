# run_full_acquisition.py
# This script orchestrates the video acquisition process.
# 1. Ensures the download destination directory exists.
# 2. Runs generate_metadata.py to fetch/update video lists.
# 3. Runs download_videos.py to download the videos.
# 4. Syncs the metadata file to the Google Drive folder.

import subprocess
import logging
import sys
import os
import shutil
from pathlib import Path

# --- CONFIGURATION (Decoupled from analysis_pipeline.py) ---
GOOGLE_DRIVE_ROOT_PATH = Path("~/DriveFileStream/Shared drives/[LCS BR] PB Futebol")
GOOGLE_DRIVE_PATH = GOOGLE_DRIVE_ROOT_PATH / "videos"
METADATA_FILENAME = "videos_metadata.csv"

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [ACQUISITION-MANAGER] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def ensure_drive_path_exists():
    """Checks if the configured Google Drive path exists, and creates it if possible/needed."""
    drive_path = GOOGLE_DRIVE_PATH.expanduser()
    
    if "Please/Update/This/Path" in str(drive_path):
        logging.error("CRITICAL: The GOOGLE_DRIVE_PATH in run_full_acquisition.py is not configured.")
        return False

    if not drive_path.exists():
        logging.warning(f"Destination directory '{drive_path}' does not exist.")
        try:
            logging.info(f"Attempting to create directory: {drive_path}")
            os.makedirs(drive_path, exist_ok=True)
            logging.info("Directory created successfully.")
        except Exception as e:
            logging.error(f"Failed to create directory '{drive_path}': {e}")
            return False
    else:
        logging.info(f"Destination directory verified: {drive_path}")
    
    return True

def run_script(script_name):
    """Runs a python script located in the same directory as this manager."""
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        logging.error(f"Script not found: {script_path}")
        return False

    logging.info(f"--- STARTING {script_name} ---")
    try:
        # Use the same python executable that is running this script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )
        logging.info(f"--- FINISHED {script_name} (Exit Code: {result.returncode}) ---")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"--- FAILED {script_name} (Exit Code: {e.returncode}) ---")
        return False
    except Exception as e:
        logging.error(f"--- ERROR executing {script_name}: {e} ---")
        return False

def sync_metadata_to_drive():
    """Copies the local metadata CSV to the Google Drive folder."""
    local_metadata = Path(__file__).parent / METADATA_FILENAME
    drive_metadata = GOOGLE_DRIVE_PATH.expanduser() / METADATA_FILENAME
    
    if not local_metadata.exists():
        logging.warning(f"Local metadata file '{local_metadata}' not found. Skipping sync.")
        return

    logging.info(f"Syncing metadata file to Google Drive: {drive_metadata}...")
    try:
        shutil.copy2(local_metadata, drive_metadata)
        logging.info("Metadata file successfully synced to Drive.")
    except Exception as e:
        logging.error(f"Failed to sync metadata file to Drive: {e}")

if __name__ == "__main__":
    logging.info("Starting Full Video Acquisition Pipeline...")
    
    # Step 0: Update Cookies
    if not run_script("update_cookies.py"):
        logging.error("Cookie update failed. Proceeding anyway, but downloads might fail.")

    # Step 1: Verify Environment
    if not ensure_drive_path_exists():
        logging.error("Aborting pipeline due to directory issues.")
        sys.exit(1)

    # Step 2: Generate Metadata (Find new videos)
    if not run_script("generate_metadata.py"):
        logging.error("Metadata generation failed. Aborting pipeline.")
        sys.exit(1)

    # Step 3: Download Videos
    if not run_script("download_videos.py"):
        logging.error("Video download process encountered errors.")
        sys.exit(1)

    # Step 4: Sync Metadata
    sync_metadata_to_drive()

    logging.info("="*80)
    logging.info("FULL ACQUISITION PIPELINE COMPLETED SUCCESSFULLY.")
    logging.info("="*80)
