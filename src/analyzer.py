# ==============================================================================
# GEMINI-POWERED BRAND ANALYZER
# ==============================================================================
# This script performs a deep analysis of brand perception using YouTube
# comments and audio transcriptions, leveraging the Gemini Pro model.
#
# How it works:
# 1. Reads configuration from a specified .ini file.
# 2. Finds the relevant raw comments CSV and audio files for the brand.
# 3. Loads a prompt template and injects the aggregated data.
# 4. Sends the text and audio files to the Gemini API for analysis.
# 5. Processes the Markdown response from the model.
# 6. Converts the analysis to HTML if required.
# 7. Populates a report template with the analysis.
# 8. Saves the final strategic report to the brand's output directory.
# ==============================================================================

import os
import configparser
import pandas as pd
import google.generativeai as genai
import re
from tqdm import tqdm
import markdown
import argparse
from dotenv import load_dotenv

class GeminiBrandAnalyzer:
    """
    Analyzes brand perception using comments and audio with Gemini.
    """
    def __init__(self, config_path=None, env_path=None):
        """Initializes the analyzer by loading configuration."""
        print("Initializing Gemini Brand Analyzer...")
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if config_path is None:
            config_path = os.path.join(self.project_root, 'config.ini')
        if env_path is None:
            env_path = os.path.join(self.project_root, '.env')

        self._load_environment_variables(env_path)
        self._load_configuration(config_path)
        
        genai.configure(api_key=self.google_api_key)
        print("SUCCESS: Google AI SDK configured.")

    def _load_environment_variables(self, env_path):
        """Loads API keys from a .env file."""
        load_dotenv(dotenv_path=env_path)
        self.google_api_key = os.getenv("GEMINI_API_KEY")
        if not self.google_api_key:
            raise ValueError("GEMINI_API_KEY must be set in the .env file.")
        print("SUCCESS: Environment variables loaded.")

    def _load_configuration(self, config_path):
        """Loads settings from the specified config file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
        
        config = configparser.ConfigParser()
        config.read(config_path)
        
        # Crawler settings needed to find the right files
        self.brand_name = config.get('Crawler', 'search_terms')
        
        # Analysis settings
        self.model_name = config.get('Analysis', 'pro_model_name')
        
        self.prompt_template_path = os.path.join(self.project_root, config.get('Analysis', 'pro_prompt_template_path'))
        self.report_format = config.get('Analysis', 'report_format')
        self.comments_path = config.get('Analysis', 'comments_csv_path', fallback=None)
        
        # Brand-specific paths
        self.safe_brand_name = re.sub(r'\W+', '', self.brand_name.replace(' ', '_'))
        # Make output paths relative to the project root
        self.output_dir = os.path.join(self.project_root, 'outputs', self.safe_brand_name)
        self.videos_csv_path = os.path.join(self.project_root, 'outputs', self.safe_brand_name, f"{self.safe_brand_name}_discovered_videos.csv")
        
        # If comments_csv_path is not specified in config, construct it dynamically
        if not self.comments_path:
            self.comments_path = os.path.join(self.project_root, 'outputs', self.safe_brand_name, f"{self.safe_brand_name}_raw_comments.csv")
        else:
            # Also make the config path relative to the project root
            self.comments_path = os.path.join(self.project_root, self.comments_path)
            
        self.audio_dir = os.path.join(self.output_dir, config.get('AudioExtractor', 'audio_folder_name', fallback='audio'))
        
        print(f"SUCCESS: Configuration loaded for brand '{self.brand_name}'.")

    def run_analysis(self):
        """Executes the full analysis pipeline."""
        print("\n▶️  Starting brand analysis...")

        # 1. Load data
        comments_df = self._load_comments()
        if comments_df.empty:
            print("No comments found to analyze. Exiting.")
            return
            
        videos_df = self._load_videos_data()
        
        audio_files = self._find_audio_files()
        if not audio_files:
            print("Warning: No audio files found. Analysis will be based on comments only.")

        # 2. Prepare prompt
        prompt = self._prepare_prompt(comments_df, videos_df)
        
        # 3. Interact with Gemini API
        print(f"\nSending data to Gemini model: '{self.model_name}'...")
        analysis_content = self._generate_analysis(prompt, audio_files)
        
        if not analysis_content:
            print("Failed to generate analysis from the model. Exiting.")
            return
            
        print("SUCCESS: Analysis received from model.")

        # 4. Generate and save report
        self._generate_report(analysis_content)

    def _load_comments(self):
        """Loads the raw comments CSV file for the brand."""
        print(f"Loading comments from '{self.comments_path}'...")
        if not os.path.exists(self.comments_path):
            print(f"Error: Comments file not found at '{self.comments_path}'.")
            return pd.DataFrame()
        try:
            return pd.read_csv(self.comments_path)
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return pd.DataFrame()

    def _load_videos_data(self):
        """Loads the discovered videos CSV to get aggregate stats."""
        print(f"Loading video data from '{self.videos_csv_path}'...")
        if not os.path.exists(self.videos_csv_path):
            print(f"Warning: Videos CSV not found at '{self.videos_csv_path}'. Cannot calculate aggregate stats.")
            return pd.DataFrame()
        try:
            return pd.read_csv(self.videos_csv_path)
        except Exception as e:
            print(f"Error reading videos CSV file: {e}")
            return pd.DataFrame()

    def _find_audio_files(self):
        """Finds all MP3 files in the brand's audio directory."""
        print(f"Searching for audio files in '{self.audio_dir}'...")
        if not os.path.isdir(self.audio_dir):
            return []
        
        return [os.path.join(self.audio_dir, f) for f in os.listdir(self.audio_dir) if f.endswith('.mp3')]

    def _prepare_prompt(self, comments_df, videos_df):
        """Loads the prompt template and injects the data."""
        with open(self.prompt_template_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        # Aggregate comments into a single string
        comments_text = "\n".join("- " + str(comment) for comment in comments_df['texto_comentario'].dropna())
        
        # Calculate aggregate stats
        total_videos = len(videos_df) if not videos_df.empty else 0
        total_views = videos_df['views'].sum() if not videos_df.empty and 'views' in videos_df.columns else 0
        total_likes = videos_df['likes'].sum() if not videos_df.empty and 'likes' in videos_df.columns else 0
        total_comments_stats = videos_df['comments'].sum() if not videos_df.empty and 'comments' in videos_df.columns else 0
        total_engagement = videos_df['engagement'].sum() if not videos_df.empty and 'engagement' in videos_df.columns else 0
        total_comments_extracted = len(comments_df)

        # Replace placeholders
        prompt = prompt_template.replace('{{BRAND_NAME}}', self.brand_name)
        prompt = prompt.replace('{{COMMENTS_DATA}}', comments_text)
        prompt = prompt.replace('{{TOTAL_VIDEOS}}', str(total_videos))
        prompt = prompt.replace('{{TOTAL_VIEWS}}', f"{total_views:,}")
        prompt = prompt.replace('{{TOTAL_LIKES}}', f"{total_likes:,}")
        prompt = prompt.replace('{{TOTAL_COMMENTS_STATS}}', f"{total_comments_stats:,}")
        prompt = prompt.replace('{{TOTAL_ENGAGEMENT}}', f"{total_engagement:,}")
        prompt = prompt.replace('{{TOTAL_COMMENTS_EXTRACTED}}', f"{total_comments_extracted:,}")
        
        return prompt

    def _generate_analysis(self, prompt, audio_files):
        """Sends data to the Gemini API and returns the response."""
        try:
            model = genai.GenerativeModel(self.model_name)
            
            # Prepare files for the API
            uploaded_files = []
            if audio_files:
                print(f"Uploading {len(audio_files)} audio files...")
                for file_path in tqdm(audio_files, desc="Uploading Files"):
                    uploaded_files.append(genai.upload_file(path=file_path))
            
            # Update the prompt with the list of files to be analyzed
            file_list_str = "\n".join([f"- {f.display_name}" for f in uploaded_files])
            final_prompt = prompt.replace('{{AUDIO_FILES_LIST}}', file_list_str)
            
            # Generate content
            response = model.generate_content([final_prompt] + uploaded_files)
            return response.text
        except Exception as e:
            print(f"An error occurred during Gemini API call: {e}")
            return None

    def _generate_report(self, analysis_content):
        """Saves the final report in the specified format."""
        file_extension = self.report_format
        output_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_strategic_report.{file_extension}")
        
        report_content = analysis_content
        
        if self.report_format == 'html':
            print("Converting analysis to HTML...")
            html_content = markdown.markdown(analysis_content)
            
            template_path = os.path.join(self.project_root, 'templates', 'strategic_report_template.html')
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"Report template not found at '{template_path}'")
                
            with open(template_path, 'r', encoding='utf-8') as f:
                report_template = f.read()
            
            report_content = report_template.replace('{{BRAND_NAME}}', self.brand_name)
            report_content = report_content.replace('{{ANALYSIS_CONTENT}}', html_content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
            
        print(f"\n\nSUCCESS: Strategic report saved to '{output_path}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini-Powered Brand Analyzer")
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini"),
        help="Path to the configuration file."
    )
    args = parser.parse_args()

    try:
        analyzer = GeminiBrandAnalyzer(config_path=args.config)
        analyzer.run_analysis()
    except (ValueError, FileNotFoundError) as e:
        print(f"\nCRITICAL ERROR: {e}")