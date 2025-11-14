# ==============================================================================
# YT SENTIMENT ANALYSIS - MAIN ORCHESTRATOR
# ==============================================================================
# This script serves as the main entry point for the entire YT Sentiment Analysis
# Suite. It orchestrates the execution of the different modules in the correct
# order to perform a full brand analysis from start to finish.
#
# Execution Flow:
# 1. Crawl YouTube for brand-related videos.
# 2. Extract comments from the discovered videos.
# 3. Extract audio from the discovered videos.
# 4. Run the cached analysis pipeline to generate the final strategic report.
# ==============================================================================

import argparse
import sys
import os

# Add the project root to the Python path to allow for absolute imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from yt-sentiment-analysis.scripts.youtube_brand_crawler import YouTubeBrandCrawler
from yt-sentiment-analysis.scripts.youtube_comment_extractor import YouTubeCommentExtractor
from yt-sentiment-analysis.scripts.audio_extractor import AudioExtractor
from yt-sentiment-analysis.scripts.cached_analysis_pipeline import CachedAnalysisPipeline

def run_full_pipeline(config_path):
    """
    Executes the complete analysis pipeline step-by-step.

    Args:
        config_path (str): The path to the configuration file.
    """
    try:
        print("=================================================")
        print("🚀 STARTING YT SENTIMENT ANALYSIS")
        print(f"⚙️  Using configuration: {config_path}")
        print("=================================================")

        # === STEP 1: Crawl YouTube for Videos ===
        print("\n[STEP 1/4] crawling YouTube for videos...")
        crawler = YouTubeBrandCrawler(config_path=config_path)
        crawler.run_crawler()
        print("✅ [STEP 1/4] Finished crawling.")

        # === STEP 2: Extract Comments ===
        print("\n[STEP 2/4] Extracting comments...")
        comment_extractor = YouTubeCommentExtractor(config_path=config_path)
        comment_extractor.extract_comments()
        print("✅ [STEP 2/4] Finished extracting comments.")

        # === STEP 3: Extract Audio ===
        print("\n[STEP 3/4] Extracting audio...")
        audio_extractor = AudioExtractor(config_path=config_path)
        audio_extractor.extract_audio()
        print("✅ [STEP 3/4] Finished extracting audio.")

        # === STEP 4: Run Cached Analysis Pipeline ===
        print("\n[STEP 4/4] Running analysis pipeline...")
        pipeline = CachedAnalysisPipeline(config_path=config_path)
        pipeline.run_pipeline()
        print("✅ [STEP 4/4] Finished analysis.")

        print("\n=================================================")
        print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
        print("=================================================")

    except (ValueError, FileNotFoundError) as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        print("Pipeline aborted.")
    except Exception as e:
        print(f"\n❌ AN UNEXPECTED ERROR OCCURRED: {e}")
        print("Pipeline aborted.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the full YT Sentiment Analysis pipeline.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--config",
        default="config/config_gemini.ini",
        help="Path to the configuration file (default: config/config_gemini.ini)."
    )
    args = parser.parse_args()

    # Ensure the config path exists
    if not os.path.exists(args.config):
        print(f"❌ Error: Configuration file not found at '{args.config}'")
        sys.exit(1)

    run_full_pipeline(args.config)
