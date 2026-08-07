# youtube_utils.py
# This file contains utility functions for interacting with YouTube,
# specifically for fetching video information using yt-dlp.

import subprocess
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict

# --- CONFIGURATION FOR YT-DLP ---
CHANNEL_URL = "https://www.youtube.com/@CazeTV/streams"
KEYWORDS_IN_TITLE = [
    "PAULISTÃO",
    "PAULISTÃO FEMININO",
    "BRASILEIRÃO",
    "BRASILEIRÃO 2026",
    "COPINHA"
]
EXCLUDE_KEYWORDS_IN_TITLE = [
    "COPINHA FEMININA",
    "GERAL CAZÉTV",
    "LANÇAMENTO",
    "PAPO 10",
    "2025",
    "2024",
    "2023",
    "2022",
    "2021",
    "2020"
]
MAX_VIDEOS_TO_CHECK = 2000
COOKIE_FILE_PATH = Path('cookies.txt')

# --- LOGGING SETUP ---
# Although this is a utility file, setting up a basic logger is good practice
# in case it's ever run standalone or needs debugging.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [YT-UTILS] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_and_filter_videos(channel_url: str, keywords: List[str], max_videos: int) -> List[Dict[str, str]]:
    """
    Fetches video metadata using yt-dlp and then filters the results inside Python
    to select only completed live streams that match the keywords.
    """
    logging.info(f"Fetching metadata for the last {max_videos} videos from {channel_url}...")
    
    python_executable_path = Path(sys.executable)
    yt_dlp_executable_path = python_executable_path.parent / 'yt-dlp'

    if not yt_dlp_executable_path.exists():
        logging.error(f"FATAL: Could not find 'yt-dlp' at: {yt_dlp_executable_path}")
        return []

    command = [
        str(yt_dlp_executable_path),
        '--no-check-certificate',
        '--flat-playlist',
        '--dump-json',
        '--playlist-end', str(max_videos),
        '--extractor-args', 'youtube:player_client=android,tv',
        channel_url
    ]

    if COOKIE_FILE_PATH and COOKIE_FILE_PATH.exists():
        command.extend(['--cookies', str(COOKIE_FILE_PATH)])

    try:
        result = subprocess.check_output(command, text=True, encoding='utf-8')
        video_lines = result.strip().split('\n')
        all_videos = [json.loads(line) for line in video_lines if line]

        logging.info("Filtering results in Python...")
        filtered_videos = []
        for video in all_videos:
            title = video.get('title', 'No Title')
            live_status = video.get('live_status')

            if live_status == 'was_live':
                if "JOGO COMPLETO" in title.upper() and \
                   any(keyword.upper() in title.upper() for keyword in keywords) and \
                   not any(exclude_keyword.upper() in title.upper() for exclude_keyword in EXCLUDE_KEYWORDS_IN_TITLE):
                    logging.info(f"MATCH FOUND: '{title}'")
                    filtered_videos.append({'title': title, 'url': video.get('url')})
                else:
                    logging.info(f"Skipping (keyword not in title): '{title}'")
            else:
                logging.info(f"Skipping (status is '{live_status}'): '{title}'")
        
        logging.info(f"Found {len(filtered_videos)} completed live streams matching the criteria after filtering.")
        return filtered_videos

    except subprocess.CalledProcessError as e:
        logging.error(f"The 'yt-dlp' command failed. The program may be blocked or corrupted.")
        logging.error(f"Error details: {e}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching videos: {e}")
        return []
