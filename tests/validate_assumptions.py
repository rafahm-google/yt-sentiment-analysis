"""
Phase 0 Spike: Validate GenAI Client, Model Ingestion, and Pydantic Schema Parsing.
Run: python tests/validate_assumptions.py
"""
import os
import sys
import time
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from client_factory import create_genai_client, get_model_names, generate_content_with_retry
from google.genai import types

load_dotenv()


class BrandAppearance(BaseModel):
    brand_name: str
    appearance_type: str
    timestamp: str
    context: str
    sentiment: str


class SingleVideoMultimodalAnalysis(BaseModel):
    video_id: str
    video_title: str
    channel_name: str
    summary_of_content: str
    target_brand_present: bool
    competitor_brands_present: List[str]
    brand_appearances: List[BrandAppearance]
    spoken_key_claims: List[str]
    creator_editorial_stance: str
    engagement_driver_assessment: str
    extraction_status: str = "SUCCESS"


def test_schema_and_model_responsiveness():
    print("--- [Test 1] Testing Client Factory & Structured Output Generation ---")
    config_path = os.path.join(PROJECT_ROOT, "config.ini")
    client = create_genai_client(config_path=config_path)
    models = get_model_names(config_path)
    model_name = models["flash_model_name"]

    prompt = (
        "Simulate multimodal video analysis extraction for a YouTube video about Leapmotor C10 vs BYD Song Plus. "
        "Return structured JSON matching the provided schema."
    )

    start_time = time.time()
    try:
        response = generate_content_with_retry(
            client=client,
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=SingleVideoMultimodalAnalysis,
            ),
            fallback_model=models["fallback_model_name"],
            max_retries=3,
            retry_delay_sec=2.0,
        )
        elapsed = time.time() - start_time
        print(f"SUCCESS: Model response generated in {elapsed:.2f}s!")
        print(f"Raw Response snippet: {response.text[:300]}...")

        parsed = SingleVideoMultimodalAnalysis.model_validate_json(response.text)
        print(f"SUCCESS: Pydantic Validation Passed! Extracted {len(parsed.brand_appearances)} brand appearances.")
        print(f"Creator Stance: {parsed.creator_editorial_stance}")
        print(f"Target Brand Present: {parsed.target_brand_present}")
        return True
    except Exception as e:
        print(f"FAILED: Structured generation error: {e}")
        return False


if __name__ == "__main__":
    success = test_schema_and_model_responsiveness()
    sys.exit(0 if success else 1)
