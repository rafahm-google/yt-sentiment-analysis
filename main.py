import argparse
import sys
import os

# Add src to python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from crawler import YouTubeBrandCrawler
from downloader import VideoDownloader
from comment_extractor import YouTubeCommentExtractor
from audio_extractor import AudioExtractor
from pipeline import CachedAnalysisPipeline

def main():
    print("\n" + "!"*60)
    print(" DISCLAIMER: This tool is for educational/research purposes only.")
    print(" Users are responsible for complying with YouTube's Terms of Service.")
    print(" By using this tool, you agree to these terms.")
    print("!"*60 + "\n")

    parser = argparse.ArgumentParser(description="Sentiment Analysis Pipeline")
    parser.add_argument('step', choices=['all', 'crawl', 'download', 'comments', 'audio', 'analyze'], 
                        help="The step of the pipeline to run.")
    parser.add_argument('--config', default='config.ini', help="Path to configuration file.")
    
    args = parser.parse_args()
    
    # Ensure config path is absolute or correctly relative
    if not os.path.exists(args.config):
        print(f"Error: Configuration file '{args.config}' not found.")
        return
        
    config_path = os.path.abspath(args.config)
    
    try:
        if args.step in ['all', 'crawl']:
            print("\n" + "="*40)
            print(" STEP 1: CRAWLING VIDEOS ")
            print("="*40)
            crawler = YouTubeBrandCrawler(config_path=config_path)
            crawler.run_crawler()
            
        if args.step in ['all', 'download']:
            print("\n" + "="*40)
            print(" STEP 2: DOWNLOADING VIDEOS ")
            print("="*40)
            downloader = VideoDownloader(config_path=config_path)
            downloader.download_videos()
            
        if args.step in ['all', 'comments']:
            print("\n" + "="*40)
            print(" STEP 3: EXTRACTING COMMENTS ")
            print("="*40)
            extractor = YouTubeCommentExtractor(config_path=config_path)
            extractor.extract_comments()

        if args.step == 'audio':
            print("\n" + "="*40)
            print(" EXTRA STEP: EXTRACTING AUDIO ")
            print("="*40)
            extractor = AudioExtractor(config_path=config_path)
            extractor.extract_audio()
            
        if args.step in ['all', 'analyze']:
            print("\n" + "="*40)
            print(" STEP 4: RUNNING ANALYSIS PIPELINE ")
            print("="*40)
            pipeline = CachedAnalysisPipeline(config_path=config_path)
            pipeline.run_pipeline()
            
    except Exception as e:
        print(f"\nAn error occurred during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
