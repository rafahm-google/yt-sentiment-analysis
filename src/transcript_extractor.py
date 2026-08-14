"""
Legacy Transcript Extractor Adapter Module.

Provides backward compatibility for callers expecting `VideoTranscriptExtractor`,
delegating all operations to the new Stage 1 `VideoMultimodalExtractor`.
"""

import os
import logging
from typing import Optional, Union, Dict, Any, Tuple
import pandas as pd

from multimodal_extractor import VideoMultimodalExtractor, SingleVideoMultimodalAnalysis, BrandAppearance

logger = logging.getLogger(__name__)


class VideoTranscriptExtractor(VideoMultimodalExtractor):
    """
    Adapter subclass maintaining full backward compatibility for legacy callers.
    Delegates underlying video frame and audio stream processing to VideoMultimodalExtractor.
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        config_path: Optional[str] = None,
        target_brand: Optional[str] = None,
        competitors: Optional[list] = None,
        category_theme: Optional[str] = None,
    ) -> None:
        super().__init__(
            config_path=config_path,
            output_dir=output_dir,
            target_brand=target_brand,
            competitors=competitors,
            category_theme=category_theme,
        )

    def extract_transcript_for_video(self, video_id: str) -> str:
        """
        Gemini processes full video streams natively via public YouTube URL.
        """
        return "Vídeo analisado nativamente via fluxo multimodal do Gemini API"

    def process_videos_df(
        self,
        videos_df: pd.DataFrame,
        max_videos: int = 100,
        max_workers: Optional[int] = None,
        **kwargs,
    ) -> Union[pd.DataFrame, Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Extracts multimodal video intelligence while maintaining backward compatibility.
        Returns the primary multimodal DataFrame for single-variable assignments.
        """
        if videos_df.empty:
            return pd.DataFrame()

        multimodal_df, appearances_df = super().process_videos_df(
            videos_df=videos_df,
            max_videos=max_videos,
            max_workers=max_workers,
            **kwargs,
        )

        # Ensure transcript columns are present for legacy compatibility
        if not multimodal_df.empty and "transcript_text" not in multimodal_df.columns:
            multimodal_df["transcript_text"] = multimodal_df.get("summary_of_content", "")
            multimodal_df["has_transcript"] = True

        return multimodal_df

    def _fetch_single(self, video_id: str, title: str, channel: str) -> Dict[str, Any]:
        """Legacy helper for single video transcript simulation."""
        transcript_text = self.extract_transcript_for_video(video_id)
        return {
            "video_id": video_id,
            "title": title,
            "channel": channel,
            "transcript_text": transcript_text,
            "has_transcript": bool(transcript_text),
        }
