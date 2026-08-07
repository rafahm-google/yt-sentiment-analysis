# download_videos.py
# This script reads a metadata CSV file and downloads the videos listed in it.
# -- MODIFIED TO DOWNLOAD DIRECTLY TO THE MOUNTED GOOGLE DRIVE FOLDER --

import subprocess
import logging
import time
import random
from typing import List, Dict
import sys
from pathlib import Path
import csv

# --- CONFIGURATION ---
METADATA_CSV_PATH = Path("videos_metadata.csv")
# DOWNLOAD_DELAY_MINUTES removed in favor of randomized sleep

# Copied from analysis_pipeline.py to make this script independent
GOOGLE_DRIVE_ROOT_PATH = Path("/home/rafahm/DriveFileStream/Shared drives/[LCS BR] PB Futebol")
GOOGLE_DRIVE_PATH = GOOGLE_DRIVE_ROOT_PATH / "videos"
STREAM_QUALITY = "480p"
COOKIE_FILE_PATH = Path('cookies.txt')

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [DOWNLOADER] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def read_metadata_csv(path: Path) -> List[Dict]:
    """Reads the video metadata from the CSV file."""
    if not path.exists():
        logging.error(f"Metadata file not found: '{path}'. Please run generate_metadata.py first.")
        return []

    videos = []
    try:
        with open(path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                videos.append(row)
        logging.info(f"Found {len(videos)} videos in metadata file '{path}'.")
        return videos
    except Exception as e:
        logging.error(f"Failed to read or parse metadata CSV: {e}")
        return []

def check_video_in_mounted_drive(video_id: str) -> bool:
    """Checks if a video file exists in the specified mounted Google Drive folder."""
    filename = f"video_{video_id}.mp4"
    
    # Expand the user's home directory and check if the path exists
    try:
        drive_path = GOOGLE_DRIVE_PATH.expanduser()
        if "Please/Update/This/Path" in str(drive_path):
            logging.warning("The GOOGLE_DRIVE_PATH configuration has not been updated. Skipping check.")
            return False
            
        video_file_path = drive_path / filename
        if video_file_path.exists():
            logging.info(f"Found '{filename}' in mounted Google Drive at '{drive_path}'.")
            return True
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred while checking the mounted Google Drive path: {e}")
        return False

def download_video(video_url: str, video_id: str) -> str:
    """
    Downloads a single video directly to the mounted Google Drive, checking for existence first.
    Returns a status: "SKIPPED", "DOWNLOADED", or "FAILED".
    """
    # 1. Check mounted Google Drive first
    if check_video_in_mounted_drive(video_id):
        logging.info(f"Video 'video_{video_id}.mp4' already exists in Google Drive. Skipping.")
        return "SKIPPED"

    # 2. Define the download path to be the mounted drive
    drive_path = GOOGLE_DRIVE_PATH.expanduser()
    if "Please/Update/This/Path" in str(drive_path):
        logging.error("The GOOGLE_DRIVE_PATH configuration must be updated before downloading.")
        return "FAILED"
    
    video_file_path = drive_path / f"video_{video_id}.mp4"

    logging.info(f"Downloading video directly to Google Drive folder: '{video_file_path}'...")
    
    python_executable_path = Path(sys.executable)
    yt_dlp_executable_path = python_executable_path.parent / 'yt-dlp'

    quality = STREAM_QUALITY.replace("p", "")
    format_string = f'bestvideo[height<={quality}]+bestaudio/best'
    command_base = [
        str(yt_dlp_executable_path), '--no-check-certificate', '--retries', 'infinite',
        '--quiet', '-f', format_string, '--merge-output-format', 'mp4',
        '--extractor-args', 'youtube:player_client=android,tv',
        '-o', str(video_file_path), video_url
    ]

    # Try with cookies.txt first
    if COOKIE_FILE_PATH and COOKIE_FILE_PATH.exists():
        logging.info("Attempting download with cookies.txt...")
        command = command_base + ['--cookies', str(COOKIE_FILE_PATH)]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
            logging.info(f"Successfully downloaded {video_url} with cookies.txt")
            return "DOWNLOADED"
        except subprocess.CalledProcessError as e:
            stderr_output = e.stderr.strip()
            if "Sign in to confirm" in stderr_output:
                logging.warning("Download with cookies.txt failed. Falling back to browser cookies.")
            else:
                logging.error(f"Download failed with unexpected error: {stderr_output}")
                return "FAILED"

    # Fallback to browser cookies
    logging.info("Using browser cookies as fallback or default for download...")
    command = command_base + ['--cookies-from-browser', 'chrome']
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        logging.info(f"Successfully downloaded {video_url} with browser cookies")
        return "DOWNLOADED"
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip()
        logging.error(f"Download failed with browser cookies: {error_output}")
        return "FAILED"
    except Exception as e:
        logging.error(f"An unexpected error occurred during download: {e}")
        return "FAILED"

if __name__ == "__main__":
    videos_to_process = read_metadata_csv(METADATA_CSV_PATH)

    if not videos_to_process:
        logging.info("No videos found in metadata file. Exiting.")
    else:
        total_videos = len(videos_to_process)
        logging.info(f"--- Found {total_videos} videos to download from '{METADATA_CSV_PATH.name}' ---")

        for i, video_info in enumerate(videos_to_process, 1):
            url = video_info.get('url')
            video_id = video_info.get('video_id')
            title = video_info.get('title', 'No Title')
            
            if not url or not video_id:
                logging.warning(f"Skipping row {i+1} in CSV due to missing 'url' or 'video_id'.")
                continue

            logging.info("="*80)
            logging.info(f"Processing video {i}/{total_videos}: {title}")
            
            download_status = download_video(url, video_id)

            if download_status == "DOWNLOADED":
                if i < total_videos:
                    # Randomized sleep between 2 and 5 minutes (120 to 300 seconds)
                    sleep_time = random.randint(120, 300)
                    logging.info(f"Waiting for {sleep_time} seconds (approx {sleep_time/60:.1f} mins) before starting the next video...")
                    time.sleep(sleep_time)
            elif download_status == "FAILED":
                logging.error(f"Failed to download video: {title}. Check logs for details.")

        logging.info("="*80)
        logging.info("ALL VIDEO DOWNLOADS ATTEMPTED.")
        logging.info("="*80)
