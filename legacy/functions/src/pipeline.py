# ==============================================================================
# CACHED ANALYSIS PIPELINE ORCHESTRATOR
# ==============================================================================
# This script orchestrates a two-stage analysis pipeline.
# ==============================================================================

import os
import configparser
import pandas as pd
import google.generativeai as genai
import re
from tqdm import tqdm
import markdown
import argparse
import math
import shutil
import time
from dotenv import load_dotenv

class CachedAnalysisPipeline:
    """
    Orchestrates the two-stage analysis pipeline.
    """
    def __init__(self, config_dict=None, config_path=None):
        print("Initializing Cached Analysis Pipeline...")
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._load_environment_variables()
        if config_dict:
            self._load_configuration_from_dict(config_dict)
        else:
            if config_path is None:
                config_path = os.path.join(self.project_root, 'config.ini')
            self._load_configuration(config_path)
        
        genai.configure(api_key=self.google_api_key)
        print("SUCCESS: Google AI SDK configured.")

    def _load_environment_variables(self):
        self.google_api_key = os.getenv("GEMINI_API_KEY")
        if not self.google_api_key:
            # Fallback for local testing
            load_dotenv(os.path.join(self.project_root, '.env'))
            self.google_api_key = os.getenv("GEMINI_API_KEY")
            if not self.google_api_key:
                raise ValueError("GEMINI_API_KEY must be set in environment.")

    def _load_configuration_from_dict(self, config):
        """Loads settings from a dictionary."""
        self.brand_name = config.get('search_terms')
        self.safe_brand_name = re.sub(r'\W+', '', self.brand_name.replace(' ', '_'))
        self.pro_model_name = config.get('pro_model_name', 'gemini-1.5-pro')
        self.flash_model_name = config.get('flash_model_name', 'gemini-1.5-flash')
        
        # In Cloud Functions, prompts should be relative to this file or absolute
        self.pro_prompt_path = os.path.join(os.path.dirname(self.project_root), config.get('pro_prompt_template_path', 'templates/prompts/topic_analysis.txt'))
        self.flash_prompt_path = os.path.join(os.path.dirname(self.project_root), config.get('flash_prompt_template_path', 'templates/prompts/topic_flash.txt'))
        
        self.batch_size = int(config.get('batch_size', 3))
        self.report_format = config.get('report_format', 'html')
        
        base_output_dir = config.get('base_output_dir', 'outputs')
        self.output_dir = os.path.join(base_output_dir, self.safe_brand_name)
        self.videos_csv_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_discovered_videos.csv")
        self.comments_csv_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_raw_comments.csv")
        self.audio_dir = os.path.join(self.output_dir, config.get('audio_folder_name', 'audio'))
        self.video_dir = os.path.join(self.output_dir, config.get('video_folder_name', 'video'))
        self.cache_dir = os.path.join(self.output_dir, config.get('cache_dir', 'cache'))
        
        os.makedirs(self.cache_dir, exist_ok=True)
        print(f"SUCCESS: Configuration loaded for brand '{self.brand_name}'.")

    def _load_configuration(self, config_path):
        config = configparser.ConfigParser()
        config.read(config_path)
        
        self.brand_name = config.get('Crawler', 'search_terms')
        self.safe_brand_name = re.sub(r'\W+', '', self.brand_name.replace(' ', '_'))
        self.pro_model_name = config.get('Analysis', 'pro_model_name')
        self.flash_model_name = config.get('Analysis', 'flash_model_name')
        
        # Paths relative to project root
        self.pro_prompt_path = os.path.join(self.project_root, config.get('Analysis', 'pro_prompt_template_path'))
        self.flash_prompt_path = os.path.join(self.project_root, config.get('Analysis', 'flash_prompt_template_path'))
        self.batch_size = config.getint('Analysis', 'batch_size')
        self.report_format = config.get('Analysis', 'report_format')
        
        self.output_dir = os.path.join(self.project_root, 'outputs', self.safe_brand_name)
        self.videos_csv_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_discovered_videos.csv")
        self.comments_csv_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_raw_comments.csv")
        self.audio_dir = os.path.join(self.output_dir, config.get('AudioExtractor', 'audio_folder_name', fallback='audio'))
        self.video_dir = os.path.join(self.output_dir, config.get('VideoDownloader', 'video_folder_name', fallback='video'))
        self.cache_dir = os.path.join(self.output_dir, config.get('Analysis', 'cache_dir', fallback='cache'))
        
        os.makedirs(self.cache_dir, exist_ok=True)
        print(f"SUCCESS: Configuration loaded for brand '{self.brand_name}'.")

    def run_pipeline(self):
        """Executes the full cached analysis pipeline and cleans up afterward."""
        try:
            print("\n▶️  Starting analysis pipeline...")
            
            videos_df = self._load_data(self.videos_csv_path, "videos")
            comments_df = self._load_data(self.comments_csv_path, "comments")
            if videos_df.empty or comments_df.empty:
                return None

            batch_summaries = self._process_batches(videos_df, comments_df)
            if not batch_summaries:
                print("No batch summaries were generated. Exiting.")
                return None

            final_report_content = self._synthesize_report(batch_summaries, videos_df, comments_df)
            if not final_report_content:
                print("Failed to generate the final report. Exiting.")
                return None
                
            report_path = self._generate_report_file(final_report_content, videos_df)
            return report_path
        except (ValueError, FileNotFoundError) as e:
            print(f"\nCRITICAL ERROR: {e}")
            return None

    def _load_data(self, path, name):
        print(f"Loading {name} data from '{path}'...")
        if not os.path.exists(path):
            print(f"Error: {name.capitalize()} file not found at '{path}'.")
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except Exception as e:
            print(f"Error reading {name} CSV file: {e}")
            return pd.DataFrame()

    def _process_batches(self, videos_df, comments_df):
        all_summaries = []
        num_batches = math.ceil(len(videos_df) / self.batch_size)
        print(f"\nStarting Stage 1: Processing {len(videos_df)} videos in {num_batches} batches...")

        for i in tqdm(range(num_batches), desc="Processing Batches"):
            batch_num = i + 1
            cache_file_path = os.path.join(self.cache_dir, f"batch_{batch_num}_summary.txt")

            if os.path.exists(cache_file_path):
                print(f"\nFound cached summary for batch {batch_num}. Loading from cache.")
                with open(cache_file_path, 'r', encoding='utf-8') as f:
                    summary = f.read()
                all_summaries.append(summary)
                continue

            print(f"\nProcessing batch {batch_num}/{num_batches}...")
            start_index = i * self.batch_size
            end_index = start_index + self.batch_size
            batch_videos = videos_df.iloc[start_index:end_index]
            
            batch_video_ids = batch_videos['video_id'].tolist()
            batch_comments = comments_df[comments_df['id_video'].isin(batch_video_ids)]
            
            # Check for video files first, then audio files
            media_files = []
            
            for vid in batch_video_ids:
                video_path = os.path.join(self.video_dir, f"{vid}.mp4")
                if os.path.exists(video_path):
                    media_files.append(video_path)
                else:
                    audio_path = os.path.join(self.audio_dir, f"{vid}.mp3")
                    if os.path.exists(audio_path):
                        media_files.append(audio_path)
            
            if not media_files:
                print(f"Warning: No media files (video or audio) found for batch {batch_num}.")

            summary = self._run_flash_analysis(batch_videos, batch_comments, media_files)
            
            if summary:
                with open(cache_file_path, 'w', encoding='utf-8') as f:
                    f.write(summary)
                print(f"SUCCESS: Saved summary for batch {batch_num} to cache.")
                all_summaries.append(summary)
            else:
                print(f"Warning: Failed to generate summary for batch {batch_num}.")
        
        return all_summaries

    def _wait_for_files_active(self, files):
        """Waits for uploaded files to be in ACTIVE state."""
        print("Waiting for file processing...", end="")
        for name in (f.name for f in files):
            file = genai.get_file(name)
            while file.state.name == "PROCESSING":
                print(".", end="", flush=True)
                time.sleep(2)
                file = genai.get_file(name)
            if file.state.name != "ACTIVE":
                raise Exception(f"File {file.name} failed to process: {file.state.name}")
        print("Done")

    def _run_flash_analysis(self, videos, comments, media_files):
        if not os.path.exists(self.flash_prompt_path):
            print(f"Error: Flash prompt template not found at {self.flash_prompt_path}")
            return None
        with open(self.flash_prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        video_metadata = videos[['title', 'views', 'likes', 'comments']].to_string(index=False)
        comments_text = "\n".join([f"- {str(comment)}" for comment in comments['texto_comentario'].dropna()])
        
        prompt = prompt_template.replace('{{BRAND_NAME}}', self.brand_name)
        prompt = prompt.replace('{{TOPIC_NAME}}', self.brand_name)
        prompt = prompt.replace('{{VIDEO_METADATA}}', video_metadata)
        prompt = prompt.replace('{{COMMENTS_DATA}}', comments_text)

        try:
            model = genai.GenerativeModel(self.flash_model_name)
            uploaded_files = [genai.upload_file(path=f) for f in media_files]
            self._wait_for_files_active(uploaded_files)
            
            file_list_str = "\n".join([f"- {os.path.basename(f.name)}" for f in uploaded_files])
            final_prompt = prompt.replace('{{AUDIO_FILES_LIST}}', file_list_str).replace('{{MEDIA_FILES_LIST}}', file_list_str)
            
            response = model.generate_content([final_prompt] + uploaded_files)
            return response.text
        except Exception as e:
            print(f"An error occurred during Gemini Flash API call: {e}")
            return None

    def _synthesize_report(self, summaries, videos_df, comments_df):
        print("\nStarting Stage 2: Synthesizing final report with Gemini Pro...")
        if not os.path.exists(self.pro_prompt_path):
             print(f"Error: Pro prompt template not found at {self.pro_prompt_path}")
             return None
        with open(self.pro_prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        batch_summaries_text = "\n\n---\n\n".join(summaries)
        total_videos = len(videos_df)
        total_views = videos_df['views'].sum()
        total_likes = videos_df['likes'].sum()
        total_comments_stats = videos_df['comments'].sum()
        total_engagement = videos_df['engagement'].sum()
        total_comments_extracted = len(comments_df)
        
        prompt = prompt_template.replace('{{BRAND_NAME}}', self.brand_name)
        prompt = prompt.replace('{{TOPIC_NAME}}', self.brand_name)
        prompt = prompt.replace('{{BATCH_SUMMARIES}}', batch_summaries_text)
        prompt = prompt.replace('{{TOTAL_VIDEOS}}', str(total_videos))
        prompt = prompt.replace('{{TOTAL_VIEWS}}', f"{total_views:,}")
        prompt = prompt.replace('{{TOTAL_LIKES}}', f"{total_likes:,}")
        prompt = prompt.replace('{{TOTAL_COMMENTS_STATS}}', f"{total_comments_stats:,}")
        prompt = prompt.replace('{{TOTAL_ENGAGEMENT}}', f"{total_engagement:,}")
        prompt = prompt.replace('{{TOTAL_COMMENTS_EXTRACTED}}', f"{total_comments_extracted:,}")

        try:
            model = genai.GenerativeModel(self.pro_model_name)
            response = model.generate_content(prompt)
            print("SUCCESS: Final report generated by Gemini Pro.")
            return response.text
        except Exception as e:
            print(f"An error occurred during Gemini Pro API call: {e}")
            return None

    def _generate_report_file(self, report_content, videos_df):
        output_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_strategic_report.{self.report_format}")
        
        # --- Create Appendix Table ---
        appendix_header = "## Apêndice: Top 15 Vídeos Analisados por Visualizações\n\n"
        appendix_df = videos_df.sort_values(by='views', ascending=False).head(15)
        
        # Format numbers with thousand separators
        for col in ['views', 'likes', 'comments']:
            appendix_df[col] = appendix_df[col].apply(lambda x: f"{x:,}")

        appendix_table = appendix_df[['title', 'channel', 'views', 'likes', 'comments']].to_markdown(index=False)
        
        # Combine main content and appendix
        full_report_md = report_content + "\n\n---\n\n" + appendix_header + appendix_table

        if self.report_format == 'html':
            html_content = markdown.markdown(full_report_md, extensions=['tables'])
            template_path = os.path.join(os.path.dirname(self.project_root), 'templates', 'strategic_report_template.html')
            if not os.path.exists(template_path):
                # Fallback to local path if running inside functions
                template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'templates', 'strategic_report_template.html')
            
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    report_template = f.read()
                final_html = report_template.replace('{{BRAND_NAME}}', self.brand_name)
                final_html = final_html.replace('{{ANALYSIS_CONTENT}}', html_content)
                report_content = final_html
            else:
                print(f"Warning: HTML template not found at {template_path}. Saving raw HTML.")
                report_content = html_content
        else:
            report_content = full_report_md

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"\n\nSUCCESS: Strategic report saved to '{output_path}'.")
        return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cached Analysis Pipeline Orchestrator")
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini"),
        help="Path to the configuration file."
    )
    args = parser.parse_args()

    try:
        pipeline = CachedAnalysisPipeline(config_path=args.config)
        pipeline.run_pipeline()
    except (ValueError, FileNotFoundError) as e:
        print(f"\nCRITICAL ERROR: {e}")
