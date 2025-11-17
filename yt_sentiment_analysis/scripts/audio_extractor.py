# ==============================================================================
# AUDIO EXTRACTOR
# ==============================================================================
# This script reads a CSV file containing YouTube video URLs and extracts the
# audio from each video, saving it as an MP3 file.
#
# How it works:
# 1. Reads configuration from a .ini file to determine input/output paths.
# 2. Reads the input CSV file.
# 3. Iterates through the 'url' column of the CSV.
# 4. For each URL, it uses yt-dlp to download the audio-only format.
# 5. Saves the audio as an MP3 file in the specified output directory.
# ==============================================================================

import os
import pandas as pd
import subprocess
from tqdm import tqdm
import argparse
import configparser
import re

class AudioExtractor:
    def __init__(self, config_path):
        """Initializes the extractor by loading configuration."""
        print("Initializing Audio Extractor...")
        self._load_configuration(config_path)

    def _load_configuration(self, config_path):
        """Loads settings from the config file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
        
        config = configparser.ConfigParser()
        config.read(config_path)
        
        brand_name = config.get('Crawler', 'search_terms')
        safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
        
        self.csv_path = os.path.join('outputs', safe_brand_name, f"{safe_brand_name}_discovered_videos.csv")
        audio_folder_name = config.get('AudioExtractor', 'audio_folder_name', fallback='audio')
        self.output_dir = os.path.join('outputs', safe_brand_name, audio_folder_name)

    def extract_audio(self):
        """
        Extracts audio from YouTube videos listed in the configured CSV file.
        """
        if not os.path.exists(self.csv_path):
            print(f"Error: The file '{self.csv_path}' was not found.")
            return

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
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

        for index, row in tqdm(df.iterrows(), total=df.shape[0], desc="Extracting Audio"):
            video_url = row['url']
            video_id = row.get('video_id', f'video_{index}')
            output_filename = os.path.join(self.output_dir, f"{video_id}.mp3")

            if os.path.exists(output_filename):
                print(f"Skipping '{output_filename}' as it already exists.")
                continue

            try:
                command = [
                    'yt-dlp',
                    '-x',  # Extract audio
                    '--audio-format', 'mp3',
                    '--output', output_filename,
                    video_url
                ]
                subprocess.run(command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"\nError downloading audio from {video_url}:")
                print(f"Stderr: {e.stderr}")
            except Exception as e:
                print(f"\nAn unexpected error occurred for {video_url}: {e}")

        print("\n\nSUCCESS: Audio extraction complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Audio Extractor")
    parser.add_argument(
        "--config",
        default="config_gemini.ini",
        help="Path to the configuration file."
    )
    args = parser.parse_args()
    
    try:
        extractor = AudioExtractor(config_path=args.config)
        extractor.extract_audio()
    except (ValueError, FileNotFoundError) as e:
        print(f"\nCRITICAL ERROR: {e}")