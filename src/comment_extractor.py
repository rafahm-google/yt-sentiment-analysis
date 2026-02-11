# ==============================================================================
# YOUTUBE COMMENT EXTRACTOR
# ==============================================================================
# This script extracts comments from YouTube videos listed in a CSV file.
# It takes a 'discovered_videos.csv' (output from youtube_brand_crawler.py)
# as input, fetches comments for each video, and saves them to a new CSV.
# ==============================================================================

import os
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from tqdm import tqdm
import argparse
import re
import configparser

class YouTubeCommentExtractor:
    """
    A class to extract comments from YouTube videos.
    """
    def __init__(self, config_path, env_path=None):
        """Initializes the extractor by loading configuration and API keys."""
        print("Initializing YouTube Comment Extractor...")
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if env_path is None:
            env_path = os.path.join(self.project_root, '.env')
            
        self._load_environment_variables(env_path)
        self._load_configuration(config_path)
        self.youtube_api = build("youtube", "v3", developerKey=self.youtube_api_key)
        print("SUCCESS: YouTube API service built.")

    def _load_environment_variables(self, env_path):
        """Loads API keys from a .env file."""
        load_dotenv(dotenv_path=env_path)
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.youtube_api_key:
            raise ValueError("YouTube API key must be set in the .env file.")
        print("SUCCESS: Environment variables loaded.")

    def _load_configuration(self, config_path):
        """Loads settings from the config file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
        
        config = configparser.ConfigParser()
        config.read(config_path)
        
        brand_name = config.get('Crawler', 'search_terms')
        safe_brand_name = re.sub(r'\W+', '', brand_name.replace(' ', '_'))
        
        self.input_csv_path = os.path.join(self.project_root, 'outputs', safe_brand_name, f"{safe_brand_name}_discovered_videos.csv")
        self.output_csv_path = os.path.join(self.project_root, 'outputs', safe_brand_name, f"{safe_brand_name}_raw_comments.csv")
        self.max_comments_per_video = config.getint('Crawler', 'max_results', fallback=100) # Reuse max_results for comments

    def extract_comments(self):
        """
        Extracts comments from videos listed in the input CSV and saves them to an output CSV.
        """
        if not os.path.exists(self.input_csv_path):
            print(f"Error: Input CSV file not found at '{self.input_csv_path}'.")
            return

        try:
            videos_df = pd.read_csv(self.input_csv_path)
            if 'video_id' not in videos_df.columns:
                print("Error: Input CSV must contain a 'video_id' column.")
                return
        except Exception as e:
            print(f"Error reading input CSV file: {e}")
            return

        all_comments = []
        print(f"Found {len(videos_df)} videos to process for comments.")

        for index, row in tqdm(videos_df.iterrows(), total=videos_df.shape[0], desc="Extracting Comments"):
            video_id = row['video_id']
            video_title = row.get('title', 'Unknown Title')
            video_url = row.get('url', f"https://www.youtube.com/watch?v={video_id}")
            
            comments_for_video = self._fetch_comments_for_video(
                video_id, video_title, video_url, self.max_comments_per_video
            )
            all_comments.extend(comments_for_video)

        if not all_comments:
            print("No comments extracted. Exiting.")
            return

        comments_df = pd.DataFrame(all_comments)
        output_dir = os.path.dirname(self.output_csv_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: '{output_dir}'")
            
        comments_df.to_csv(self.output_csv_path, index=False)
        print(f"\nSUCCESS: Extracted {len(comments_df)} comments to '{self.output_csv_path}'.")

    def _fetch_comments_for_video(self, video_id, video_title, video_url, max_comments):
        """
        Fetches comments for a single video using the YouTube Data API.
        """
        comments = []
        next_page_token = None
        count = 0

        while True:
            try:
                response = self.youtube_api.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    textFormat="plainText",
                    maxResults=100, # Max results per API call
                    pageToken=next_page_token
                ).execute()

                for item in response['items']:
                    comment = item['snippet']['topLevelComment']['snippet']
                    comments.append({
                        'id_video': video_id,
                        'titulo_video': video_title,
                        'url_video': video_url,
                        'texto_comentario': comment['textDisplay'],
                        'autor': comment['authorDisplayName'],
                        'publicado_em': comment['publishedAt'],
                    })
                    count += 1
                    if count >= max_comments:
                        break

                next_page_token = response.get('nextPageToken')
                if not next_page_token or count >= max_comments:
                    break

            except HttpError as e:
                if e.resp.status == 403 and "commentsDisabled" in str(e.content):
                    print(f"\nWarning: Comments are disabled for video {video_id} - {video_title}.")
                else:
                    print(f"\nError fetching comments for video {video_id} - {video_title}: {e}")
                break
            except Exception as e:
                print(f"\nAn unexpected error occurred while fetching comments for {video_id}: {e}")
                break

        return comments

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Comment Extractor")
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini"),
        help="Path to the configuration file."
    )
    args = parser.parse_args()

    try:
        extractor = YouTubeCommentExtractor(config_path=args.config)
        extractor.extract_comments()
    except (ValueError, FileNotFoundError) as e:
        print(f"\nCRITICAL ERROR: {e}")