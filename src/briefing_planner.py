import os
import json
import configparser
import time
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

from pydantic import BaseModel, Field
from typing import List, Optional

class CampaignStrategySchema(BaseModel):
    primary_search_term: str = Field(description="1-3 word primary term representing the brand or topic")
    strategic_reasoning: str = Field(description="Detailed explanation of the search strategy and deep thinking")
    search_queries: List[str] = Field(description="3 to 6 targeted YouTube search query strings with exact-quoted entities")
    search_modifiers: List[str] = Field(description="Search modifier keywords like review, unboxing, compras")
    exclude_keywords: List[str] = Field(description="Comprehensive negative keywords across culinary, infant formula, stock, repair, and spam zones")
    recommended_region: str = Field(default="BR", description="2-letter ISO region code")
    recommended_video_type: str = Field(default="both", description="videos, shorts, or both")
    recommended_sort_by: str = Field(default="relevance", description="relevance, viewCount, or date")
    recommended_channels: List[str] = Field(default_factory=list, description="Optional high-signal channel names")
    additional_context_for_analysis: str = Field(description="Synthesized background context for downstream analysis")
    campaign_objective_summary: str = Field(default="", description="Concise 2-sentence objective summary for semantic filtering")
    model_config = {"extra": "ignore"}

class BriefingPlanner:
    """
    Leverages Gemini deep thinking to translate high-level campaign briefings
    or broad research topics into optimized YouTube API search strategies.
    """
    def __init__(self, config_path=None, model_name=None, fallback_model_name=None):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if config_path is None:
            config_path = os.path.join(self.project_root, 'config.ini')
        
        self.config_path = config_path
        self.custom_model_name = model_name
        self.custom_fallback_model_name = fallback_model_name
        self._load_environment_variables()
        self._load_configuration()
        if self.custom_model_name:
            self.pro_model_name = self.custom_model_name
        if self.custom_fallback_model_name:
            self.fallback_model_name = self.custom_fallback_model_name
        self.client = genai.Client(api_key=self.google_api_key)

    def _load_environment_variables(self):
        load_dotenv(os.path.join(self.project_root, '.env'))
        self.google_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.google_api_key:
            print("Warning: Neither GEMINI_API_KEY nor YOUTUBE_API_KEY found in env.")

    def _load_configuration(self):
        config = configparser.ConfigParser(interpolation=None)
        if os.path.exists(self.config_path):
            config.read(self.config_path)
            
        self.pro_model_name = config.get('Analysis', 'briefing_model_name', fallback='gemini-3.7-flash')
        self.flash_model_name = config.get('Analysis', 'flash_model_name', fallback='gemini-3.7-flash')
        self.fallback_model_name = config.get('Analysis', 'fallback_model_name', fallback='gemini-3.6-flash')
        
        prompt_rel_path = config.get('Analysis', 'briefing_prompt_template_path', fallback='templates/prompts/briefing_planner.txt')
        self.prompt_path = os.path.join(self.project_root, prompt_rel_path)

    def plan_campaign(self, campaign_briefing, output_language="Portuguese", region_code="BR", additional_context="", enable_google_search=True):
        """
        Takes a campaign briefing and returns a structured search strategy for YouTube API.
        """
        if not campaign_briefing or not campaign_briefing.strip():
            raise ValueError("Campaign briefing cannot be empty.")

        # Read prompt template
        if os.path.exists(self.prompt_path):
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        else:
            # Fallback inline prompt template
            prompt_template = """
You are a Senior Digital Marketing Strategist and YouTube Search API Expert.
Analyze the following Campaign Briefing and generate an optimized YouTube search strategy.

## CAMPAIGN BRIEFING:
{{CAMPAIGN_BRIEFING}}

## CONTEXT:
Language: {{OUTPUT_LANGUAGE}}
Region: {{REGION_CODE}}
Additional Context: {{ADDITIONAL_CONTEXT}}

## 4-STEP PROCESS:
1. Entity Grounding: Discover official brand/storefront names.
2. Exact-Match Quoted Queries: 3-6 queries enclosing core entities in quotes ('"[Entity]" idiom').
3. 5-Zone Negative Taxonomy: Exclude culinary, infant formula, stock news, repairs, and marketplace spam.
4. Campaign Objective Summary: 2-sentence objective summary for semantic filtering.
"""

        # Replace placeholders
        prompt = prompt_template.replace("{{CAMPAIGN_BRIEFING}}", campaign_briefing.strip())
        prompt = prompt.replace("{{OUTPUT_LANGUAGE}}", output_language)
        prompt = prompt.replace("{{REGION_CODE}}", region_code)
        prompt = prompt.replace("{{ADDITIONAL_CONTEXT}}", additional_context or "None provided")

        print(f"\n🧠 Initiating Gemini Deep Thinking for Campaign Briefing...")
        print(f"Primary Model: {self.pro_model_name}")

        # Attempt call with retries and fallback
        response_text = self._call_gemini_json(prompt, self.pro_model_name, self.fallback_model_name, enable_google_search=enable_google_search)
        
        if not response_text:
            raise RuntimeError("Failed to get search strategy from Gemini API.")

        # Parse JSON response
        strategy = self._parse_json_response(response_text)
        return strategy

    def _call_gemini_json(self, prompt, model_name, fallback_model_name=None, enable_google_search=True):
        """Calls Gemini API with JSON response mime type and schema, optional Search Grounding, 503 retries, and model fallback."""
        kwargs = {
            "response_mime_type": "application/json",
            "response_schema": CampaignStrategySchema
        }
        if enable_google_search:
            kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
            
        config = types.GenerateContentConfig(**kwargs)
        
        for attempt in range(3):
            try:
                print(f"Calling Gemini API ({model_name}) - Attempt {attempt + 1}...")
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e) or "OVERLOADED" in str(e):
                    print(f"Model {model_name} overloaded (503). Retrying in 4 seconds...")
                    time.sleep(4)
                else:
                    print(f"Error calling model {model_name}: {e}")
                    break
        
        if fallback_model_name:
            print(f"Primary model {model_name} failed. Attempting fallback model {fallback_model_name}...")
            try:
                response = self.client.models.generate_content(
                    model=fallback_model_name,
                    contents=prompt,
                    config=config
                )
                if response and response.text:
                    print(f"SUCCESS: Received response from fallback model {fallback_model_name}.")
                    return response.text
            except Exception as e_fb:
                print(f"Fallback model {fallback_model_name} also failed: {e_fb}")

        return None

    def _parse_json_response(self, text):
        """Clean markdown wrapping if present and parse JSON with fallbacks."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}. Attempting auto-fix...")
            # Try appending missing closing brace or bracket
            fixed_text = cleaned
            if not fixed_text.endswith("}"):
                fixed_text += '"}' if not fixed_text.endswith('"') else '}'
            try:
                parsed = json.loads(fixed_text)
            except Exception:
                json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                else:
                    raise e

        # Ensure default keys exist and fallback campaign_objective_summary
        additional_context = parsed.get("additional_context_for_analysis", "")
        objective_summary = parsed.get("campaign_objective_summary", "").strip()
        if not objective_summary:
            objective_summary = additional_context

        strategy = {
            "primary_search_term": parsed.get("primary_search_term", ""),
            "strategic_reasoning": parsed.get("strategic_reasoning", ""),
            "search_queries": parsed.get("search_queries", []),
            "search_modifiers": parsed.get("search_modifiers", []),
            "exclude_keywords": parsed.get("exclude_keywords", []),
            "recommended_region": parsed.get("recommended_region", "BR"),
            "recommended_video_type": parsed.get("recommended_video_type", "both"),
            "recommended_sort_by": parsed.get("recommended_sort_by", "relevance"),
            "recommended_channels": parsed.get("recommended_channels", []),
            "additional_context_for_analysis": additional_context,
            "campaign_objective_summary": objective_summary
        }
        return strategy

if __name__ == "__main__":
    planner = BriefingPlanner()
    test_briefing = "Analisar o canal D2C Empório Nestlé vs Marketplaces no Brasil."
    result = planner.plan_campaign(test_briefing)
    print("\n--- GENERATED STRATEGY ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))
