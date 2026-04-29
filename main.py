import argparse
import sys
import os

# Add src to python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from crawler import YouTubeBrandCrawler
from comment_extractor import YouTubeCommentExtractor
from pipeline import CachedAnalysisPipeline

def main():
    print("\n" + "!"*60)
    print(" DISCLAIMER: This tool is for educational/research purposes only.")
    print(" Users are responsible for complying with YouTube's Terms of Service.")
    print(" By using this tool, you agree to these terms.")
    print("!"*60 + "\n")

    parser = argparse.ArgumentParser(description="Sentiment Analysis Pipeline")
    parser.add_argument('step', choices=['all', 'crawl', 'comments', 'analyze', 'slides'], 
                        help="The step of the pipeline to run.")
    parser.add_argument('--config', default='config.ini', help="Path to configuration file.")
    
    args = parser.parse_args()
    
    # Ensure config path is absolute or correctly relative
    if not os.path.exists(args.config):
        print(f"Error: Configuration file '{args.config}' not found.")
        sys.exit(1)
        
    config_path = os.path.abspath(args.config)
    
    try:
        if args.step in ['all', 'crawl']:
            print("\n" + "="*40)
            print(" STEP 1: CRAWLING VIDEOS ")
            print("="*40)
            crawler = YouTubeBrandCrawler(config_path=config_path)
            crawler.run_crawler()
            

            
        if args.step in ['all', 'comments']:
            print("\n" + "="*40)
            print(" STEP 3: EXTRACTING COMMENTS ")
            print("="*40)
            extractor = YouTubeCommentExtractor(config_path=config_path)
            extractor.extract_comments()


            
        if args.step in ['all', 'analyze']:
            print("\n" + "="*40)
            print(" STEP 4: RUNNING ANALYSIS PIPELINE ")
            print("="*40)
            pipeline = CachedAnalysisPipeline(config_path=config_path)
            pipeline.run_pipeline()
            
        if args.step in ['all', 'slides']:
            print("\n" + "="*40)
            print(" STEP 5: GENERATING SLIDES ")
            print("="*40)
            from generate_slides_final import run_slide_generation
            run_slide_generation(config_path=config_path)
            
    except Exception as e:
        print(f"\nAn error occurred during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
