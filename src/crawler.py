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
from datetime import datetime
import requests

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
        self.search_modifiers = [mod.strip() for mod in config.get('Crawler', 'search_modifiers').split(',') if mod.strip()]
        self.exclude_keywords = [key.strip().lower() for key in config.get('Crawler', 'exclude_keywords').split(',') if key.strip()]
        
        # New filters
        self.video_type = config.get('Crawler', 'video_type', fallback='both').lower()
        self.published_after = config.get('Crawler', 'published_after', fallback='').strip()
        self.region_code = config.get('Crawler', 'region_code', fallback='US').strip().upper()
        
        # Format published_after to RFC 3339 if present
        if self.published_after:
            try:
                # Try parsing full ISO format first
                dt = datetime.fromisoformat(self.published_after.replace('Z', '+00:00'))
                self.published_after = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                try:
                    # Try YYYY-MM-DD format and append time
                    dt = datetime.strptime(self.published_after, "%Y-%m-%d")
                    self.published_after = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                except ValueError:
                     print(f"WARNING: Invalid date format for 'published_after' ({self.published_after}). Ignoring filter.")
                     self.published_after = None

        include_str = config.get('Crawler', 'include_channels', fallback='')
        self.include_channels = [ch.strip().lower() for ch in include_str.split(',') if ch.strip()]
        
        exclude_str = config.get('Crawler', 'exclude_channels', fallback='')
        self.exclude_channels = [ch.strip().lower() for ch in exclude_str.split(',') if ch.strip()]

        self.min_view_count = config.getint('Crawler', 'min_view_count')
        self.sort_by = config.get('Crawler', 'sort_by')
        self.max_results = config.getint('Crawler', 'max_results')

        # --- Brand-Specific Output Path (BUG FIX) ---
        safe_brand_name = re.sub(r'\W+', '', self.search_terms.replace(' ', '_'))
        self.output_dir = os.path.join('outputs', safe_brand_name)
        self.output_path = os.path.join(self.output_dir, f"{safe_brand_name}_discovered_videos.csv")
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"SUCCESS: Configuration loaded for brand '{self.search_terms}'.")
        if self.video_type != 'both':
            print(f"Filtering for video type: {self.video_type}")
        if self.published_after:
            print(f"Filtering for videos published after: {self.published_after}")
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
        
        target_channel_ids = []
        if self.include_channels:
            print(f"Resolving channel IDs for targeted search ({len(self.include_channels)} channels)...")
            for ch_name in self.include_channels:
                try:
                    ch_resp = self.youtube_api.search().list(q=ch_name, type="channel", part="id,snippet", maxResults=1).execute()
                    if ch_resp.get("items"):
                        c_id = ch_resp["items"][0]["id"]["channelId"]
                        c_title = ch_resp["items"][0]["snippet"]["title"]
                        target_channel_ids.append(c_id)
                        print(f"  - Resolved '{ch_name}' to {c_title} ({c_id})")
                    else:
                        print(f"  - Warning: Could not find channel matching '{ch_name}'")
                except Exception as e:
                    print(f"  - Error resolving channel '{ch_name}': {e}")
            if not target_channel_ids:
                print("Error: No provided include_channels could be resolved to a valid YouTube Channel ID. Exiting.")
                return

        video_ids = set()
        # Prepare base search arguments
        search_kwargs_base = {
            'part': "id",
            'type': "video",
            'maxResults': 50,
        }
        
        if self.region_code:
            search_kwargs_base['regionCode'] = self.region_code
        
        if self.sort_by == 'date':
            search_kwargs_base['order'] = 'date'
        elif self.sort_by == 'viewCount':
            search_kwargs_base['order'] = 'viewCount'
             
        if self.video_type == 'shorts':
            search_kwargs_base['videoDuration'] = 'short'
        
        if self.published_after:
            search_kwargs_base['publishedAfter'] = self.published_after

        def fetch_pages(search_q, channel_id=None):
            next_page_token = None
            v_ids = set()
            for _ in range(3): # Fetch up to 3 pages per search
                try:
                    kwargs = search_kwargs_base.copy()
                    kwargs["q"] = search_q
                    kwargs["pageToken"] = next_page_token
                    
                    if channel_id:
                        kwargs["channelId"] = channel_id
                        
                    search_response = self.youtube_api.search().list(**kwargs).execute()
                    
                    for item in search_response.get("items", []):
                        v_ids.add(item["id"]["videoId"])
                    
                    next_page_token = search_response.get('nextPageToken')
                    if not next_page_token:
                        break # Exit if there are no more pages
                except HttpError as e:
                    print(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
                    break
            return v_ids

        if target_channel_ids:
            print(f"\nTargeting specific channels for videos...")
            for c_id in target_channel_ids:
                video_ids.update(fetch_pages(query, c_id))
        else:
            print("\nSearching globally for videos...")
            video_ids.update(fetch_pages(query))

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
                    part="snippet,statistics,contentDetails",
                    id=",".join(batch_ids)
                ).execute()
                video_details.extend(details_response.get("items", []))
            except HttpError as e:
                print(f"An HTTP error {e.resp.status} occurred while fetching details:\n{e.content}")
        return video_details

    def _is_short_video(self, video_id):
        """
        Determines if a video is a YouTube Short by checking for redirection.
        Returns True if it's a Short, False otherwise.
        """
        try:
            url = f"https://www.youtube.com/shorts/{video_id}"
            # We only need the headers, so use HEAD request.
            # Allow redirects=False to check the status code directly.
            response = requests.head(url, allow_redirects=False, timeout=5)
            
            # 200 OK means it resides at /shorts/, so it's a Short.
            # 303 See Other (or 302) means it redirects to /watch, so it's a regular video.
            return response.status_code == 200
        except requests.RequestException:
            # If verification fails (e.g. timeout), default to False or log warning.
            # For robustness, we'll assume it's NOT a short if we can't verify.
            return False

    def _process_and_filter_videos(self, video_details):
        """Processes the raw API response, filters it, and returns a DataFrame."""
        processed_videos = []
        
        # If filtering by type, we might need to check many videos.
        # Doing this sequentially is slow. In a production app, we'd use asyncio.
        # For now, we'll check inside the loop but be aware of the latency.
        
        desc = "Processing Videos"
        if self.video_type != 'both':
            desc += f" (Checking for {self.video_type})"

        for video in tqdm(video_details, desc=desc):
            title = video["snippet"]["title"]
            channel_title = video["snippet"]["channelTitle"]
            published_at = video["snippet"]["publishedAt"]
            
            # 1. Filter by excluded keywords in title
            if any(keyword in title.lower() for keyword in self.exclude_keywords):
                continue

            # 1a. Filter by excluded channels dynamically
            if self.exclude_channels and any(exc_ch in channel_title.lower() for exc_ch in self.exclude_channels):
                continue

            stats = video.get("statistics", {})
            view_count = int(stats.get("viewCount", 0))
            
            # 2. Filter by minimum view count
            if view_count < self.min_view_count:
                continue

            # 3. Filter by video type (Shorts vs Videos) - Precise Check
            if self.video_type != 'both':
                is_short = self._is_short_video(video["id"])
                
                if self.video_type == 'shorts' and not is_short:
                    continue
                if self.video_type == 'videos' and is_short:
                    continue

            like_count = int(stats.get("likeCount", 0))
            comment_count = int(stats.get("commentCount", 0))
            
            processed_videos.append({
                "video_id": video["id"],
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video['id']}",
                "channel": channel_title,
                "date": published_at,
                "views": view_count,
                "likes": like_count,
                "comments": comment_count,
                "engagement": like_count + comment_count,
                "description": video["snippet"]["description"],
                "duration": video.get("contentDetails", {}).get("duration", ""),
                "published_at": video.get("snippet", {}).get("publishedAt", "")
            })
        
        return pd.DataFrame(processed_videos)

    def _sort_results(self, df):
        """Sorts the DataFrame based on the configuration."""
        if self.sort_by == 'viewCount':
            return df.sort_values(by="views", ascending=False).reset_index(drop=True)
        elif self.sort_by == 'engagement':
            return df.sort_values(by="engagement", ascending=False).reset_index(drop=True)
        elif self.sort_by == 'date':
            df['parsed_date'] = pd.to_datetime(df['date'])
            df = df.sort_values(by="parsed_date", ascending=False).reset_index(drop=True)
            df = df.drop(columns=['parsed_date'])
            return df
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
