# generate_metadata.py
# This script is intended to be run on a machine with access to YouTube (e.g., in Brazil).
# It identifies the target videos, fetches their metadata using yt-dlp, and saves it
# to a CSV file. This file, along with the downloaded videos, can then be moved to
# another environment (like a cloudtop) for offline analysis.
# This script is resumable; it will skip videos already present in the metadata file.

import csv
import logging
import time
from typing import List, Dict, Set, Tuple, Optional
from pathlib import Path
import re
import urllib.parse
import subprocess
import json
import datetime
import sys

# Import functions from the existing scripts
from youtube_utils import get_and_filter_videos, CHANNEL_URL, KEYWORDS_IN_TITLE, MAX_VIDEOS_TO_CHECK

# --- CONFIGURATION ---
METADATA_CSV_PATH = Path("videos_metadata.csv")
COOKIE_FILE_PATH = Path('cookies.txt')

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [METADATA-GEN] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_video_metadata(video_url: str) -> Optional[Tuple[str, str, int, datetime.datetime]]:
    logging.info(f"Fetching metadata for {video_url}...")
    
    python_executable_path = Path(sys.executable)
    yt_dlp_executable_path = python_executable_path.parent / 'yt-dlp'
    
    try:
        command = [str(yt_dlp_executable_path), '--no-check-certificate', '-j', '--no-playlist', '--extractor-args', 'youtube:player_client=android,tv', video_url]
        if COOKIE_FILE_PATH and COOKIE_FILE_PATH.exists():
            command.extend(['--cookies', str(COOKIE_FILE_PATH)])
        else:
            command.extend(['--cookies-from-browser', 'chrome'])
        json_output = subprocess.check_output(command, text=True, encoding='utf-8')
        video_info = json.loads(json_output)
        video_id = video_info['id']
        video_title = video_info.get('title', f"video_{video_id}")
        duration = video_info.get('duration', 0)
        if ts := video_info.get('release_timestamp'): dt = datetime.datetime.fromtimestamp(ts)
        elif ds := video_info.get('upload_date'): dt = datetime.datetime.strptime(ds, '%Y%m%d')
        else: dt = datetime.datetime.now()
        logging.info(f"Video ID: '{video_id}' | Title: '{video_title}' | Duration: {duration}s")
        return video_id, video_title, int(duration), dt
    except Exception as e:
        logging.error(f"Failed to get metadata for {video_url}: {e}")
        return None

def read_existing_metadata_ids(path: Path) -> Set[str]:
    """Reads an existing metadata CSV and returns a set of video_ids."""
    if not path.exists():
        return set()
    
    existing_ids = set()
    try:
        with open(path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'video_id' in row:
                    existing_ids.add(row['video_id'])
        logging.info(f"Found {len(existing_ids)} existing videos in '{path.name}'.")
        return existing_ids
    except Exception as e:
        logging.error(f"Could not read existing metadata file: {e}")
        return set()

def get_id_from_url(url: str) -> str:
    """Extracts the YouTube video ID from a URL."""
    if not url:
        return None
    parsed_url = urllib.parse.urlparse(url)
    if 'v' in urllib.parse.parse_qs(parsed_url.query):
        return urllib.parse.parse_qs(parsed_url.query)['v'][0]
    return None

def generate_metadata_file(videos: List[Dict[str, str]], output_path: Path, existing_ids: Set[str]):
    """
    Fetches detailed metadata for a list of video URLs and appends it to a CSV file.
    Skips videos that are already in the `existing_ids` set.
    """
    if not videos:
        logging.warning("Video list is empty. No metadata file will be generated.")
        return

    header = ['video_id', 'title', 'url', 'upload_datetime', 'duration_seconds', 'local_path']
    new_rows_written = 0
    
    # Check if the file is new or empty to write the header
    write_header = not output_path.exists() or output_path.stat().st_size == 0

    logging.info(f"Checking {len(videos)} videos against existing metadata...")
    
    with open(output_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)

        for i, video_info in enumerate(videos, 1):
            url = video_info['url']
            title = video_info['title']
            
            video_id = get_id_from_url(url)
            if not video_id:
                logging.warning(f"Could not extract video ID from URL '{url}'. Skipping.")
                continue

            if video_id in existing_ids:
                logging.info(f"Metadata for '{title}' ({video_id}) already exists. Skipping.")
                continue

            logging.info(f"Fetching new metadata for video {i}/{len(videos)}: {title}")

            metadata = get_video_metadata(url)
            
            if metadata:
                # get_video_metadata returns: video_id, video_title, duration, dt
                _, video_title, duration, dt = metadata
                
                local_path = f"video_{video_id}.mp4"

                writer.writerow([
                    video_id,
                    video_title,
                    url,
                    dt.isoformat(),
                    duration,
                    local_path
                ])
                new_rows_written += 1
            else:
                logging.error(f"Could not fetch metadata for '{title}' ({url}). It will be skipped.")

            # Add a delay to avoid being rate-limited or having cookies invalidated
            if i < len(videos):
                logging.info("Waiting for 15 seconds before the next request...")
                time.sleep(15)

    logging.info(f"Wrote metadata for {new_rows_written} new videos.")
    logging.info(f"Metadata file updated: '{output_path}'")


if __name__ == "__main__":
    logging.info("Starting metadata generation process...")
    
    # 1. Read existing metadata to avoid re-processing
    existing_video_ids = read_existing_metadata_ids(METADATA_CSV_PATH)
    
    # 2. Find all relevant videos from the channel
    videos_to_process = get_and_filter_videos(CHANNEL_URL, KEYWORDS_IN_TITLE, MAX_VIDEOS_TO_CHECK)

    # 3. Generate metadata for new videos only
    if videos_to_process:
        generate_metadata_file(videos_to_process, METADATA_CSV_PATH, existing_video_ids)
    else:
        logging.info("No videos found matching the criteria. Exiting.")

    logging.info("="*80)
    logging.info("METADATA GENERATION COMPLETE.")
    logging.info(f"The next step is to upload the '{METADATA_CSV_PATH.name}' file and all 'video_*.mp4' files to your cloud environment.")
    logging.info("="*80)
