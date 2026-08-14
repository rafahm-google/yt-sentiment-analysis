"""
Unit & Integration Tests for GenAI Client Factory (Chunk 1 Verification).
"""

import os
import sys
import unittest

# Ensure src/ is on Python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from client_factory import (
    create_genai_client,
    get_multimodal_config,
    get_model_names,
    generate_content_with_retry,
)


class TestClientFactory(unittest.TestCase):

    def test_multimodal_config_parsing(self):
        """Verify config.ini [Multimodal] section parsing."""
        config_path = os.path.join(PROJECT_ROOT, "config.ini")
        cfg = get_multimodal_config(config_path)

        self.assertEqual(cfg["max_workers"], 4)
        self.assertEqual(cfg["worker_delay_seconds"], 1.5)
        self.assertEqual(cfg["max_video_duration_seconds"], 1800)
        self.assertTrue(cfg["enable_visual_analysis"])
        self.assertTrue(cfg["use_vertex_ai"])
        self.assertEqual(cfg["vertex_location"], "us-central1")
        print("PASS: test_multimodal_config_parsing")

    def test_model_names_parsing(self):
        """Verify config.ini [Analysis] model names."""
        config_path = os.path.join(PROJECT_ROOT, "config.ini")
        models = get_model_names(config_path)

        self.assertEqual(models["pro_model_name"], "gemini-3.7-flash")
        self.assertEqual(models["flash_model_name"], "gemini-3.7-flash")
        print("PASS: test_model_names_parsing")

    def test_client_initialization_and_gemini_query(self):
        """Verify client initializes and successfully queries gemini-3.7-flash."""
        config_path = os.path.join(PROJECT_ROOT, "config.ini")
        client = create_genai_client(config_path=config_path)
        self.assertIsNotNone(client, "Client should not be None")

        models = get_model_names(config_path)
        target_model = models["flash_model_name"]
        self.assertEqual(target_model, "gemini-3.7-flash")

        print(f"Querying model '{target_model}' for live responsiveness...")
        response = generate_content_with_retry(
            client=client,
            model=target_model,
            contents="Respond with 'CHUNK1_VERIFIED' and explain in 1 short sentence why gemini-3.7-flash is great for video analysis.",
            max_retries=3,
            retry_delay_sec=2.0,
        )

        self.assertIsNotNone(response.text)
        self.assertIn("CHUNK1_VERIFIED", response.text)
        print(f"SUCCESS: Model response received:\n{response.text.strip()}")

    def test_vertex_ai_mode_initialization(self):
        """Verify Vertex AI client initializes with explicit project and location."""
        project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_NUMBER")
        if not project:
            self.skipTest("No GCP project configured in environment.")

        client = create_genai_client(use_vertex=True, project_id=project, location="us-central1")
        self.assertIsNotNone(client)
        print("PASS: test_vertex_ai_mode_initialization")


if __name__ == "__main__":
    unittest.main()
