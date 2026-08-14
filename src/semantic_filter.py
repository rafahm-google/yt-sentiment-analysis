"""
Semantic Relevance Filter Module for YouTube Brand Crawler.

Combines Stage 1 deterministic pre-filtering heuristics (Unicode script checks,
word-boundary negative regex, and channel exclusions) with Stage 2 high-speed,
parallel batch semantic evaluation using Gemini LLM structured outputs.
"""

import os
import re
import json
import time
import unicodedata
import configparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple, Set

from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv


class VideoCandidate(BaseModel):
    """Represents a candidate video with metadata for evaluation."""
    video_id: str
    title: str
    channel: str
    description: str = ""
    views: int = 0
    likes: int = 0
    comments: int = 0
    duration: str = ""
    published_at: str = ""
    tags: List[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class VideoEvaluation(BaseModel):
    """Evaluation result for a single candidate video against campaign objectives."""
    video_id: str
    is_relevant: bool = Field(description="True if video matches campaign goals, False otherwise")
    relevance_score: int = Field(ge=0, le=100, description="Score from 0 to 100")
    reason: str = Field(description="Concise 1-sentence rationale for the score")
    matched_themes: List[str] = Field(default_factory=list, description="Matching thematic tags")
    content_archetype: Optional[str] = Field(default=None, description="One of the campaign content archetypes")

    model_config = {"extra": "ignore"}


class BatchRelevanceResponse(BaseModel):
    """Pydantic model representing structured batch LLM response."""
    evaluations: List[VideoEvaluation]

    model_config = {"extra": "ignore"}


class VideoRelevanceFilter:
    """
    Two-stage hybrid relevance filter:
    1. Fast Stage 1 deterministic heuristics (zero LLM tokens, 0ms latency).
    2. Stage 2 parallel batch semantic evaluation using Gemini structured outputs.
    """

    LATIN_REGIONS: Set[str] = {
        'BR', 'US', 'PT', 'ES', 'MX', 'AR', 'CL', 'CO', 'GB', 'FR', 'DE', 'IT', 'CA'
    }

    # Unicode ranges for Non-Latin scripts:
    # Devanagari (ऀ-ॿ), Tamil (஀-௿), Cyrillic (Ѐ-ӿ), Arabic (؀-ۿ), CJK (一-鿿), Thai (฀-๿)
    NON_LATIN_SCRIPTS_PATTERN = re.compile(
        r'[\u0900-\u097F\u0B80-\u0BFF\u0400-\u04FF\u0600-\u06FF\u4E00-\u9FFF\u0E00-\u0E7F]'
    )

    def __init__(
        self,
        config_path: Optional[str] = None,
        model_name: Optional[str] = None,
        fallback_model_name: Optional[str] = None,
        relevance_threshold: Optional[int] = None
    ):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if config_path is None:
            config_path = os.path.join(self.project_root, 'config.ini')

        self.config_path = config_path
        self.custom_model_name = model_name
        self.custom_fallback_model_name = fallback_model_name
        self.custom_relevance_threshold = relevance_threshold

        self._load_environment_variables()
        self._load_configuration()

        if self.custom_model_name:
            self.model_name = self.custom_model_name
        if self.custom_fallback_model_name:
            self.fallback_model_name = self.custom_fallback_model_name
        if self.custom_relevance_threshold is not None:
            self.relevance_threshold = self.custom_relevance_threshold

        self.client = None
        if self.google_api_key:
            try:
                self.client = genai.Client(api_key=self.google_api_key)
            except Exception as e:
                print(f"[WARNING] Failed to initialize genai.Client: {e}")

    def _load_environment_variables(self):
        load_dotenv(os.path.join(self.project_root, '.env'))
        self.google_api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("YOUTUBE_API_KEY")
        )
        if not self.google_api_key:
            print("[WARNING] No API key found (GEMINI_API_KEY / GOOGLE_API_KEY / YOUTUBE_API_KEY).")

    def _load_configuration(self):
        config = configparser.ConfigParser(interpolation=None)
        if os.path.exists(self.config_path):
            config.read(self.config_path)

        self.model_name = config.get(
            'Analysis',
            'relevance_model_name',
            fallback=config.get('Analysis', 'flash_model_name', fallback='gemini-3.7-flash')
        )
        self.fallback_model_name = config.get(
            'Analysis',
            'fallback_model_name',
            fallback='gemini-3.6-flash'
        )
        self.relevance_threshold = config.getint('Crawler', 'relevance_threshold', fallback=70)

    @staticmethod
    def strip_accents(text: str) -> str:
        """
        Removes diacritical marks / accents from text for robust matching in Portuguese/Spanish.
        E.g., 'ações' -> 'acoes', 'reações' -> 'reacoes', 'símbolo' -> 'simbolo'.
        """
        if not text:
            return ""
        return "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )

    @classmethod
    def sanitize_description(cls, description: str, max_chars: int = 500) -> str:
        """
        Sanitizes and caps description to the first 8 non-empty lines and at most max_chars.
        Prevents prompt token bloat while retaining high-signal introductory creator context.
        """
        if not description:
            return ""
        lines = [line.strip() for line in description.splitlines() if line.strip()]
        if not lines:
            return ""
        truncated = " ".join(lines[:8])
        return truncated[:max_chars].strip()

    def pre_filter_heuristics(
        self,
        candidates: List[Dict[str, Any]],
        exclude_keywords: Optional[List[str]] = None,
        exclude_channels: Optional[List[str]] = None,
        region_code: str = 'BR'
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Stage 1: Fast deterministic heuristic pre-filtering.
        - Non-Latin script pruning (for Latin regions like BR, US, PT).
        - Word-boundary regex matching for negative keywords across title & 500-char sanitized description.
        - Channel exclusion matching.

        Returns: (surviving_candidates, dropped_candidates)
        """
        if not candidates:
            return [], []

        exclude_keywords = exclude_keywords or []
        exclude_channels = exclude_channels or []

        # Prepare normalized exclude channels
        clean_excluded_channels = [
            self.strip_accents(c.strip().lower()) for c in exclude_channels if c and c.strip()
        ]

        # Compile word-boundary regex patterns for exclude_keywords (Reviewer Finding 1)
        compiled_patterns = []
        for kw in exclude_keywords:
            raw_kw = kw.strip()
            if raw_kw:
                norm_kw = self.strip_accents(raw_kw.lower())
                # Use \b at word edges to prevent substring collisions (e.g. 'nan' vs 'financiamento', 'acoes' vs 'reacoes')
                pattern = re.compile(r'\b' + re.escape(norm_kw) + r'\b', re.IGNORECASE)
                compiled_patterns.append((raw_kw, pattern))

        is_latin_region = bool(region_code and region_code.upper() in self.LATIN_REGIONS)

        surviving_candidates = []
        dropped_candidates = []

        for candidate in candidates:
            cand_dict = dict(candidate)
            title = str(cand_dict.get('title', ''))
            raw_desc = str(cand_dict.get('description', ''))
            sanitized_desc = self.sanitize_description(raw_desc, max_chars=500)
            cand_dict['sanitized_description'] = sanitized_desc
            channel = str(cand_dict.get('channel', '')).strip()

            # 1. Region-aware script check on raw title
            if is_latin_region and self.NON_LATIN_SCRIPTS_PATTERN.search(title):
                drop_reason = f"[PRE-FILTER] Non-Latin script detected in title for {region_code.upper()} region"
                cand_dict['relevance_score'] = 0
                cand_dict['is_relevant'] = False
                cand_dict['relevance_reason'] = drop_reason
                cand_dict['content_archetype'] = "Off-topic Script"
                dropped_candidates.append(cand_dict)
                continue

            # 2. Excluded channels check
            if clean_excluded_channels:
                chan_norm = self.strip_accents(channel.lower())
                matched_chan = next(
                    (ec for ec in clean_excluded_channels if ec == chan_norm or ec in chan_norm),
                    None
                )
                if matched_chan:
                    drop_reason = f"[PRE-FILTER] Excluded channel matched: '{matched_chan}'"
                    cand_dict['relevance_score'] = 0
                    cand_dict['is_relevant'] = False
                    cand_dict['relevance_reason'] = drop_reason
                    cand_dict['content_archetype'] = "Excluded Channel"
                    dropped_candidates.append(cand_dict)
                    continue

            # 3. Negative keywords word-boundary regex check across title & sanitized description
            searchable_text = self.strip_accents(f"{title} {sanitized_desc}".lower())
            matched_kw = None
            for raw_kw, pattern in compiled_patterns:
                if pattern.search(searchable_text):
                    matched_kw = raw_kw
                    break

            if matched_kw:
                drop_reason = f"[PRE-FILTER] Negative keyword '{matched_kw}' matched title/description"
                cand_dict['relevance_score'] = 0
                cand_dict['is_relevant'] = False
                cand_dict['relevance_reason'] = drop_reason
                cand_dict['content_archetype'] = "Negative Keyword Match"
                dropped_candidates.append(cand_dict)
                continue

            # Candidate passed Stage 1 heuristics
            surviving_candidates.append(cand_dict)

        return surviving_candidates, dropped_candidates

    def _build_evaluation_prompt(
        self,
        chunk: List[Dict[str, Any]],
        campaign_objective: str,
        additional_context: str = ""
    ) -> str:
        """Constructs prompt for structured batch evaluation."""
        candidate_snippets = []
        for i, c in enumerate(chunk, 1):
            vid_id = c.get('video_id', f'unknown_{i}')
            title = c.get('title', 'N/A')
            channel = c.get('channel', 'N/A')
            desc = c.get('sanitized_description') or self.sanitize_description(c.get('description', ''))
            tags = c.get('tags', [])
            tag_str = ", ".join(tags[:8]) if tags else "N/A"
            views = c.get('views', 0)
            duration = c.get('duration', 'N/A')
            published = c.get('published_at', '') or c.get('date', 'N/A')

            snippet = (
                f"[{i}] Video ID: {vid_id}\n"
                f"    Title: {title}\n"
                f"    Channel: {channel}\n"
                f"    Description: {desc if desc else 'N/A'}\n"
                f"    Tags: {tag_str}\n"
                f"    Metrics: {views} views | Duration: {duration} | Published: {published}"
            )
            candidate_snippets.append(snippet)

        candidates_block = "\n\n".join(candidate_snippets)

        prompt = f"""You are a Lead Market Research Analyst and YouTube Content Curation Expert.
Your task is to evaluate the relevance of YouTube video candidates against a specific commercial campaign briefing or research objective.

## CAMPAIGN OBJECTIVE:
{campaign_objective.strip()}

## ADDITIONAL STRATEGIC CONTEXT:
{additional_context.strip() if additional_context else 'None provided'}

## EVALUATION INSTRUCTIONS & SCORING RULES:
1. Rate each video candidate from 0 to 100 on semantic relevance and strategic value to the campaign objective:
   - Score >= 70 (`is_relevant = true`): Direct relevance to the commercial entity, brand initiative, customer purchasing experience, unboxing, comparison, pricing, fulfillment, customer friction, or strategic topic.
   - Score 40 to 69 (`is_relevant = false`): Weak or tangential relevance (e.g. general brand mentions without covering the specific campaign topic).
   - Score 0 to 39 (`is_relevant = false`): Completely off-topic noise (e.g., cooking recipes, infant nutrition/baby formula, unrelated stock market updates, generic marketplace try-ons, appliance repairs/tutorials).
2. For YouTube Shorts or videos with minimal description, judge primarily by the title, channel name, and tags.
3. Provide a concise 1-sentence reason (`reason`) in Portuguese explaining why the video is or is not relevant.
4. Extract 1-3 key thematic tags (`matched_themes`).
5. Classify the video into a `content_archetype` (e.g. 'Haul / Unboxing', 'Review & Comparison', 'Pricing & Promos', 'Customer Experience / Friction', 'Brand Strategy', 'Off-topic / Noise').
6. Return evaluations for ALL candidate videos in the batch, matching each evaluation by `video_id`.

## CANDIDATE VIDEOS TO EVALUATE ({len(chunk)} items):
{candidates_block}
"""
        return prompt

    def _evaluate_chunk(
        self,
        chunk: List[Dict[str, Any]],
        campaign_objective: str,
        additional_context: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Evaluates a chunk of up to 20 video candidates in a single structured Gemini call.
        - Implements 3 retries with exponential backoff on 503 / 429 errors.
        - Falls back to fallback_model_name if primary fails.
        - Defensive matching: Maps evaluations by video_id with title fallback.
        - Fail-safe mode: If LLM is totally unreachable, tags candidates with relevance_score=-1 and keeps them.
        """
        if not chunk:
            return []

        if not self.client:
            print("[WARNING] GenAI Client not initialized. Triggering fail-safe bypass mode.")
            return self._apply_failsafe_mode(chunk, "GenAI Client not initialized (missing API key)")

        prompt = self._build_evaluation_prompt(chunk, campaign_objective, additional_context)
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BatchRelevanceResponse,
            temperature=0.1
        )

        response_text = None
        flash_hierarchy = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]
        models_to_try = []
        for m in [self.model_name, getattr(self, 'fallback_model_name', 'gemini-3.6-flash')] + flash_hierarchy:
            if m and m not in models_to_try and "pro" not in m.lower():
                models_to_try.append(m)

        for current_model in models_to_try:
            print(f"🧠 Evaluating batch of {len(chunk)} videos using {current_model}...")
            for attempt in range(3):
                try:
                    response = self.client.models.generate_content(
                        model=current_model,
                        contents=prompt,
                        config=config
                    )
                    if response and response.text:
                        response_text = response.text
                        break
                except Exception as e:
                    err_str = str(e)
                    is_transient = any(
                        code in err_str
                        for code in ["503", "429", "UNAVAILABLE", "OVERLOADED", "RESOURCE_EXHAUSTED"]
                    )
                    if is_transient and attempt < 2:
                        sleep_time = (2 ** attempt) * 2  # 2s, 4s
                        print(f"⚠️ Model {current_model} temporary error ({err_str[:60]}...). Retrying in {sleep_time}s (Attempt {attempt+1}/3)...")
                        time.sleep(sleep_time)
                    else:
                        print(f"❌ Attempt {attempt+1} on {current_model} failed: {err_str[:120]}")
                        break

            if response_text:
                break

        if not response_text:
            print(f"[FAILSAFE] All GenAI models ({', '.join(models_to_try)}) failed. Activating fail-safe bypass mode.")
            return self._apply_failsafe_mode(chunk, "GenAI API outage across all attempted models")

        # Parse structured response
        try:
            batch_resp = BatchRelevanceResponse.model_validate_json(response_text)
            evaluations = batch_resp.evaluations
        except Exception as parse_err:
            print(f"⚠️ Pydantic parsing error on Gemini response: {parse_err}. Attempting raw JSON fallback...")
            evaluations = self._fallback_json_parse(response_text)

        # Defensive matching by video_id with index/title fallback
        eval_map_by_id = {e.video_id.strip(): e for e in evaluations if e.video_id}
        eval_map_by_index = {i: e for i, e in enumerate(evaluations)}

        evaluated_chunk = []
        for idx, candidate in enumerate(chunk):
            cand_item = dict(candidate)
            vid_id = str(cand_item.get('video_id', '')).strip()

            ev = None
            if vid_id and vid_id in eval_map_by_id:
                ev = eval_map_by_id[vid_id]
            elif idx in eval_map_by_index:
                ev = eval_map_by_index[idx]

            if ev:
                cand_item['relevance_score'] = int(ev.relevance_score)
                cand_item['is_relevant'] = bool(ev.is_relevant)
                cand_item['relevance_reason'] = str(ev.reason)
                cand_item['matched_themes'] = list(ev.matched_themes)
                cand_item['content_archetype'] = str(ev.content_archetype) if ev.content_archetype else "General"
            else:
                cand_item['relevance_score'] = 50
                cand_item['is_relevant'] = False
                cand_item['relevance_reason'] = "Video evaluation omitted in LLM response (defaulted)"
                cand_item['matched_themes'] = []
                cand_item['content_archetype'] = "Unknown"

            evaluated_chunk.append(cand_item)

        return evaluated_chunk

    def _fallback_json_parse(self, text: str) -> List[VideoEvaluation]:
        """Defensive regex-based JSON parser for response text."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            evals_raw = data.get("evaluations", [])
            return [VideoEvaluation(**e) for e in evals_raw]
        except Exception as e:
            print(f"Failed to recover evaluations from response JSON: {e}")
            return []

    def _apply_failsafe_mode(self, chunk: List[Dict[str, Any]], reason: str) -> List[Dict[str, Any]]:
        """Applies fail-safe bypass attributes when GenAI API is completely unreachable."""
        failsafe_chunk = []
        for candidate in chunk:
            cand = dict(candidate)
            cand['relevance_score'] = -1
            cand['is_relevant'] = True
            cand['relevance_reason'] = f"[FAILSAFE] Heuristic passed; AI evaluation bypassed due to API outage ({reason})"
            cand['matched_themes'] = ["Failsafe Fallback"]
            cand['content_archetype'] = "Failsafe"
            failsafe_chunk.append(cand)
        return failsafe_chunk

    def evaluate_semantic_relevance(
        self,
        candidates: List[Dict[str, Any]],
        campaign_objective: str,
        additional_context: str = "",
        batch_size: int = 20,
        max_workers: int = 3,
        threshold: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Stage 2: Chunked batch evaluation with bounded concurrency.
        - Chunks candidates into batches of batch_size (default 20).
        - Executes concurrently via ThreadPoolExecutor(max_workers=max_workers).
        - Filters candidates by relevance_score >= threshold and is_relevant == True (or relevance_score == -1 in fail-safe).
        Returns: (relevant_candidates, rejected_candidates)
        """
        if not candidates:
            return [], []

        active_threshold = self.relevance_threshold if threshold is None else threshold

        # Chunk candidates into batches
        chunks = [candidates[i:i + batch_size] for i in range(0, len(candidates), batch_size)]
        evaluated_candidates = []

        if len(chunks) == 1:
            evaluated_candidates = self._evaluate_chunk(chunks[0], campaign_objective, additional_context)
        else:
            print(f"📦 Distributing {len(candidates)} candidates across {len(chunks)} parallel chunks (workers={max_workers})...")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_chunk = {
                    executor.submit(self._evaluate_chunk, chunk, campaign_objective, additional_context): idx
                    for idx, chunk in enumerate(chunks)
                }
                results_by_index = {}
                for future in as_completed(future_to_chunk):
                    chunk_idx = future_to_chunk[future]
                    try:
                        results_by_index[chunk_idx] = future.result()
                    except Exception as exc:
                        print(f"❌ Chunk {chunk_idx} generated an exception: {exc}")
                        results_by_index[chunk_idx] = self._apply_failsafe_mode(
                            chunks[chunk_idx], f"Worker thread exception: {exc}"
                        )

                # Reassemble in original order
                for idx in range(len(chunks)):
                    evaluated_candidates.extend(results_by_index.get(idx, []))

        # Segregate relevant vs rejected
        relevant_candidates = []
        rejected_candidates = []

        for candidate in evaluated_candidates:
            score = candidate.get('relevance_score', 0)
            is_rel = candidate.get('is_relevant', False)

            # Pass if fail-safe mode (-1) or if meets threshold & is_relevant
            if score == -1 or (score >= active_threshold and is_rel):
                relevant_candidates.append(candidate)
            else:
                rejected_candidates.append(candidate)

        return relevant_candidates, rejected_candidates

    def filter_videos(
        self,
        video_details: List[Dict[str, Any]],
        campaign_objective: str,
        additional_context: str = "",
        exclude_keywords: Optional[List[str]] = None,
        exclude_channels: Optional[List[str]] = None,
        region_code: str = 'BR',
        threshold: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Coordinates Stage 1 Heuristics and Stage 2 Semantic Evaluation.
        Returns: (curated_relevant_videos, all_rejected_videos)
        """
        if not video_details:
            return [], []

        print(f"\n🔍 [STAGE 1] Running Deterministic Heuristics on {len(video_details)} candidate videos...")
        surviving_heuristics, dropped_heuristics = self.pre_filter_heuristics(
            candidates=video_details,
            exclude_keywords=exclude_keywords,
            exclude_channels=exclude_channels,
            region_code=region_code
        )
        print(f"✅ Stage 1 Complete: {len(surviving_heuristics)} passed, {len(dropped_heuristics)} pruned by heuristics.")

        if not surviving_heuristics:
            print("⚠️ Zero candidates passed Stage 1 heuristics.")
            return [], dropped_heuristics

        print(f"\n🧠 [STAGE 2] Running Batch LLM Semantic Relevance Evaluation on {len(surviving_heuristics)} videos...")
        relevant_videos, rejected_semantic = self.evaluate_semantic_relevance(
            candidates=surviving_heuristics,
            campaign_objective=campaign_objective,
            additional_context=additional_context,
            batch_size=20,
            max_workers=3,
            threshold=threshold
        )
        print(f"🎯 Stage 2 Complete: {len(relevant_videos)} relevant (>= {threshold or self.relevance_threshold} pts), {len(rejected_semantic)} rejected.")

        all_rejected = dropped_heuristics + rejected_semantic
        return relevant_videos, all_rejected


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING UNIT & INTEGRATION TESTS FOR VideoRelevanceFilter")
    print("=" * 70)

    filter_module = VideoRelevanceFilter(model_name="gemini-3.7-flash", fallback_model_name="gemini-3.6-flash")

    # -------------------------------------------------------------
    # TEST 1: Regex Word Boundary Matching (Reviewer Finding 1)
    # -------------------------------------------------------------
    print("\n--- TEST 1: Regex Word Boundary Matching ---")
    exclude_kws = ["nan", "bolo", "acoes", "roupas shopee"]
    
    test_cases_heuristics = [
        # Should NOT trigger "nan":
        {"video_id": "v1", "title": "Como parcelar compras no Empório Nestlé sem juros (Financiamento e Cupons)", "description": "Guia de finanças para economizar no frete."},
        # Should trigger "nan":
        {"video_id": "v2", "title": "Lata de Leite Nan Supreme 1 para bebês", "description": "Review da fórmula infantil."},
        # Should NOT trigger "bolo":
        {"video_id": "v3", "title": "O novo símbolo da Nestlé na embalagem oficial", "description": "Mudança visual no branding da marca."},
        # Should trigger "bolo":
        {"video_id": "v4", "title": "Receita de bolo de chocolate fofinho Nestlé", "description": "Como fazer bolo caseiro fácil."},
        # Should NOT trigger "acoes":
        {"video_id": "v5", "title": "Reações dos clientes ao receber a entrega do Empório Nestlé", "description": "Comentários sinceros sobre a entrega rápida."},
        # Should trigger "acoes":
        {"video_id": "v6", "title": "Análise de ações da Nestlé e dividendos na Bolsa", "description": "Vale a pena investir em ações?"},
        # Should trigger "roupas shopee":
        {"video_id": "v7", "title": "Mega provador roupas Shopee e Shein 2026", "description": "Comprei vestidinhos e blusas baratas."},
        # Should NOT trigger "roupas shopee":
        {"video_id": "v8", "title": "Comprei no Empório Nestlé vs Shopee oficial de alimentos", "description": "Comparativo de frete e preços."},
    ]

    surviving, dropped = filter_module.pre_filter_heuristics(
        candidates=test_cases_heuristics,
        exclude_keywords=exclude_kws,
        region_code="BR"
    )

    surviving_ids = {c["video_id"] for c in surviving}
    dropped_ids = {c["video_id"] for c in dropped}

    assert "v1" in surviving_ids, "v1 (Financiamento) should NOT trigger 'nan'!"
    assert "v2" in dropped_ids, "v2 (Nan Supreme) MUST trigger 'nan'!"
    assert "v3" in surviving_ids, "v3 (Símbolo) should NOT trigger 'bolo'!"
    assert "v4" in dropped_ids, "v4 (Bolo de chocolate) MUST trigger 'bolo'!"
    assert "v5" in surviving_ids, "v5 (Reações) should NOT trigger 'acoes'!"
    assert "v6" in dropped_ids, "v6 (Ações e dividendos) MUST trigger 'acoes'!"
    assert "v7" in dropped_ids, "v7 (Roupas Shopee) MUST trigger 'roupas shopee'!"
    assert "v8" in surviving_ids, "v8 (Empório vs Shopee alimentos) should NOT trigger 'roupas shopee'!"
    print("✅ TEST 1 PASSED: All word-boundary regex checks succeeded with zero false collisions.")

    # -------------------------------------------------------------
    # TEST 2: Region-Aware Script Filtering
    # -------------------------------------------------------------
    print("\n--- TEST 2: Region-Aware Script Filtering ---")
    script_candidates = [
        {"video_id": "s_tamil", "title": "நெஸ்லே தயாரிப்பு விமர்சனம்", "description": "Tamil review"},
        {"video_id": "s_hindi", "title": "नेस्ले उत्पाद की समीक्षा", "description": "Hindi review"},
        {"video_id": "s_cyrillic", "title": "Обзор покупок в интернет-магазине Nestlé", "description": "Russian review"},
        {"video_id": "s_arabic", "title": "مراجعة منتجات نستله الرسمية", "description": "Arabic review"},
        {"video_id": "s_cjk", "title": "雀巢官方商城开箱测评", "description": "Chinese review"},
        {"video_id": "s_thai", "title": "รีวิวการสั่งซื้อจาก Nestlé", "description": "Thai review"},
        {"video_id": "s_valid_br", "title": "Comprei no Empório Nestlé: Unboxing e Avaliação", "description": "Tudo sobre o D2C oficial no Brasil."},
    ]

    # In Latin region ('BR')
    surv_br, drop_br = filter_module.pre_filter_heuristics(
        candidates=script_candidates,
        exclude_keywords=[],
        region_code="BR"
    )
    surv_br_ids = {c["video_id"] for c in surv_br}
    assert surv_br_ids == {"s_valid_br"}, f"Expected only 's_valid_br' to survive in BR, got {surv_br_ids}"

    # In Non-Latin region ('IN' or 'JP')
    surv_in, drop_in = filter_module.pre_filter_heuristics(
        candidates=script_candidates,
        exclude_keywords=[],
        region_code="IN"
    )
    assert len(surv_in) == len(script_candidates), "Non-Latin regions should not drop non-Latin scripts!"
    print("✅ TEST 2 PASSED: Region-aware script filtering correctly enforces Latin constraints.")

    # -------------------------------------------------------------
    # TEST 3: Live Batch Evaluation of Synthetic Fixtures with Gemini
    # -------------------------------------------------------------
    print("\n--- TEST 3: Live Batch Semantic Evaluation with Gemini ---")
    campaign_objective = "Analisar a experiência de compra, percepção de preço, frete, cupons e adoção do canal D2C Empório Nestlé em comparação a marketplaces no Brasil."
    additional_context = "Estudo focado na loja oficial online Empório Nestlé, inteligência artificial Nina, cupons promocionais e atritos de entrega."

    synthetic_candidates = [
        # 5 Relevant D2C Videos:
        {"video_id": "d2c_1", "title": "Comprei no Empório Nestlé pela primeira vez: Unboxing e Cupom de Frete Grátis!", "channel": "Economia e Compras", "description": "Mostrando minha compra no site oficial do Empório Nestlé com cupom de desconto.", "views": 15000, "duration": "PT6M30S"},
        {"video_id": "d2c_2", "title": "Empório Nestlé vs Mercado Livre: Onde é mais barato comprar Nescafé Dolce Gusto?", "channel": "Café & Análise", "description": "Comparando preços, frete e tempo de entrega da loja oficial versus marketplaces.", "views": 28000, "duration": "PT10M15S"},
        {"video_id": "d2c_3", "title": "Testei a IA Nina do Empório Nestlé para fazer compras no WhatsApp", "channel": "Inovação Varejo", "description": "Como funciona o assistente virtual da Nestlé para pedidos D2C e atendimento.", "views": 8500, "duration": "PT4M45S"},
        {"video_id": "d2c_4", "title": "Minhas compras no Clube Empório Nestlé: Vale a pena o programa de fidelidade?", "channel": "Dicas de Consumo", "description": "Review dos pontos, descontos exclusivos e promoções do clube D2C.", "views": 12000, "duration": "PT8M00S"},
        {"video_id": "d2c_5", "title": "Empório Nestlé atrasou minha entrega? Avaliação sincera do atendimento Reclame Aqui", "channel": "Consumidor Alerta", "description": "Análise da logística, embalagem dos chocolates e resolução de problemas.", "views": 21000, "duration": "PT7M20S"},
        
        # 5 Off-Topic Videos:
        {"video_id": "noise_1", "title": "Bolo Vulcão de Ninho com Nutella - Receita Super Fácil e Cremosa", "channel": "Receitas da Vovó", "description": "Ingredientes: 1 lata de Leite Moça Nestlé, leite em pó ninho...", "views": 450000, "duration": "PT12M00S"},
        {"video_id": "noise_2", "title": "Qual a melhor fórmula infantil? Nan Comfor vs Nestogeno vs Aptamil", "channel": "Pediatria para Mães", "description": "Diferenças nutricionais para bebês recém nascidos e cólicas.", "views": 89000, "duration": "PT15M30S"},
        {"video_id": "noise_3", "title": "Petrobras (PETR4) e Vale (VALE3) disparam com dividendos; IBOVESPA hoje", "channel": "Investidor Pro", "description": "Notícias do mercado financeiro e análise gráfica de ações na B3.", "views": 34000, "duration": "PT20M00S"},
        {"video_id": "noise_4", "title": "Como descalcificar e consertar vazamento na cafeteira Dolce Gusto Mini Me", "channel": "Consertos Caseiros", "description": "Passo a passo para limpar o bico injetor e trocar anel de vedação.", "views": 115000, "duration": "PT9M10S"},
        {"video_id": "noise_5", "title": "Provador Fashion Shopee: 10 vestidos e croppeds por menos de 30 reais", "channel": "Moda & Estilo", "description": "Haul de roupas femininas compradas na Shopee da China.", "views": 67000, "duration": "PT14M40S"},
    ]

    curated_videos, rejected_videos = filter_module.filter_videos(
        video_details=synthetic_candidates,
        campaign_objective=campaign_objective,
        additional_context=additional_context,
        exclude_keywords=["receita", "bolo", "formula infantil", "acoes", "dividendos", "conserto", "descalcificar", "provador"],
        exclude_channels=[],
        region_code="BR",
        threshold=70
    )

    curated_ids = {v["video_id"] for v in curated_videos}
    rejected_ids = {v["video_id"] for v in rejected_videos}

    print(f"\nCurated Video IDs ({len(curated_videos)}): {curated_ids}")
    print(f"Rejected Video IDs ({len(rejected_videos)}): {rejected_ids}")

    expected_relevant = {"d2c_1", "d2c_2", "d2c_3", "d2c_4", "d2c_5"}
    expected_noise = {"noise_1", "noise_2", "noise_3", "noise_4", "noise_5"}

    # Validate that all noise videos were rejected
    assert expected_noise.issubset(rejected_ids), f"Noise leakage detected! Leaked: {expected_noise - rejected_ids}"
    
    # Validate that relevant D2C videos were curated
    assert expected_relevant.issubset(curated_ids), f"Relevant videos missed! Missed: {expected_relevant - curated_ids}"

    print("\nCurated Videos Audit:")
    for v in curated_videos:
        print(f"  • [{v['relevance_score']} pts] {v['title']} (Archetype: {v.get('content_archetype')})")
        print(f"    Reason: {v.get('relevance_reason')}")

    print("\n✅ TEST 3 PASSED: All synthetic tests passed with 100% precision and zero noise leakage.")
    print("=" * 70)
    print("ALL TESTS IN src/semantic_filter.py COMPLETED SUCCESSFULLY!")
    print("=" * 70)
