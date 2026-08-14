"""
GenAI Client Factory Module.

Provides centralized, robust initialization for Google GenAI Client (`google-genai` SDK),
supporting Vertex AI (Cloud Run / ADC) with automatic fallback to Developer API Key mode.
"""

import os
import re
import time
import logging
import configparser
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from google import genai

# Ensure mTLS certificate verification does not fail on environments without OpenSSL
os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

logger = logging.getLogger(__name__)


def _str_to_bool(val: Any, default: bool = False) -> bool:
    """Converts common string boolean representations to bool."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    val_str = str(val).strip().lower()
    if val_str in ("1", "true", "yes", "y", "t", "enable", "enabled"):
        return True
    if val_str in ("0", "false", "no", "n", "f", "disable", "disabled"):
        return False
    return default


def get_multimodal_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Parses [Multimodal] section from config.ini with sensible defaults.
    
    Args:
        config_path: Path to config.ini. Defaults to 'config.ini' in project root.
        
    Returns:
        Dict containing multimodal configuration options.
    """
    config = configparser.ConfigParser(interpolation=None)
    if config_path and os.path.exists(config_path):
        config.read(config_path)
    elif os.path.exists("config.ini"):
        config.read("config.ini")

    section = "Multimodal" if config.has_section("Multimodal") else "Analysis"
    
    max_workers = 4
    if config.has_option(section, "max_workers"):
        max_workers = config.getint(section, "max_workers", fallback=4)

    # Support worker_delay_seconds and worker_pacing_delay_sec aliases
    worker_delay = 1.5
    if config.has_option(section, "worker_delay_seconds"):
        worker_delay = config.getfloat(section, "worker_delay_seconds", fallback=1.5)
    elif config.has_option(section, "worker_pacing_delay_sec"):
        worker_delay = config.getfloat(section, "worker_pacing_delay_sec", fallback=1.5)

    # Support max_video_duration_seconds and max_video_duration_minutes
    max_duration_sec = 1800
    if config.has_option(section, "max_video_duration_seconds"):
        max_duration_sec = config.getint(section, "max_video_duration_seconds", fallback=1800)
    elif config.has_option(section, "max_video_duration_minutes"):
        max_duration_sec = config.getint(section, "max_video_duration_minutes", fallback=30) * 60

    enable_visual = True
    if config.has_option(section, "enable_visual_analysis"):
        enable_visual = config.getboolean(section, "enable_visual_analysis", fallback=True)

    use_vertex = True
    if config.has_option(section, "use_vertex_ai"):
        use_vertex = config.getboolean(section, "use_vertex_ai", fallback=True)

    vertex_location = "us-central1"
    if config.has_option(section, "vertex_location"):
        vertex_location = config.get(section, "vertex_location", fallback="us-central1")

    return {
        "max_workers": max_workers,
        "worker_delay_seconds": worker_delay,
        "max_video_duration_seconds": max_duration_sec,
        "enable_visual_analysis": enable_visual,
        "use_vertex_ai": use_vertex,
        "vertex_location": vertex_location,
    }


def get_model_names(config_path: Optional[str] = None) -> Dict[str, str]:
    """
    Retrieves model names from config.ini [Analysis] section with defaults.
    """
    config = configparser.ConfigParser(interpolation=None)
    if config_path and os.path.exists(config_path):
        config.read(config_path)
    elif os.path.exists("config.ini"):
        config.read("config.ini")

    pro_model = "gemini-3.7-flash"
    flash_model = "gemini-3.7-flash"
    fallback_model = "gemini-3.6-flash"

    if config.has_section("Analysis"):
        pro_model = config.get("Analysis", "pro_model_name", fallback="gemini-3.7-flash")
        flash_model = config.get("Analysis", "flash_model_name", fallback="gemini-3.7-flash")
        fallback_model = config.get("Analysis", "fallback_model_name", fallback="gemini-3.6-flash")

    return {
        "pro_model_name": pro_model,
        "flash_model_name": flash_model,
        "fallback_model_name": fallback_model,
    }


