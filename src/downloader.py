# ==============================================================================
# VIDEO DOWNLOADER
# ==============================================================================
# This script reads a CSV file containing YouTube video URLs and extracts the
# video (video + audio) from each entry, saving it as an MP4 file.
#
# It is designed to download lower resolution videos (e.g., 480p) to balance
# quality for AI analysis (visuals + audio) with file size and bandwidth.
# ==============================================================================

import os
import pandas as pd
import subprocess
from tqdm import tqdm
import argparse
import configparser
import re
import sys

class VideoDownloader:
    def __init__(self, config_path):
        """Initializes the downloader by loading configuration."""
        print("Initializing Video Downloader...")
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._load_configuration(config_path)

    def _load_configuration(self, config_path):
        """Loads settings from the config file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
        
        config = configparser.ConfigParser()
        config.read(config_path)
        
        brand_name = config.get('Crawler', 'search_terms')
        safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
        
        # Use project_root for paths
        self.csv_path = os.path.join(self.project_root, 'outputs', safe_brand_name, f"{safe_brand_name}_discovered_videos.csv")
        # Default to 'video' folder
        video_folder_name = config.get('VideoDownloader', 'video_folder_name', fallback='video')
        self.output_dir = os.path.join(self.project_root, 'outputs', safe_brand_name, video_folder_name)

    def download_videos(self):
        """
        Downloads videos from YouTube videos listed in the configured CSV file.
        """
        if not os.path.exists(self.csv_path):
            print(f"Error: The file '{self.csv_path}' was not found.")
            return

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            print(f"Created output directory: '{self.output_dir}'")

        try:
            df = pd.read_csv(self.csv_path)
            if 'url' not in df.columns:
                print("Error: The CSV file must contain a 'url' column.")
                return
        except Exception as e:
            print(f"Error reading the CSV file: {e}")
            return

        print(f"Found {len(df)} videos to process.")

        # Determine the path to the yt-dlp executable in the current environment
        yt_dlp_path = os.path.join(sys.prefix, 'bin', 'yt-dlp')
        if not os.path.exists(yt_dlp_path):
             # Fallback to system yt-dlp if not found in venv (though it should be there)
             yt_dlp_path = 'yt-dlp'
             # print(f"Warning: yt-dlp not found in {sys.prefix}/bin. Using system default.")

        for index, row in tqdm(df.iterrows(), total=df.shape[0], desc="Downloading Videos"):
            video_url = row['url']
            # video_id might not be present if CSV structure changed, fallback safely
            video_id = row.get('video_id', f'video_{index}')
            # Sanitize video_id just in case
            if isinstance(video_id, str):
                video_id = re.sub(r'[\\/*?:"<>|]', "", video_id)
            
            output_filename = os.path.join(self.output_dir, f"{video_id}.mp4")

            if os.path.exists(output_filename):
                # print(f"Skipping '{output_filename}' as it already exists.")
                continue

            try:
                # Use project_root to find cookies.txt
                cookies_path = os.path.join(self.project_root, 'cookies.txt')
                
                # Command to download video <= 480p to save space but keep visual context
                command = [
                    yt_dlp_path,
                    '-f', 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]', 
                    '--merge-output-format', 'mp4',
                    '--output', output_filename,
                    video_url,
                    '--extractor-args', 'youtube:player_client=default'
                ]
                
                if os.path.exists(cookies_path):
                    command.extend(['--cookies', cookies_path])
                
                # Run quietly
                subprocess.run(command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"\nWarning: Could not download video from {video_url}. Error: {e.stderr.strip()}")
            except Exception as e:
                print(f"\nAn unexpected error occurred for {video_url}: {e}")

        print("\n\nSUCCESS: Video downloading complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Video Downloader")
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini"),
        help="Path to the configuration file."
    )
    args = parser.parse_args()
    
    try:
        downloader = VideoDownloader(config_path=args.config)
        downloader.download_videos()
    except (ValueError, FileNotFoundError) as e:
        print(f"\nCRITICAL ERROR: {e}")
