# ==============================================================================
# YOUTUBE BRAND CRAWLER
# ==============================================================================
# This script intelligently searches YouTube for relevant user-generated
# content about a specific brand or product, filtering out ads and official
# content to provide a list of the most viewed or engaging videos.
#
# How it works:
# 1. Reads a search query and filtering criteria from config.ini.
# 2. Performs multiple targeted searches using modifiers (e.g., "review").
# 3. Fetches detailed video statistics for each search result.
# 4. Filters out videos that don't meet the criteria (e.g., low views, ads).
# 5. Calculates an engagement score for each video.
# 6. Sorts the results by the desired metric (views, engagement, relevance).
# 7. Saves the final, curated list to a CSV file in a brand-specific folder.
# ==============================================================================

import os
import configparser
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import re
from tqdm import tqdm

class YouTubeBrandCrawler:
    """
    A class to crawl YouTube for brand-related user-generated content.
    """
    def __init__(self, config_path=None, env_path=None):
        """Initializes the crawler by loading configuration and API keys."""
        print("Initializing YouTube Brand Crawler...")
        
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if config_path is None:
            config_path = os.path.join(self.project_root, 'config.ini')
        if env_path is None:
            env_path = os.path.join(self.project_root, '.env')
            
        self._load_environment_variables(env_path)
        self._load_configuration(config_path)
        self.youtube_api = build("youtube", "v3", developerKey=self.youtube_api_key)

    def _load_environment_variables(self, env_path):
        """Loads API keys from a .env file."""
        load_dotenv(dotenv_path=env_path)
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.youtube_api_key:
            raise ValueError("YouTube API key must be set in the .env file.")
        print("SUCCESS: Environment variables loaded.")

    def _load_configuration(self, config_path):
        """Loads settings from the [Crawler] section of config.ini."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
        
        config = configparser.ConfigParser()
        config.read(config_path)
        
        self.search_terms = config.get('Crawler', 'search_terms')
        self.search_modifiers = [mod.strip() for mod in config.get('Crawler', 'search_modifiers').split(',')]
        self.exclude_keywords = [key.strip().lower() for key in config.get('Crawler', 'exclude_keywords').split(',')]
        self.min_view_count = config.getint('Crawler', 'min_view_count')
        self.sort_by = config.get('Crawler', 'sort_by')
        self.max_results = config.getint('Crawler', 'max_results')

        # --- Brand-Specific Output Path (BUG FIX) ---
        safe_brand_name = re.sub(r'\W+', '', self.search_terms.replace(' ', '_'))
        self.output_dir = os.path.join('outputs', safe_brand_name)
        self.output_path = os.path.join(self.output_dir, f"{safe_brand_name}_discovered_videos.csv")
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"SUCCESS: Configuration loaded for brand '{self.search_terms}'.")
        print(f"Output will be saved to '{self.output_path}'")

    def run_crawler(self):
        """Executes the full crawling and filtering pipeline."""
        print("\n▶️  Starting video search on YouTube...")
        
        # --- API Efficiency Improvement ---
        # Combine all search modifiers into a single query for efficiency.
        # Example: "Brand" (review | analysis | unboxing)
        combined_modifiers = " | ".join(self.search_modifiers)
        query = f'"{self.search_terms}" ({combined_modifiers})'
        
        print(f"Executing combined search query: '{query}'")
        
        video_ids = set()
        next_page_token = None
        
        # Fetch multiple pages of results to get a wider selection
        for _ in range(3): # Fetch up to 3 pages of results
            try:
                search_response = self.youtube_api.search().list(
                    q=query,
                    part="id",
                    type="video",
                    maxResults=50,
                    regionCode="BR",
                    pageToken=next_page_token
                ).execute()
                
                for item in search_response.get("items", []):
                    video_ids.add(item["id"]["videoId"])
                
                next_page_token = search_response.get('nextPageToken')
                if not next_page_token:
                    break # Exit if there are no more pages
            except HttpError as e:
                print(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
                break

        if not video_ids:
            print("No videos found matching the search criteria. Exiting.")
            return

        print(f"\nFound {len(video_ids)} unique videos. Fetching details...")
        video_details = self._get_video_details(list(video_ids))
        
        print("\nFiltering and processing video data...")
        df = self._process_and_filter_videos(video_details)

        if df.empty:
            print("No videos remained after filtering. Exiting.")
            return

        print(f"\nSorting results by '{self.sort_by}'...")
        df = self._sort_results(df)

        final_df = df.head(self.max_results)
        final_df.to_csv(self.output_path, index=False)
        
        print(f"\n\nSUCCESS: Crawling complete! Saved {len(final_df)} videos to '{self.output_path}'.")

    def _get_video_details(self, video_ids):
        """Fetches detailed statistics for a list of video IDs in batches."""
        video_details = []
        # Process in batches of 50 (API limit)
        for i in tqdm(range(0, len(video_ids), 50), desc="Fetching Video Details"):
            batch_ids = video_ids[i:i+50]
            try:
                details_response = self.youtube_api.videos().list(
                    part="snippet,statistics",
                    id=",".join(batch_ids)
                ).execute()
                video_details.extend(details_response.get("items", []))
            except HttpError as e:
                print(f"An HTTP error {e.resp.status} occurred while fetching details:\n{e.content}")
        return video_details

    def _process_and_filter_videos(self, video_details):
        """Processes the raw API response, filters it, and returns a DataFrame."""
        processed_videos = []
        for video in video_details:
            title = video["snippet"]["title"]
            
            # 1. Filter by excluded keywords
            if any(keyword in title.lower() for keyword in self.exclude_keywords):
                continue

            stats = video.get("statistics", {})
            view_count = int(stats.get("viewCount", 0))
            
            # 2. Filter by minimum view count
            if view_count < self.min_view_count:
                continue

            like_count = int(stats.get("likeCount", 0))
            comment_count = int(stats.get("commentCount", 0))
            
            processed_videos.append({
                "video_id": video["id"],
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video['id']}",
                "channel": video["snippet"]["channelTitle"],
                "views": view_count,
                "likes": like_count,
                "comments": comment_count,
                "engagement": like_count + comment_count,
                "description": video["snippet"]["description"]
            })
        
        return pd.DataFrame(processed_videos)

    def _sort_results(self, df):
        """Sorts the DataFrame based on the configuration."""
        if self.sort_by == 'viewCount':
            return df.sort_values(by="views", ascending=False).reset_index(drop=True)
        elif self.sort_by == 'engagement':
            return df.sort_values(by="engagement", ascending=False).reset_index(drop=True)
        else: # Default to relevance (which is the default API return order, so no-op)
            return df

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Brand Crawler")
    parser.add_argument(
        "--config",
        default="config.ini",
        help="Path to the configuration file."
    )
    args = parser.parse_args()

    try:
        crawler = YouTubeBrandCrawler(config_path=args.config)
        crawler.run_crawler()
    except (ValueError, FileNotFoundError) as e:
        print(f"\nCRITICAL ERROR: {e}")
