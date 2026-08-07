# ==============================================================================
# EEAT ANALYSIS PIPELINE ORCHESTRATOR
# ==============================================================================
# This script orchestrates a two-stage E-E-A-T analysis pipeline:
# 1. Batch Processing (Gemini Flash): Processes videos, comments, and
#    audio in small batches, generating an E-E-A-T audit summary for each.
# 2. Final Synthesis (Gemini Pro): Takes all the cached summaries and
#    synthesizes them into a single, comprehensive strategic report.
# ==============================================================================

import os
import configparser
import pandas as pd
from google import genai
from google.genai import types
import re
from tqdm import tqdm
import markdown
import argparse
import math
import shutil
import time
from dotenv import load_dotenv

class EEATAnalysisPipeline:
    """
    Orchestrates the two-stage E-E-A-T analysis pipeline.
    """
    def __init__(self, config_path):
        print("Initializing EEAT Analysis Pipeline...")
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = config_path
        self._load_environment_variables()
        self._load_configuration()
        
        self.client = genai.Client(api_key=self.google_api_key)
        print("SUCCESS: Google GenAI Client initialized.")

    def _load_environment_variables(self):
        load_dotenv(os.path.join(self.project_root, '.env'))
        self.google_api_key = os.getenv("GEMINI_API_KEY")
        if not self.google_api_key:
            raise ValueError("GEMINI_API_KEY must be set in the .env file.")

    def _load_configuration(self):
        config = configparser.ConfigParser()
        config.read(self.config_path)
        
        self.brand_name = config.get('Crawler', 'search_terms')
        self.safe_brand_name = re.sub(r'\W+', '', self.brand_name.replace(' ', '_'))
        self.run_id = config.get('General', 'run_id', fallback=self.safe_brand_name)
        self.pro_model_name = config.get('Analysis', 'pro_model_name')
        self.flash_model_name = config.get('Analysis', 'flash_model_name')
        self.fallback_model_name = config.get('Analysis', 'fallback_model_name', fallback='gemini-3.1-pro-preview')
        
        # EEAT specific prompt template paths (defaults)
        self.pro_prompt_path = os.path.join(
            self.project_root, 
            config.get('Analysis', 'pro_prompt_template_path', fallback='templates/prompts/eeat_analysis.txt')
        )
        self.flash_prompt_path = os.path.join(
            self.project_root, 
            config.get('Analysis', 'flash_prompt_template_path', fallback='templates/prompts/eeat_flash.txt')
        )
        
        # EEAT specific advertiser channels configuration
        self.advertiser_channels_str = config.get('Analysis', 'advertiser_channels', fallback='')
        
        self.batch_size = config.getint('Analysis', 'batch_size')
        self.report_format = config.get('Analysis', 'report_format')
        self.additional_context = config.get('Analysis', 'additional_context', fallback='')
        self.output_language = config.get('Analysis', 'output_language', fallback='Portuguese')
        
        self.max_results = config.getint('Crawler', 'max_results', fallback=15)
        
        self.output_dir = os.path.join(self.project_root, 'outputs', self.run_id)
        self.videos_csv_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_discovered_videos.csv")
        self.comments_csv_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_raw_comments.csv")
        self.audio_dir = os.path.join(self.output_dir, config.get('AudioExtractor', 'audio_folder_name', fallback='audio'))
        self.video_dir = os.path.join(self.output_dir, config.get('VideoDownloader', 'video_folder_name', fallback='video'))
        self.cache_dir = os.path.join(self.output_dir, config.get('Analysis', 'cache_dir', fallback='cache'))
        
        os.makedirs(self.cache_dir, exist_ok=True)
        print(f"SUCCESS: EEAT Configuration loaded for brand '{self.brand_name}'.")

    def run_pipeline(self):
        """Executes the full cached E-E-A-T analysis pipeline and cleans up afterward."""
        try:
            print("\n▶️  Starting EEAT analysis pipeline...")
            
            videos_df = self._load_data(self.videos_csv_path, "videos")
            comments_df = self._load_data(self.comments_csv_path, "comments")
            if videos_df.empty or comments_df.empty:
                return

            if not videos_df.empty:
                print(f"Limiting analysis to top {self.max_results} videos from config...")
                videos_df = videos_df.head(self.max_results)


            batch_summaries = self._process_batches(videos_df, comments_df)
            if not batch_summaries:
                print("No batch summaries were generated. Exiting.")
                return

            final_report_content = self._synthesize_report(batch_summaries, videos_df, comments_df)
            if not final_report_content:
                print("Failed to generate the final report. Exiting.")
                return
                
            self._generate_report_file(final_report_content, videos_df)

            # Cleanup only after successful completion
            self._cleanup()
        except (ValueError, FileNotFoundError) as e:
            print(f"\nCRITICAL ERROR: {e}")

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
        num_batches = math.ceil(len(videos_df) / self.batch_size)
        all_summaries = [None] * num_batches
        
        def process_single_batch(i):
            batch_num = i + 1
            cache_file_path = os.path.join(self.cache_dir, f"batch_{batch_num}_eeat_summary.txt")

            if os.path.exists(cache_file_path):
                print(f"Found cached EEAT summary for batch {batch_num}. Loading from cache.", flush=True)
                with open(cache_file_path, 'r', encoding='utf-8') as f:
                    return i, f.read()

            print(f"Processing batch {batch_num}/{num_batches} for E-E-A-T...", flush=True)
            start_index = i * self.batch_size
            end_index = start_index + self.batch_size
            batch_videos = videos_df.iloc[start_index:end_index]
            
            batch_video_ids = batch_videos['video_id'].tolist()
            batch_comments = comments_df[comments_df['id_video'].isin(batch_video_ids)]
            
            summary = self._run_flash_analysis(batch_videos, batch_comments)
            
            if summary:
                with open(cache_file_path, 'w', encoding='utf-8') as f:
                    f.write(summary)
                print(f"SUCCESS: Saved EEAT summary for batch {batch_num} to cache.", flush=True)
                return i, summary
            else:
                print(f"Warning: Failed to generate EEAT summary for batch {batch_num}.")
                return i, None

        print(f"\nStarting Stage 1 (Parallel): Processing {len(videos_df)} videos in {num_batches} batches...", flush=True)
        
        # Use 5 workers to avoid overwhelming rate limits
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_single_batch, i) for i in range(num_batches)]
            for future in as_completed(futures):
                i, summary = future.result()
                all_summaries[i] = summary
        
        valid_summaries = [s for s in all_summaries if s is not None]
        return valid_summaries

    def _run_flash_analysis(self, videos, comments):
        with open(self.flash_prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        video_metadata = videos[['video_id', 'title', 'channel', 'views', 'likes', 'comments']].to_string(index=False)
        
        # Limit comments to avoid blowing up the context in large batches
        comments_text = "\n".join([
            f"- Video ID: {row['id_video']} | Comentário: {str(row['texto_comentario'])}" 
            for _, row in comments.dropna(subset=['texto_comentario']).iterrows()
        ])
        
        prompt = prompt_template.replace('{{TOPIC_NAME}}', self.brand_name)
        prompt = prompt.replace('{{VIDEO_METADATA}}', video_metadata)
        prompt = prompt.replace('{{COMMENTS_DATA}}', comments_text)
        
        try:
            contents = [prompt]
            file_list_str = ""
            for _, row in videos.iterrows():
                video_url = row['url']
                contents.append(
                    types.Part(
                        file_data=types.FileData(
                            file_uri=video_url,
                            mime_type="video/mp4"
                        )
                    )
                )
                file_list_str += f"- {video_url}\n"
            
            final_prompt = prompt.replace('{{MEDIA_FILES_LIST}}', file_list_str).replace('{{AUDIO_FILES_LIST}}', file_list_str)
            contents[0] = final_prompt

            response = self.client.models.generate_content(
                model=self.flash_model_name,
                contents=contents
            )
            return response.text
        except Exception as e:
            print(f"An error occurred during Gemini Flash API call: {e}")
            return None

    def _synthesize_report(self, summaries, videos_df, comments_df):
        print("\nStarting Stage 2: Synthesizing final E-E-A-T report with Gemini Pro...")
        with open(self.pro_prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        batch_summaries_text = "\n\n---\n\n".join(summaries)
        total_videos = len(videos_df)
        total_views = videos_df['views'].sum()
        total_likes = videos_df['likes'].sum()
        total_engagement = videos_df['engagement'].sum()
        total_comments_extracted = len(comments_df)
        
        prompt = prompt_template.replace('{{BRAND_NAME}}', self.brand_name)
        prompt = prompt.replace('{{BATCH_SUMMARIES}}', batch_summaries_text)
        
        advertiser_channels_info = self.advertiser_channels_str if self.advertiser_channels_str else "Nenhum canal de anunciante especificado na configuração."
        prompt = prompt.replace('{{ADVERTISER_CHANNELS}}', advertiser_channels_info)
        
        prompt = prompt.replace('{{TOTAL_VIDEOS}}', str(total_videos))
        prompt = prompt.replace('{{TOTAL_VIEWS}}', f"{total_views:,}")
        prompt = prompt.replace('{{TOTAL_LIKES}}', f"{total_likes:,}")
        prompt = prompt.replace('{{TOTAL_ENGAGEMENT}}', f"{total_engagement:,}")
        prompt = prompt.replace('{{TOTAL_COMMENTS_EXTRACTED}}', f"{total_comments_extracted:,}")
        
        if self.additional_context:
            prompt += f"\n\nInformações/Diretrizes Adicionais do Usuário (PRIORIDADE MÁXIMA):\n{self.additional_context}"
            prompt += "\nIMPORTANTE: Priorize as diretrizes adicionais do usuário acima sobre as regras do prompt original se houver conflito."
            
        prompt += f"\n\nIDIOMA DE SAÍDA: O relatório final DEVE ser gerado no idioma: {self.output_language}."

        try:
            response = self.client.models.generate_content(
                model=self.pro_model_name,
                contents=prompt
            )
            print(f"SUCCESS: Final E-E-A-T report generated by Primary model ({self.pro_model_name}).")
            return response.text
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                print(f"Primary model ({self.pro_model_name}) overloaded (503). Retrying once after 5 seconds...")
                time.sleep(5)
                try:
                    response = self.client.models.generate_content(
                        model=self.pro_model_name,
                        contents=prompt
                    )
                    print(f"SUCCESS: Final E-E-A-T report generated by Primary model ({self.pro_model_name}) after retry.")
                    return response.text
                except Exception as e2:
                    print(f"Primary model failed again. Falling back to Fallback model ({self.fallback_model_name})...")
                    try:
                        response = self.client.models.generate_content(
                            model=self.fallback_model_name,
                            contents=prompt
                        )
                        print(f"SUCCESS: Final E-E-A-T report generated by Fallback model ({self.fallback_model_name}).")
                        return response.text
                    except Exception as e3:
                        print(f"All models failed: {e3}")
                        return None
            else:
                print(f"An error occurred during Gemini API call: {e}")
                return None

    def _generate_report_file(self, report_content, videos_df):
        output_path = os.path.join(self.output_dir, f"{self.safe_brand_name}_strategic_report.{self.report_format}")
        
        # --- Create Appendix Table ---
        appendix_header = "## Apêndice: Top 15 Vídeos Analisados por Visualizações\n\n"
        appendix_df = videos_df.sort_values(by='views', ascending=False).head(15).copy()
        
        # Replace pipe characters to avoid malforming the markdown table columns
        appendix_df['title'] = appendix_df['title'].astype(str).str.replace('|', '-', regex=False)
        appendix_df['channel'] = appendix_df['channel'].astype(str).str.replace('|', '-', regex=False)
        
        # Format numbers with thousand separators
        for col in ['views', 'likes', 'comments']:
            appendix_df[col] = appendix_df[col].apply(lambda x: f"{x:,}")

        appendix_table = appendix_df[['title', 'channel', 'views', 'likes', 'comments']].to_markdown(index=False)
        
        # Combine main content and appendix
        full_report_md = report_content + "\n\n---\n\n" + appendix_header + appendix_table

        if self.report_format == 'html':
            html_content = markdown.markdown(full_report_md, extensions=['tables'])
            template_path = os.path.join(self.project_root, 'templates', 'strategic_report_template.html')
            with open(template_path, 'r', encoding='utf-8') as f:
                report_template = f.read()
            final_html = report_template.replace('{{BRAND_NAME}}', self.brand_name)
            final_html = final_html.replace('{{ANALYSIS_CONTENT}}', html_content)
            report_content = final_html
        else:
            report_content = full_report_md

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"\n\nSUCCESS: Strategic report saved to '{output_path}'.")

    def _cleanup(self):
        """Removes the audio and cache directories."""
        print("\n▶️  Cleaning up temporary files...")
        if os.path.isdir(self.audio_dir):
            try:
                shutil.rmtree(self.audio_dir)
                print(f"SUCCESS: Removed audio directory: '{self.audio_dir}'")
            except OSError as e:
                print(f"Error removing audio directory '{self.audio_dir}': {e.strerror}")
        
        if os.path.isdir(self.video_dir):
            try:
                shutil.rmtree(self.video_dir)
                print(f"SUCCESS: Removed video directory: '{self.video_dir}'")
            except OSError as e:
                print(f"Error removing video directory '{self.video_dir}': {e.strerror}")
        
        if os.path.isdir(self.cache_dir):
            try:
                shutil.rmtree(self.cache_dir)
                print(f"SUCCESS: Removed cache directory: '{self.cache_dir}'")
            except OSError as e:
                print(f"Error removing cache directory '{self.cache_dir}': {e.strerror}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EEAT Analysis Pipeline Orchestrator")
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini"),
        help="Path to the configuration file."
    )
    args = parser.parse_args()

    try:
        pipeline = EEATAnalysisPipeline(config_path=args.config)
        pipeline.run_pipeline()
    except (ValueError, FileNotFoundError) as e:
        print(f"\nCRITICAL ERROR: {e}")