def create_genai_client(
    config_path: Optional[str] = None,
    use_vertex: Optional[bool] = None,
    project_id: Optional[str] = None,
    location: Optional[str] = None,
    api_key: Optional[str] = None,
) -> genai.Client:
    """
    Initializes a Google GenAI Client (`genai.Client`) configured for Vertex AI or Developer API.

    Resolution Order:
    1. Explicit parameters passed to this function (`use_vertex`, `project_id`, `location`, `api_key`).
    2. Environment variables (`GOOGLE_GENAI_USE_VERTEX`, `GCP_PROJECT`, `GOOGLE_CLOUD_PROJECT`,
       `VERTEXAI_LOCATION`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`).
    3. Configuration file (`config.ini`).

    Args:
        config_path: Path to config.ini.
        use_vertex: Explicit flag to force Vertex AI (True) or API Key (False). If None, resolves from env/config.
        project_id: GCP Project ID for Vertex AI.
        location: GCP region for Vertex AI (e.g., 'us-central1').
        api_key: Gemini Developer API key.

    Returns:
        genai.Client instance.
    """
    # Load environment variables
    load_dotenv()
    if config_path and os.path.exists(config_path):
        config_dir = os.path.dirname(os.path.abspath(config_path))
        env_file = os.path.join(config_dir, ".env")
        if os.path.exists(env_file):
            load_dotenv(env_file)

    # Read configuration if available
    multimodal_cfg = get_multimodal_config(config_path)

    # Resolve project_id
    if not project_id:
        project_id = (
            os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCP_PROJECT")
            or os.getenv("GCP_PROJECT_NUMBER")
        )

    # Resolve location
    if not location:
        location = (
            os.getenv("VERTEXAI_LOCATION")
            or os.getenv("GOOGLE_CLOUD_LOCATION")
            or os.getenv("GCP_LOCATION")
            or multimodal_cfg.get("vertex_location", "us-central1")
        )

    # Resolve API Key
    if not api_key:
        api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("YOUTUBE_API_KEY")
        )

    # Resolve use_vertex
    if use_vertex is None:
        env_use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEX")
        if env_use_vertex is not None:
            use_vertex = _str_to_bool(env_use_vertex, default=False)
        elif api_key:
            # When API key is available in environment/config, default to Developer API
            use_vertex = False
        elif project_id:
            use_vertex = True
        else:
            use_vertex = False

    # Attempt Vertex AI Client if requested
    if use_vertex and project_id:
        try:
            logger.info(
                f"Initializing genai.Client in Vertex AI mode (project='{project_id}', location='{location}')..."
            )
            client = genai.Client(vertexai=True, project=project_id, location=location)
            logger.info("SUCCESS: GenAI Client initialized with Vertex AI backend.")
            return client
        except Exception as e:
            logger.warning(
                f"Vertex AI initialization failed ({e}). Falling back to Gemini Developer API key mode."
            )

    # Attempt Developer API Key Client
    if api_key:
        try:
            logger.info("Initializing genai.Client in Developer API Key mode...")
            client = genai.Client(api_key=api_key)
            logger.info("SUCCESS: GenAI Client initialized with API key.")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize GenAI Client with API key: {e}")
            raise

    # Attempt Default Environment Client
    try:
        logger.info("Initializing default genai.Client()...")
        client = genai.Client()
        logger.info("SUCCESS: Default GenAI Client initialized.")
        return client
    except Exception as e:
        logger.error(f"All GenAI Client initialization attempts failed: {e}")
        raise RuntimeError(
            "Could not initialize Google GenAI Client. Please ensure GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT is configured."
        ) from e


def generate_content_with_retry(
    client: genai.Client,
    model: str,
    contents: Any,
    config: Optional[Any] = None,
    fallback_model: Optional[str] = "gemini-3.6-flash",
    max_retries: int = 2,
    retry_delay_sec: float = 2.0,
) -> Any:
    """
    Executes generate_content with a hierarchy of Flash models:
    gemini-3.7-flash -> gemini-3.6-flash -> gemini-3.5-flash.
    Strictly avoids Pro models as requested.
    """
    # Define Flash model hierarchy (strictly Flash, no Pro)
    flash_hierarchy = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]
    
    # Build models queue ensuring starting model is first
    model_queue = [model]
    for m in flash_hierarchy:
        if m not in model_queue:
            model_queue.append(m)
            
    if fallback_model and fallback_model not in model_queue and "pro" not in fallback_model.lower():
        model_queue.append(fallback_model)

    last_exception = None

    for current_model in model_queue:
        delay = retry_delay_sec
        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=current_model,
                    contents=contents,
                    config=config,
                )
                return response
            except Exception as e:
                last_exception = e
                err_str = str(e)
                if "503" in err_str or "429" in err_str or "UNAVAILABLE" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    logger.warning(
                        f"Model {current_model} temporary error ({attempt}/{max_retries}). Retrying in {delay:.1f}s... Error: {e}"
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Generate content error with model {current_model}: {e}")
                    break
        logger.warning(f"Model {current_model} exhausted retries. Trying next Flash fallback model in hierarchy...")

    raise last_exception or RuntimeError("All Flash models in hierarchy failed.")
