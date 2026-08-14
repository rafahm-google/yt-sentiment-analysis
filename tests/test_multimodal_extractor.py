"""
Unit & Integration Tests for Video Multimodal Extractor Module (Chunk 2 Verification).
"""

import os
import sys
import shutil
import tempfile
import unittest
import pandas as pd

# Ensure src/ is on Python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from multimodal_extractor import (
    VideoMultimodalExtractor,
    SingleVideoMultimodalAnalysis,
    BrandAppearance,
)
from transcript_extractor import VideoTranscriptExtractor


class TestMultimodalExtractor(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_multimodal_")
        self.config_path = os.path.join(PROJECT_ROOT, "config.ini")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -----------------------------------------------------------------------
    # 1. ISO 8601 Duration Parser Tests
    # -----------------------------------------------------------------------
    def test_iso8601_duration_parsing(self):
        """Validate ISO 8601 duration parser across multiple standard and edge formats."""
        parser = VideoMultimodalExtractor._parse_iso8601_duration

        # Standard ISO 8601 durations
        self.assertEqual(parser("PT1H2M10S"), 3730)
        self.assertEqual(parser("PT14M32S"), 872)
        self.assertEqual(parser("PT45S"), 45)
        self.assertEqual(parser("PT1H"), 3600)
        self.assertEqual(parser("PT5M"), 300)
        self.assertEqual(parser("PT1H30S"), 3630)
        self.assertEqual(parser("P1DT2H"), 93600)
        self.assertEqual(parser("PT0S"), 0)

        # Colon-delimited time strings
        self.assertEqual(parser("14:32"), 872)
        self.assertEqual(parser("01:15:30"), 4530)
        self.assertEqual(parser("00:45"), 45)

        # Numeric / Integer inputs
        self.assertEqual(parser("120"), 120)
        self.assertEqual(parser(120), 120)
        self.assertEqual(parser(0), 0)

        # Edge cases / Malformed inputs (should safely return 0 without raising exceptions)
        self.assertEqual(parser(""), 0)
        self.assertEqual(parser(None), 0)
        self.assertEqual(parser("invalid_duration_string"), 0)
        self.assertEqual(parser("PT"), 0)
        print("PASS: test_iso8601_duration_parsing")

    # -----------------------------------------------------------------------
    # 2. Pydantic Schema Parsing & Serialization Tests
    # -----------------------------------------------------------------------
    def test_pydantic_schemas_and_validation(self):
        """Validate Pydantic schema validation, defaults, and json round-tripping."""
        appearance = BrandAppearance(
            brand_name="Leapmotor",
            modality="both",
            timestamps=["01:15", "04:30"],
            sentiment="positive",
            context_summary="Visual close-up of C10 badge and spoken praise for cabin NVH.",
            prominence="high",
            appearance_type="Visual Logo & Spoken Review",
        )

        self.assertEqual(appearance.brand_name, "Leapmotor")
        self.assertEqual(appearance.modality, "both")
        self.assertEqual(len(appearance.timestamps), 2)
        self.assertEqual(appearance.sentiment, "positive")

        analysis = SingleVideoMultimodalAnalysis(
            video_id="3KtWfp0UopM",
            video_title="Novo Leapmotor C10 no Brasil: Vale a Pena?",
            channel_name="AutoEsporte",
            summary_of_content="Comprehensive road test and feature breakdown of Leapmotor C10 vs BYD Song Plus.",
            creator_stance="Brand Promoter",
            brand_appearances=[appearance],
            features_valued_most=["Chassis calibration", "Interior finish", "Range efficiency"],
            features_criticized_or_irrelevant=["Infotainment translation quirks"],
            brand_co_occurrences=["BYD", "GWM"],
            investment_whitespace_signals=["Charging network partnerships needed"],
            duration_seconds=872,
            target_brand_present=True,
            competitor_brands_present=["BYD", "GWM"],
            spoken_key_claims=["Autonomia real de 420km", "Excelente acabamento interno"],
        )

        # Validate JSON serialization and reconstruction
        json_str = analysis.model_dump_json()
        self.assertIn("3KtWfp0UopM", json_str)
        self.assertIn("Leapmotor", json_str)

        reconstructed = SingleVideoMultimodalAnalysis.model_validate_json(json_str)
        self.assertEqual(reconstructed.video_id, "3KtWfp0UopM")
        self.assertEqual(len(reconstructed.brand_appearances), 1)
        self.assertEqual(reconstructed.brand_appearances[0].brand_name, "Leapmotor")
        self.assertEqual(len(reconstructed.features_valued_most), 3)
        self.assertEqual(reconstructed.duration_seconds, 872)
        print("PASS: test_pydantic_schemas_and_validation")

    # -----------------------------------------------------------------------
    # 3. Fallback Parsing & Unresolvable Video Tests
    # -----------------------------------------------------------------------
    def test_fallback_and_resilient_parser(self):
        """Validate parser extracts JSON wrapped in markdown code blocks and handles malformed text."""
        extractor = VideoMultimodalExtractor(
            config_path=self.config_path,
            output_dir=self.temp_dir,
            target_brand="Leapmotor",
            competitors=["BYD", "GWM"],
        )

        dummy_meta = {
            "video_id": "dummy_vid_001",
            "title": "Leapmotor C10 SUV Elétrico Test Drive",
            "channel": "Canal Automotivo",
            "duration_seconds": 600,
            "description": "Avaliamos o novo SUV elétrico da Leapmotor comparado ao BYD Song.",
        }

        # Test markdown-wrapped JSON parsing
        raw_markdown_json = """```json
{
  "video_id": "dummy_vid_001",
  "video_title": "Leapmotor C10 SUV Elétrico Test Drive",
  "channel_name": "Canal Automotivo",
  "summary_of_content": "Teste dinâmico completo do Leapmotor C10.",
  "creator_stance": "Brand Promoter",
  "brand_appearances": [
    {
      "brand_name": "Leapmotor",
      "modality": "visual",
      "timestamps": ["02:10"],
      "sentiment": "positive",
      "context_summary": "Logo em destaque",
      "prominence": "high"
    }
  ],
  "features_valued_most": ["Suspensão", "Conforto"],
  "features_criticized_or_irrelevant": [],
  "brand_co_occurrences": ["BYD"],
  "investment_whitespace_signals": ["Pós-venda"],
  "duration_seconds": 600
}
```"""
        parsed = extractor._parse_analysis_response(raw_markdown_json, dummy_meta)
        self.assertEqual(parsed.video_id, "dummy_vid_001")
        self.assertEqual(len(parsed.brand_appearances), 1)
        self.assertTrue(parsed.target_brand_present)
        self.assertEqual(parsed.features_valued_most, ["Suspensão", "Conforto"])

        # Test safe fallback creation on empty / malformed responses
        fallback = extractor._create_fallback_analysis(dummy_meta, status="TEST_FALLBACK")
        self.assertEqual(fallback.video_id, "dummy_vid_001")
        self.assertTrue(fallback.target_brand_present)
        self.assertEqual(fallback.extraction_status, "TEST_FALLBACK")
        print("PASS: test_fallback_and_resilient_parser")

    # -----------------------------------------------------------------------
    # 4. Duration Limit Constraint Test (> 30 mins)
    # -----------------------------------------------------------------------
    def test_duration_limit_constraint(self):
        """Verify that videos longer than 30 minutes trigger duration constraint handling."""
        extractor = VideoMultimodalExtractor(
            config_path=self.config_path,
            output_dir=self.temp_dir,
            target_brand="Leapmotor",
            competitors=["BYD"],
        )

        long_video = {
            "video_id": "long_vid_45m",
            "title": "Live 45 minutos sobre Carros Elétricos e Leapmotor C10",
            "channel": "Live Channel",
            "duration": "PT45M00S", # 2700s > 1800s
            "description": "Debate ao vivo sobre carros elétricos no Brasil.",
        }

        analysis = extractor.analyze_single_video(long_video)
        self.assertEqual(analysis.video_id, "long_vid_45m")
        self.assertEqual(analysis.duration_seconds, 2700)
        self.assertIn(analysis.extraction_status, ["DURATION_EXCEEDED", "METADATA_FALLBACK"])
        print("PASS: test_duration_limit_constraint")

    # -----------------------------------------------------------------------
    # 5. Parallel Processing & DataFrame Generation Test
    # -----------------------------------------------------------------------
    def test_process_videos_df_pipeline(self):
        """Verify process_videos_df produces structured DataFrames and persists CSV outputs."""
        extractor = VideoMultimodalExtractor(
            config_path=self.config_path,
            output_dir=self.temp_dir,
            target_brand="Leapmotor",
            competitors=["BYD", "GWM"],
        )

        # Create mock DataFrame of discovered videos
        test_df = pd.DataFrame([
            {
                "video_id": "test_vid_1",
                "title": "Leapmotor C10 vs BYD Song Plus Comparativo",
                "channel": "Auto Testes",
                "views": 25000,
                "likes": 1200,
                "comments": 95,
                "duration": "PT12M30S",
                "description": "Comparativo detalhado entre os dois SUVs elétricos.",
                "url": "https://www.youtube.com/watch?v=test_vid_1",
            },
            {
                "video_id": "test_vid_2",
                "title": "Melhores Carros Elétricos de 2024 no Brasil",
                "channel": "Guia Automotivo",
                "views": 50000,
                "likes": 3100,
                "comments": 210,
                "duration": "PT08M15S",
                "description": "Ranking dos melhores veículos elétricos do ano.",
                "url": "https://www.youtube.com/watch?v=test_vid_2",
            }
        ])

        multimodal_df, appearances_df = extractor.process_videos_df(test_df, max_videos=2)

        self.assertIsInstance(multimodal_df, pd.DataFrame)
        self.assertIsInstance(appearances_df, pd.DataFrame)
        self.assertEqual(len(multimodal_df), 2)

        # Verify summary DataFrame columns
        expected_cols = [
            "video_id", "video_title", "channel_name", "duration_seconds",
            "summary_of_content", "creator_stance", "target_brand_present",
            "features_valued_most", "features_criticized_or_irrelevant",
            "brand_co_occurrences", "investment_whitespace_signals",
            "extraction_status", "transcript_text", "has_transcript"
        ]
        for col in expected_cols:
            self.assertIn(col, multimodal_df.columns, f"Missing column {col} in multimodal_df")

        # Verify output CSV file generation
        saved_files = os.listdir(self.temp_dir)
        self.assertTrue(any("multimodal_analysis.csv" in f for f in saved_files))
        self.assertTrue(any("brand_appearances_timeline.csv" in f for f in saved_files))
        print("PASS: test_process_videos_df_pipeline")

    # -----------------------------------------------------------------------
    # 6. Backward Compatibility Adapter Test
    # -----------------------------------------------------------------------
    def test_transcript_extractor_backward_compatibility(self):
        """Verify VideoTranscriptExtractor acts as backward-compatible drop-in adapter."""
        legacy_extractor = VideoTranscriptExtractor(
            output_dir=self.temp_dir,
            config_path=self.config_path,
            target_brand="Leapmotor",
        )

        test_df = pd.DataFrame([
            {
                "video_id": "legacy_vid_01",
                "title": "Avaliação Leapmotor C10",
                "channel": "Canal Carros",
                "duration": "PT10M00S",
                "description": "Review completo.",
            }
        ])

        # Legacy caller expecting a single DataFrame returned
        res_df = legacy_extractor.process_videos_df(test_df, max_videos=1)
        self.assertIsInstance(res_df, pd.DataFrame)
        self.assertEqual(len(res_df), 1)
        self.assertIn("transcript_text", res_df.columns)
        self.assertTrue(res_df.iloc[0]["has_transcript"])

        # Legacy single fetch method
        single_res = legacy_extractor._fetch_single("vid123", "Title", "Channel")
        self.assertEqual(single_res["video_id"], "vid123")
        self.assertTrue(single_res["has_transcript"])
        print("PASS: test_transcript_extractor_backward_compatibility")


if __name__ == "__main__":
    unittest.main()
