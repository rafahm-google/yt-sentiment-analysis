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
    parser.add_argument('step', choices=['all', 'plan', 'crawl', 'comments', 'analyze', 'slides'], 
                        help="The step of the pipeline to run.")
    parser.add_argument('--config', default='config.ini', help="Path to configuration file.")
    parser.add_argument('--briefing', help="Campaign briefing text for Gemini Deep Thinking planning.")
    
    args = parser.parse_args()
    
    # Ensure config path is absolute or correctly relative
    if not os.path.exists(args.config):
        print(f"Error: Configuration file '{args.config}' not found.")
        sys.exit(1)
        
    config_path = os.path.abspath(args.config)
    
    import json
    from datetime import datetime
    import configparser
    from briefing_planner import BriefingPlanner
    
    # Read config for logging
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_path)
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "step": args.step,
        "config_file": args.config,
        "search_terms": config.get('Crawler', 'search_terms', fallback='N/A'),
        "max_results": config.get('Crawler', 'max_results', fallback='N/A'),
        "max_comments": config.get('Crawler', 'max_comments_per_video', fallback='N/A')
    }
    
    log_file_path = os.path.join(os.path.dirname(__file__), 'outputs', 'usage_log.jsonl')
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    
    try:
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
        print(f"Logged execution to {log_file_path}")
    except Exception as e:
        # On Cloud Run, the filesystem is ephemeral, so this might fail.
        pass
        
    # Print structured log for Cloud Run (Cloud Logging)
    print(f"USAGE_LOG:{json.dumps(log_entry)}")

    try:
        if args.step == 'plan' or args.briefing:
            print("\n" + "="*40)
            print(" STEP 0: GEMINI DEEP THINKING BRIEFING PLANNER ")
            print("="*40)
            briefing_text = args.briefing or config.get('Crawler', 'campaign_briefing', fallback='')
            if not briefing_text:
                print("Error: Please provide --briefing or set campaign_briefing in config.ini")
                if args.step == 'plan':
                    sys.exit(1)
            else:
                planner = BriefingPlanner(config_path=config_path)
                strategy = planner.plan_campaign(
                    campaign_briefing=briefing_text,
                    output_language=config.get('Analysis', 'output_language', fallback='Portuguese'),
                    region_code=config.get('Crawler', 'region_code', fallback='BR'),
                    additional_context=config.get('Analysis', 'additional_context', fallback='')
                )
                print("\n🧠 Strategy Generated:")
                print(f"Primary Search Term: {strategy.get('primary_search_term')}")
                print(f"Search Queries: {strategy.get('search_queries')}")
                print(f"Modifiers: {strategy.get('search_modifiers')}")
                print(f"Exclusions: {strategy.get('exclude_keywords')}")
                print(f"Objective Summary: {strategy.get('campaign_objective_summary')}")
                print(f"\nRationale:\n{strategy.get('strategic_reasoning')}\n")
                
                # Update config with strategy parameters
                if strategy.get('primary_search_term'):
                    config.set('Crawler', 'search_terms', strategy.get('primary_search_term'))
                if strategy.get('search_queries'):
                    config.set('Crawler', 'search_queries', "; ".join(strategy.get('search_queries')))
                if strategy.get('search_modifiers'):
                    config.set('Crawler', 'search_modifiers', ", ".join(strategy.get('search_modifiers')))
                if strategy.get('exclude_keywords'):
                    config.set('Crawler', 'exclude_keywords', ", ".join(strategy.get('exclude_keywords')))
                if strategy.get('recommended_region'):
                    config.set('Crawler', 'region_code', strategy.get('recommended_region'))
                if strategy.get('campaign_objective_summary'):
                    config.set('Crawler', 'campaign_briefing', strategy.get('campaign_objective_summary'))
                elif briefing_text:
                    config.set('Crawler', 'campaign_briefing', briefing_text)
                if strategy.get('additional_context_for_analysis'):
                    config.set('Analysis', 'additional_context', strategy.get('additional_context_for_analysis'))
                    
                with open(config_path, 'w', encoding='utf-8') as f:
                    config.write(f)
                print(f"Updated configuration written to {config_path}")

        if args.step in ['all', 'crawl']:
            print("\n" + "="*40)
            print(" STEP 1: CRAWLING VIDEOS ")
            print("="*40)
            crawler = YouTubeBrandCrawler(config_path=config_path)
            crawler.run_crawler()
            
            # Check if discovered_videos.csv is empty after crawling
            if os.path.exists(crawler.output_path):
                import pandas as pd
                try:
                    df_discovered = pd.read_csv(crawler.output_path)
                    if df_discovered.empty:
                        print(f"\n⚠️ [WARNING] Zero videos met the campaign relevance criteria in '{crawler.output_path}'.")
                        print("Pipeline exiting safely — skipping downstream comment extraction and analysis.")
                        if args.step == 'all':
                            return
                except Exception as e:
                    print(f"Warning: Could not read crawler output file '{crawler.output_path}': {e}")
            
        if args.step in ['all', 'comments']:
            print("\n" + "="*40)
            print(" STEP 3: EXTRACTING COMMENTS ")
            print("="*40)
            extractor = YouTubeCommentExtractor(config_path=config_path)
            if not os.path.exists(extractor.input_csv_path):
                print(f"⚠️ [WARNING] Discovered videos file '{extractor.input_csv_path}' not found. Skipping comment extraction.")
                if args.step == 'all':
                    return
            else:
                import pandas as pd
                try:
                    df_vids = pd.read_csv(extractor.input_csv_path)
                    if df_vids.empty:
                        print(f"⚠️ [WARNING] Discovered videos file '{extractor.input_csv_path}' is empty. Skipping comment extraction.")
                        if args.step == 'all':
                            return
                    else:
                        extractor.extract_comments()
                except Exception as e:
                    print(f"Error checking input videos: {e}")
                    extractor.extract_comments()


            
        if args.step in ['all', 'analyze']:
            print("\n" + "="*40)
            print(" STEP 4: RUNNING ANALYSIS PIPELINE ")
            print("="*40)
            pipeline = CachedAnalysisPipeline(config_path=config_path)
            pipeline.run_pipeline()
            
        # Parse requested output formats
        req_outputs_str = config.get('Analysis', 'requested_outputs', fallback='html,pdf,markdown')
        requested_outputs = [o.strip().lower() for o in req_outputs_str.split(',') if o.strip()]

        # Step 5: Slide & PDF Generation (Only if requested or step == 'slides')
        if args.step == 'slides' or (args.step == 'all' and ('pdf' in requested_outputs or 'slides' in requested_outputs)):
            print("\n" + "="*40)
            print(" STEP 5: GENERATING SLIDES & PDF PRESENTATION ")
            print("="*40)
            from generate_slides_final import run_slide_generation
            run_slide_generation(config_path=config_path)
        elif args.step == 'all':
            print("\n⏩ SKIPPING Slide & PDF Generation (saving processing time & Gemini tokens as requested).")

        # Step 6: Secure Backup to Google Drive
        if args.step in ['all', 'analyze', 'slides']:
            from drive_uploader import upload_run_outputs_to_drive
            upload_run_outputs_to_drive(config_path=config_path)
            
    except Exception as e:
        print(f"\nAn error occurred during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
