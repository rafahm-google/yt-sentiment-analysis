"""
Video Multimodal Extractor Module (Stage 1 Engine).

Extracts 360-degree brand presence intelligence (spoken dialogue, on-screen logos,
product placements, creator stance, features valued/criticized, and investment whitespace)
from YouTube videos using Gemini 3.7 Flash multimodal streaming on Vertex AI.
"""

import os
import re
import time
import json
import logging
import configparser
from typing import List, Optional, Tuple, Dict, Any, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from pydantic import BaseModel, Field
from tqdm import tqdm
from google.genai import types

from client_factory import (
    create_genai_client,
    get_multimodal_config,
    get_model_names,
    generate_content_with_retry,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Schemas for Structured Multimodal Video Intelligence
# ---------------------------------------------------------------------------

class BrandAppearance(BaseModel):
    """Structured record of a single brand appearance in video."""
    brand_name: str = Field(description="Target brand or competitor name detected in the video")
    modality: str = Field(default="spoken", description="Modality of appearance: 'spoken', 'visual', or 'both'")
    timestamps: List[str] = Field(default_factory=list, description="List of timestamps formatted as MM:SS where appearance occurs")
    sentiment: str = Field(default="neutral", description="Sentiment associated with appearance: 'positive', 'negative', or 'neutral'")
    context_summary: str = Field(default="", description="Context summary, exact quote, or visual scene description")
    prominence: str = Field(default="medium", description="Prominence level: 'high', 'medium', or 'low'")
    appearance_type: Optional[str] = Field(default=None, description="Visual Logo, On-Screen Product, Spoken Mention, Lower Third, UI Banner")
    timestamp: Optional[str] = Field(default=None, description="Primary timestamp MM:SS")
    context: Optional[str] = Field(default=None, description="Context snippet")


class SingleVideoMultimodalAnalysis(BaseModel):
    """Comprehensive multimodal analysis schema for a single YouTube video."""
    video_id: str = Field(default="", description="YouTube 11-character video ID")
    video_title: str = Field(default="", description="Title of the YouTube video")
    channel_name: str = Field(default="", description="Name of the channel / creator")
    summary_of_content: str = Field(default="", description="Summary of narrative and topics covered in video")
    creator_stance: str = Field(
        default="Neutral Category Creator",
        description="Creator stance: 'Brand Promoter', 'Competitor Aligned', 'Neutral Category Creator', 'Critical'"
    )
    brand_appearances: List[BrandAppearance] = Field(
        default_factory=list,
        description="All detected visual and spoken brand appearances"
    )
    features_valued_most: List[str] = Field(
        default_factory=list,
        description="Features/benefits most praised or valued by creator/audience"
    )
    features_criticized_or_irrelevant: List[str] = Field(
        default_factory=list,
        description="Features criticized, pain points, or considered irrelevant"
    )
    brand_co_occurrences: List[str] = Field(
        default_factory=list,
        description="Competitor brands co-occurring or compared in the video"
    )
    investment_whitespace_signals: List[str] = Field(
        default_factory=list,
        description="Signals of unmet customer needs or whitespace investment opportunities"
    )
    duration_seconds: int = Field(default=0, description="Video duration in seconds")
    target_brand_present: bool = Field(default=False, description="Whether the target brand was present")
    competitor_brands_present: List[str] = Field(default_factory=list, description="List of competitor brands detected")
    spoken_key_claims: List[str] = Field(default_factory=list, description="Key spoken claims or quotes from the video")
    creator_editorial_stance: Optional[str] = Field(default=None, description="Alias for creator_stance")
    engagement_driver_assessment: Optional[str] = Field(default=None, description="Assessment of engagement drivers for this video")
    extraction_status: str = Field(default="SUCCESS", description="SUCCESS, METADATA_FALLBACK, or DURATION_EXCEEDED")


# ---------------------------------------------------------------------------
# Video Multimodal Extractor Class (Stage 1 Engine)
# ---------------------------------------------------------------------------

class VideoMultimodalExtractor:
    """
    Direct multimodal video extractor leveraging Gemini 3.7 Flash on Vertex AI.
    Processes video visual frames and spoken audio in parallel to extract rich brand intelligence.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        output_dir: Optional[str] = None,
        target_brand: Optional[str] = None,
        competitors: Optional[List[str]] = None,
        category_theme: Optional[str] = None,
    ) -> None:
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Resolve config path
        if config_path:
            self.config_path = config_path if os.path.isabs(config_path) else os.path.join(self.project_root, config_path)
        else:
            default_cfg = os.path.join(self.project_root, "config.ini")
            self.config_path = default_cfg if os.path.exists(default_cfg) else "config.ini"

        # Load configuration
        self._load_config(target_brand, competitors, category_theme, output_dir)

        # Initialize GenAI Client
        logger.info("Initializing Google GenAI Client for VideoMultimodalExtractor...")
        self.client = create_genai_client(config_path=self.config_path)
        logger.info("SUCCESS: VideoMultimodalExtractor GenAI Client ready.")

    def _load_config(
        self,
        target_brand: Optional[str],
        competitors: Optional[List[str]],
        category_theme: Optional[str],
        output_dir: Optional[str],
    ) -> None:
        """Loads configuration from config.ini and overrides with explicit parameters."""
        config = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            config.read(self.config_path)

        # Target Brand & Competitors
        self.target_brand = target_brand or config.get("Target", "target_brand", fallback="Target Brand")
        if competitors is not None:
            self.competitors = competitors
        else:
            comp_str = config.get("Target", "competitors", fallback="")
            self.competitors = [c.strip() for c in comp_str.split(",") if c.strip()]

        # Category Theme & Run ID
        self.category_theme = category_theme or config.get("Category", "category_theme", fallback="Category Strategy")
        safe_brand = re.sub(r"\W+", "_", self.target_brand.strip())
        safe_theme = re.sub(r"\W+", "_", self.category_theme.strip())
        default_run_id = f"{safe_brand}_{safe_theme}" if safe_brand else "multimodal_run"
        self.run_id = config.get("General", "run_id", fallback=default_run_id)

        # Multimodal Parameters
        multimodal_cfg = get_multimodal_config(self.config_path)
        self.max_workers = multimodal_cfg.get("max_workers", 4)
        self.worker_delay_seconds = multimodal_cfg.get("worker_delay_seconds", 1.5)
        self.max_video_duration_seconds = multimodal_cfg.get("max_video_duration_seconds", 1800)
        self.enable_visual = multimodal_cfg.get("enable_visual_analysis", True)
        self.use_vertex = multimodal_cfg.get("use_vertex_ai", True)
        self.vertex_location = multimodal_cfg.get("vertex_location", "us-central1")

        # Models
        models = get_model_names(self.config_path)
        self.model_name = models.get("flash_model_name", "gemini-3.7-flash")
        self.fallback_model_name = models.get("fallback_model_name", "gemini-3.6-flash")

        # Output Directory
        if output_dir:
            self.output_dir = output_dir
        else:
            self.output_dir = os.path.join(self.project_root, "outputs", self.run_id)

    @staticmethod
    def _parse_iso8601_duration(duration_str: Any) -> int:
        """
        Parses ISO 8601 duration strings (e.g. 'PT14M32S', 'PT1H2M10S', 'PT45S', 'PT1H', 'P1DT2H')
        or standard time formats ('MM:SS', 'HH:MM:SS', integer seconds) into total seconds.
        Returns 0 for invalid, empty, or None values without raising exceptions.
        """
        if duration_str is None or pd.isna(duration_str):
            return 0
        if isinstance(duration_str, (int, float)):
            return max(0, int(duration_str))

        val = str(duration_str).strip()
        if not val:
            return 0

        # Pure integer string (e.g. "120")
        if val.isdigit():
            return int(val)

        # Standard colon-delimited format (MM:SS or HH:MM:SS)
        time_parts = val.split(":")
        if len(time_parts) in (2, 3) and all(p.strip().isdigit() for p in time_parts):
            if len(time_parts) == 2:
                return int(time_parts[0]) * 60 + int(time_parts[1])
            elif len(time_parts) == 3:
                return int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])

        # Strict ISO 8601 Duration pattern
        pattern = re.compile(
            r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
            re.IGNORECASE,
        )
        match = pattern.match(val)
        if match:
            parts = match.groupdict()
            days = int(parts.get("days") or 0)
            hours = int(parts.get("hours") or 0)
            minutes = int(parts.get("minutes") or 0)
            seconds = int(parts.get("seconds") or 0)
            return days * 86400 + hours * 3600 + minutes * 60 + seconds

        # Permissive regex fallback for partial ISO components
        days_m = re.search(r"(\d+)\s*D", val, re.I)
        hours_m = re.search(r"(\d+)\s*H", val, re.I)
        mins_m = re.search(r"(\d+)\s*M", val, re.I)
        secs_m = re.search(r"(\d+)\s*S", val, re.I)

        if any([days_m, hours_m, mins_m, secs_m]):
            days = int(days_m.group(1)) if days_m else 0
            hours = int(hours_m.group(1)) if hours_m else 0
            minutes = int(mins_m.group(1)) if mins_m else 0
            seconds = int(secs_m.group(1)) if secs_m else 0
            return days * 86400 + hours * 3600 + minutes * 60 + seconds

        return 0

    def _construct_multimodal_prompt(
        self,
        video_meta: Dict[str, Any],
        target_brand: str,
        competitors: List[str],
        category_theme: str,
        metadata_only: bool = False,
    ) -> str:
        """Builds a comprehensive prompt for Gemini multimodal inspection."""
        comps_formatted = ", ".join(competitors) if competitors else "None specified"
        title = video_meta.get("title", "")
        channel = video_meta.get("channel", "")
        desc = video_meta.get("description", "")
        duration = video_meta.get("duration_seconds", 0)

        prompt = f"""You are an elite marketing intelligence analyst and multimodal brand auditor.
Analyze the provided YouTube video for brand exposure, creator stance, feature sentiment, and whitespace opportunities.

### Context & Target Entity:
- **Target Brand**: {target_brand}
- **Competitors**: {comps_formatted}
- **Category / Theme**: {category_theme}

### Video Metadata:
- **Title**: {title}
- **Channel / Creator**: {channel}
- **Duration**: {duration} seconds (~{duration // 60} mins)
- **Description**: {desc[:400]}

### Multimodal Analysis Instructions:
1. **Visual & Audio Inspection**:
   - Detect all visual appearances: on-screen car/product shots, badges, logos, lower-third overlays, UI banners, physical product placement.
   - Detect all spoken dialogue mentions of {target_brand} and competitors ({comps_formatted}).
   - Note exact timestamps (MM:SS), modality ('visual', 'spoken', or 'both'), sentiment ('positive', 'neutral', or 'negative'), and context.

2. **Perception & Decision Drivers**:
   - **Features Valued Most**: What specific features, qualities, or aspects does the creator/audience praise or value most?
   - **Features Criticized / Irrelevant**: What pain points, complaints, drawbacks, or irrelevant features are highlighted?

3. **Competitive Dynamics & Whitespace**:
   - **Brand Co-occurrences**: Which competitor brands are shown or discussed in comparison with {target_brand}?
   - **Investment Whitespace Signals**: What unmet customer needs, gaps, or proactive investment opportunities for {target_brand} are visible in this video?

4. **Creator Stance**:
   - Classify creator editorial posture: 'Brand Promoter' ({target_brand}), 'Competitor Aligned', 'Neutral Category Creator', or 'Critical'.

5. **Summary**:
   - Provide a concise 2-3 sentence overview of the video's narrative and verdict.

Return ONLY valid JSON matching the SingleVideoMultimodalAnalysis schema.
"""
        if metadata_only:
            prompt += "\nNote: Analyze based strictly on the provided video metadata (title, description, channel, stats)."

        return prompt

    def _create_fallback_analysis(
        self,
        video_meta: Dict[str, Any],
        summary: str = "",
        status: str = "METADATA_FALLBACK",
    ) -> SingleVideoMultimodalAnalysis:
        """Builds a safe, complete SingleVideoMultimodalAnalysis instance on extraction failure."""
        video_id = video_meta.get("video_id", "")
        title = video_meta.get("title", "")
        channel = video_meta.get("channel", "")
        duration_sec = video_meta.get("duration_seconds", 0)
        desc = video_meta.get("description", "")

        all_text = f"{title} {desc}".lower()
        target_present = self.target_brand.lower() in all_text if self.target_brand else False
        comps_present = [c for c in self.competitors if c.lower() in all_text]

        appearances = []
        if target_present:
            appearances.append(
                BrandAppearance(
                    brand_name=self.target_brand,
                    modality="spoken",
                    timestamps=["00:00"],
                    sentiment="neutral",
                    context_summary=f"Mencionado nos metadados do vídeo ({title[:60]})",
                    prominence="medium",
                    appearance_type="Metadata Mention",
                )
            )

        for comp in comps_present:
            appearances.append(
                BrandAppearance(
                    brand_name=comp,
                    modality="spoken",
                    timestamps=["00:00"],
                    sentiment="neutral",
                    context_summary=f"Concorrente identificado no título/descrição",
                    prominence="low",
                    appearance_type="Metadata Mention",
                )
            )

        creator_stance = "Neutral Category Creator"
        if target_present and not comps_present:
            creator_stance = f"Brand Promoter ({self.target_brand})"
        elif comps_present:
            creator_stance = f"Competitor Aligned ({', '.join(comps_present)})"

        return SingleVideoMultimodalAnalysis(
            video_id=video_id,
            video_title=title,
            channel_name=channel,
            summary_of_content=summary or (desc[:200] if desc else "Análise baseada em metadados do vídeo."),
            creator_stance=creator_stance,
            creator_editorial_stance=creator_stance,
            brand_appearances=appearances,
            features_valued_most=[],
            features_criticized_or_irrelevant=[],
            brand_co_occurrences=comps_present,
            investment_whitespace_signals=[],
            duration_seconds=duration_sec,
            target_brand_present=target_present,
            competitor_brands_present=comps_present,
            spoken_key_claims=[title] if title else [],
            engagement_driver_assessment="Análise de engajamento baseada em métricas orgânicas.",
            extraction_status=status,
        )

    def _parse_analysis_response(
        self,
        response_text: str,
        video_meta: Dict[str, Any],
    ) -> SingleVideoMultimodalAnalysis:
        """Parses GenAI JSON response with resilient fallback handling."""
        if not response_text:
            return self._create_fallback_analysis(video_meta, status="EMPTY_RESPONSE")

        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        # Attempt 1: Direct Pydantic validation
        try:
            analysis = SingleVideoMultimodalAnalysis.model_validate_json(cleaned)
            self._fill_missing_metadata(analysis, video_meta)
            return analysis
        except Exception as e:
            logger.warning(f"Direct Pydantic validation failed ({e}). Attempting regex extraction...")

        # Attempt 2: Extract JSON substring via regex
        try:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                # Ensure list fields are lists
                list_keys = [
                    "brand_appearances",
                    "features_valued_most",
                    "features_criticized_or_irrelevant",
                    "brand_co_occurrences",
                    "investment_whitespace_signals",
                    "competitor_brands_present",
                    "spoken_key_claims",
                ]
                for k in list_keys:
                    if k in data and isinstance(data[k], str):
                        data[k] = [data[k]]
                analysis = SingleVideoMultimodalAnalysis.model_validate(data)
                self._fill_missing_metadata(analysis, video_meta)
                return analysis
        except Exception as json_err:
            logger.error(f"Fallback JSON parsing failed: {json_err}")

        # Attempt 3: Safe fallback with raw snippet
        return self._create_fallback_analysis(video_meta, summary=cleaned[:300], status="PARSING_FALLBACK")

    def _fill_missing_metadata(
        self,
        analysis: SingleVideoMultimodalAnalysis,
        video_meta: Dict[str, Any],
    ) -> None:
        """Ensures core metadata fields are populated."""
        if not analysis.video_id:
            analysis.video_id = video_meta.get("video_id", "")
        if not analysis.video_title:
            analysis.video_title = video_meta.get("title", "")
        if not analysis.channel_name:
            analysis.channel_name = video_meta.get("channel", "")
        if not analysis.duration_seconds:
            analysis.duration_seconds = video_meta.get("duration_seconds", 0)

        # Synchronize stance aliases
        if not analysis.creator_editorial_stance and analysis.creator_stance:
            analysis.creator_editorial_stance = analysis.creator_stance
        elif not analysis.creator_stance and analysis.creator_editorial_stance:
            analysis.creator_stance = analysis.creator_editorial_stance

        # Check target brand presence
        if self.target_brand:
            t_lower = self.target_brand.lower()
            detected_brands = [a.brand_name.lower() for a in analysis.brand_appearances]
            analysis.target_brand_present = (
                t_lower in detected_brands or t_lower in analysis.summary_of_content.lower()
            )

        # Check competitor presence
        detected_comps = []
        for comp in self.competitors:
            c_lower = comp.lower()
            if any(c_lower in a.brand_name.lower() for a in analysis.brand_appearances) or c_lower in analysis.summary_of_content.lower():
                detected_comps.append(comp)
        analysis.competitor_brands_present = list(set(analysis.competitor_brands_present + detected_comps))

    def analyze_single_video(
        self,
        video_row: Union[Dict[str, Any], pd.Series],
        target_brand: Optional[str] = None,
        competitors: Optional[List[str]] = None,
        category_theme: Optional[str] = None,
    ) -> SingleVideoMultimodalAnalysis:
        """
        Analyzes a single video record using Gemini 3.7 Flash multimodal video streaming.
        Falls back to metadata extraction if video duration > 30m, URL resolution fails, or API is in key-only mode.
        """
        # Normalize input row
        row_dict = video_row.to_dict() if isinstance(video_row, pd.Series) else dict(video_row)
        video_id = str(row_dict.get("video_id") or row_dict.get("videoId") or row_dict.get("id") or "")
        title = str(row_dict.get("title") or row_dict.get("video_title") or "")
        channel = str(row_dict.get("channel") or row_dict.get("channelTitle") or row_dict.get("channel_name") or "")
        url = str(row_dict.get("url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else ""))
        duration_raw = row_dict.get("duration") or row_dict.get("duration_seconds") or 0
        duration_sec = self._parse_iso8601_duration(duration_raw)
        desc = str(row_dict.get("description") or "")

        video_meta = {
            "video_id": video_id,
            "title": title,
            "channel": channel,
            "url": url,
            "duration_seconds": duration_sec,
            "description": desc,
            "views": row_dict.get("views") or row_dict.get("viewCount") or 0,
            "likes": row_dict.get("likes") or row_dict.get("likeCount") or 0,
        }

        t_brand = target_brand or self.target_brand
        comps = competitors if competitors is not None else self.competitors
        c_theme = category_theme or self.category_theme

        # 1. Check Duration Constraint (> 30 mins / 1800s)
        if duration_sec > self.max_video_duration_seconds:
            logger.warning(
                f"Video {video_id} duration ({duration_sec}s) exceeds limit ({self.max_video_duration_seconds}s). "
                "Applying metadata-focused analysis to conserve token budget."
            )
            return self._analyze_video_metadata_only(video_meta, t_brand, comps, c_theme, status="DURATION_EXCEEDED")

        # 2. Attempt Multimodal Video Ingestion via URL Part
        if url and self.enable_visual:
            prompt = self._construct_multimodal_prompt(video_meta, t_brand, comps, c_theme, metadata_only=False)
            try:
                video_part = types.Part.from_uri(file_uri=url, mime_type="video/mp4")
                contents = [video_part, prompt]

                response = generate_content_with_retry(
                    client=self.client,
                    model=self.model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=SingleVideoMultimodalAnalysis,
                    ),
                    fallback_model=self.fallback_model_name,
                    max_retries=3,
                    retry_delay_sec=2.0,
                )
                return self._parse_analysis_response(response.text, video_meta)
            except Exception as e:
                logger.warning(
                    f"Multimodal URL streaming failed for {video_id} ({e}). Falling back to metadata-only extraction."
                )

        # 3. Fallback to Metadata-Only Extraction
        return self._analyze_video_metadata_only(video_meta, t_brand, comps, c_theme, status="METADATA_FALLBACK")

    def _analyze_video_metadata_only(
        self,
        video_meta: Dict[str, Any],
        target_brand: str,
        competitors: List[str],
        category_theme: str,
        status: str = "METADATA_FALLBACK",
    ) -> SingleVideoMultimodalAnalysis:
        """Executes metadata-based extraction when video stream ingestion is unavailable."""
        prompt = self._construct_multimodal_prompt(video_meta, target_brand, competitors, category_theme, metadata_only=True)
        try:
            response = generate_content_with_retry(
                client=self.client,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=SingleVideoMultimodalAnalysis,
                ),
                fallback_model=self.fallback_model_name,
                max_retries=3,
                retry_delay_sec=2.0,
            )
            analysis = self._parse_analysis_response(response.text, video_meta)
            analysis.extraction_status = status
            return analysis
        except Exception as e:
            logger.error(f"Metadata extraction also failed for {video_meta.get('video_id')}: {e}")
            return self._create_fallback_analysis(video_meta, status=status)

    def process_videos_df(
        self,
        videos_df: pd.DataFrame,
        target_brand: Optional[str] = None,
        competitors: Optional[List[str]] = None,
        max_videos: int = 20,
        max_workers: Optional[int] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Dispatches parallel multimodal analysis across discovered videos with worker pacing.

        Args:
            videos_df: DataFrame containing discovered video metadata.
            target_brand: Target brand name override.
            competitors: Competitors list override.
            max_videos: Maximum number of videos to analyze (default 20).
            max_workers: Concurrency limit (default from config, typically 4).

        Returns:
            Tuple of (multimodal_summary_df, appearances_timeline_df).
        """
        if videos_df.empty:
            logger.info("process_videos_df received empty DataFrame.")
            return pd.DataFrame(), pd.DataFrame()

        t_brand = target_brand or self.target_brand
        comps = competitors if competitors is not None else self.competitors
        workers = max_workers or self.max_workers
        subset_df = videos_df.head(max_videos).copy()

        print(
            f"\n--- [Stage 1] Ingestão Multimodal em Paralelo ({len(subset_df)} vídeos, {workers} threads, pacing={self.worker_delay_seconds}s) ---",
            flush=True,
        )

        analysis_results: List[SingleVideoMultimodalAnalysis] = []
        timeline_records: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_meta = {}
            for idx, row in subset_df.iterrows():
                future = executor.submit(self.analyze_single_video, row, t_brand, comps)
                future_to_meta[future] = row.to_dict()
                # Pacing delay between task launches to prevent 429 quota spikes
                if self.worker_delay_seconds > 0 and idx < len(subset_df) - 1:
                    time.sleep(self.worker_delay_seconds)

            for future in tqdm(
                as_completed(future_to_meta),
                total=len(future_to_meta),
                desc="Extração Multimodal (Áudio + Visual)",
            ):
                meta = future_to_meta[future]
                try:
                    result = future.result()
                    analysis_results.append(result)
                except Exception as exc:
                    logger.error(f"Worker exception processing video {meta.get('video_id')}: {exc}")
                    fallback = self._create_fallback_analysis(meta, status="THREAD_EXCEPTION")
                    analysis_results.append(fallback)

        # Build Multimodal Summary DataFrame
        summary_rows = []
        for a in analysis_results:
            visual_count = sum(1 for app in a.brand_appearances if app.modality in ("visual", "both") or "visual" in str(app.appearance_type).lower())
            spoken_count = sum(1 for app in a.brand_appearances if app.modality in ("spoken", "both") or "spoken" in str(app.appearance_type).lower())

            # Legacy compatibility transcript representation
            spoken_claims_str = " | ".join(a.spoken_key_claims) if a.spoken_key_claims else ""
            transcript_composite = f"{a.summary_of_content}" + (f" Claims: {spoken_claims_str}" if spoken_claims_str else "")

            summary_rows.append({
                "video_id": a.video_id,
                "video_title": a.video_title,
                "channel_name": a.channel_name,
                "duration_seconds": a.duration_seconds,
                "summary_of_content": a.summary_of_content,
                "creator_stance": a.creator_stance,
                "creator_editorial_stance": a.creator_editorial_stance or a.creator_stance,
                "target_brand_present": a.target_brand_present,
                "competitor_brands_present": ", ".join(a.competitor_brands_present) if a.competitor_brands_present else "None",
                "features_valued_most": "; ".join(a.features_valued_most) if a.features_valued_most else "None",
                "features_criticized_or_irrelevant": "; ".join(a.features_criticized_or_irrelevant) if a.features_criticized_or_irrelevant else "None",
                "brand_co_occurrences": ", ".join(a.brand_co_occurrences) if a.brand_co_occurrences else "None",
                "investment_whitespace_signals": "; ".join(a.investment_whitespace_signals) if a.investment_whitespace_signals else "None",
                "spoken_key_claims": "; ".join(a.spoken_key_claims) if a.spoken_key_claims else "None",
                "brand_appearances_count": len(a.brand_appearances),
                "visual_appearances_count": visual_count,
                "spoken_appearances_count": spoken_count,
                "extraction_status": a.extraction_status,
                "transcript_text": transcript_composite,
                "has_transcript": True,
            })

            # Build Appearances Timeline Records
            for app in a.brand_appearances:
                timeline_records.append({
                    "video_id": a.video_id,
                    "video_title": a.video_title,
                    "channel_name": a.channel_name,
                    "brand_name": app.brand_name,
                    "modality": app.modality,
                    "appearance_type": app.appearance_type or ("Visual Logo / Product" if app.modality == "visual" else "Spoken Mention"),
                    "timestamps": ", ".join(app.timestamps) if app.timestamps else (app.timestamp or "00:00"),
                    "sentiment": app.sentiment,
                    "context_summary": app.context_summary or app.context or "",
                    "prominence": app.prominence,
                })

        multimodal_df = pd.DataFrame(summary_rows)
        appearances_df = pd.DataFrame(timeline_records)

        # Merge original video stats if available
        if not subset_df.empty and "video_id" in multimodal_df.columns:
            id_col = "video_id" if "video_id" in subset_df.columns else ("videoId" if "videoId" in subset_df.columns else "id")
            if id_col in subset_df.columns:
                extra_cols = [c for c in ["views", "likes", "comments", "url", "published_at"] if c in subset_df.columns]
                if extra_cols:
                    meta_subset = subset_df[[id_col] + extra_cols].rename(columns={id_col: "video_id"})
                    multimodal_df = multimodal_df.merge(meta_subset, on="video_id", how="left")

        # Persist CSV outputs
        self._save_outputs(multimodal_df, appearances_df, t_brand)

        return multimodal_df, appearances_df

    def _save_outputs(
        self,
        multimodal_df: pd.DataFrame,
        appearances_df: pd.DataFrame,
        target_brand: str,
    ) -> None:
        """Saves generated DataFrames to disk."""
        if not self.output_dir:
            return

        try:
            os.makedirs(self.output_dir, exist_ok=True)
            safe_brand = re.sub(r"\W+", "_", target_brand.strip()) or "brand"

            # 1. Multimodal Analysis Summary
            if not multimodal_df.empty:
                summary_file = os.path.join(self.output_dir, f"{safe_brand}_multimodal_analysis.csv")
                run_summary_file = os.path.join(self.output_dir, f"{self.run_id}_multimodal_analysis.csv")
                multimodal_df.to_csv(summary_file, index=False)
                multimodal_df.to_csv(run_summary_file, index=False)
                logger.info(f"Saved multimodal analysis to {summary_file}")

            # 2. Brand Appearances Timeline
            if not appearances_df.empty:
                timeline_file = os.path.join(self.output_dir, f"{safe_brand}_brand_appearances_timeline.csv")
                run_timeline_file = os.path.join(self.output_dir, f"{self.run_id}_brand_appearances_timeline.csv")
                appearances_df.to_csv(timeline_file, index=False)
                appearances_df.to_csv(run_timeline_file, index=False)
                logger.info(f"Saved brand appearances timeline to {timeline_file}")
        except Exception as e:
            logger.warning(f"Could not persist output CSV files: {e}")

    def extract_transcript_for_video(self, video_id: str) -> str:
        """Compatibility helper for legacy callers."""
        return "Vídeo analisado nativamente via fluxo multimodal do Gemini API"
