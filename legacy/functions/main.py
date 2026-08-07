import sys
import os
import re
import shutil
import datetime
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore, storage

# Add current directory to path so we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.crawler import YouTubeBrandCrawler
from src.downloader import VideoDownloader
from src.comment_extractor import YouTubeCommentExtractor
from src.pipeline import CachedAnalysisPipeline

initialize_app()

@https_fn.on_call(timeout_sec=540, memory=options.MemoryOption.GB_2)
def analyze_youtube_brand(req: https_fn.CallableRequest):
    """
    Triggers the YouTube sentiment analysis pipeline.
    """
    db = firestore.client()
    search_terms = req.data.get("search_terms")
    if not search_terms:
        return {"status": "error", "message": "Missing search_terms"}

    # Create a job record in Firestore
    job_ref = db.collection("analysis_jobs").document()
    job_id = job_ref.id
    job_ref.set({
        "status": "CRAWLING",
        "search_terms": search_terms,
        "created_at": firestore.SERVER_TIMESTAMP
    })

    # Set up temporary paths for Cloud Functions (/tmp is writable)
    base_tmp_dir = os.path.join("/tmp", job_id)
    os.makedirs(base_tmp_dir, exist_ok=True)
    
    config_dict = {
        "search_terms": search_terms,
        "search_modifiers": "review, unboxing, analysis",
        "exclude_keywords": "EUA, Americano, kings, League, jogo completo",
        "min_view_count": "5000",
        "sort_by": "relevance",
        "max_results": "3", # Reduced for Cloud Function duration limits
        "max_comments_per_video": "20",
        "base_output_dir": base_tmp_dir,
        "pro_model_name": "gemini-1.5-pro",
        "flash_model_name": "gemini-1.5-flash",
        "pro_prompt_template_path": "templates/prompts/topic_analysis.txt",
        "flash_prompt_template_path": "templates/prompts/topic_flash.txt",
        "batch_size": "3",
        "report_format": "html"
    }

    try:
        # 1. Crawl
        print(f"[{job_id}] Step 1: Crawling...")
        crawler = YouTubeBrandCrawler(config_dict=config_dict)
        crawler.run_crawler()
        
        # 2. Download
        print(f"[{job_id}] Step 2: Downloading...")
        job_ref.update({"status": "DOWNLOADING"})
        downloader = VideoDownloader(config_dict=config_dict)
        downloader.download_videos()

        # 3. Comments
        print(f"[{job_id}] Step 3: Extracting Comments...")
        job_ref.update({"status": "EXTRACTING_COMMENTS"})
        extractor = YouTubeCommentExtractor(config_dict=config_dict)
        extractor.extract_comments()

        # 4. Analyze
        print(f"[{job_id}] Step 4: Analyzing...")
        job_ref.update({"status": "ANALYZING"})
        pipeline = CachedAnalysisPipeline(config_dict=config_dict)
        report_path = pipeline.run_pipeline()

        if report_path and os.path.exists(report_path):
            # 5. Upload to Storage
            print(f"[{job_id}] Step 5: Uploading report...")
            bucket = storage.bucket()
            blob_name = f"reports/{job_id}/{os.path.basename(report_path)}"
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(report_path)
            
            # Make it publicly accessible (or generate a signed URL)
            # For simplicity, we'll use a signed URL valid for 7 days
            url = blob.generate_signed_url(datetime.timedelta(days=7), method='GET')

            job_ref.update({
                "status": "COMPLETED",
                "report_url": url,
                "completed_at": firestore.SERVER_TIMESTAMP
            })
            
            result_message = f"Analysis completed for {search_terms}."
        else:
            raise Exception("Failed to generate report file.")

        # Cleanup
        shutil.rmtree(base_tmp_dir)

        return {
            "status": "success",
            "message": result_message,
            "job_id": job_id,
            "report_url": url
        }

    except Exception as e:
        print(f"Error in analyze_youtube_brand: {e}")
        job_ref.update({"status": "FAILED", "error": str(e)})
        if os.path.exists(base_tmp_dir):
            shutil.rmtree(base_tmp_dir)
        return {"status": "error", "message": str(e)}
