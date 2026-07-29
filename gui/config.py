"""Application configuration: directories, logging, file paths, and module re-exports."""

from __future__ import annotations

import atexit
import json
import logging
import multiprocessing
import os
from logging.handlers import RotatingFileHandler
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

# --- Free Zen LLM models ---

ZEN_BASE_URL: str = "https://opencode.ai/zen/v1"
"""Base URL for free Zen LLM API endpoints."""

FREE_ZEN_MODELS: list[dict[str, str]] = [
    {"id": "zen-deepseek-free", "name": "Zen DeepSeek V4 Flash Free", "model": "deepseek-v4-flash-free"},
    {"id": "zen-mimo-free", "name": "Zen MiMo-V2.5 Free", "model": "mimo-v2.5-free"},
    {"id": "zen-laguna-free", "name": "Zen Laguna S 2.1 Free", "model": "laguna-s-2.1-free"},
    {"id": "zen-north-code-free", "name": "Zen North Mini Code Free", "model": "north-mini-code-free"},
    {"id": "zen-nemotron-free", "name": "Zen Nemotron 3 Ultra Free", "model": "nemotron-3-ultra-free"},
    {"id": "zen-big-pickle", "name": "Zen Big Pickle", "model": "big-pickle"},
]
"""Free Zen LLM models auto-populated into ``llm_profiles`` on startup."""

# --- Directory setup ---

GUI_DIR: str = os.path.dirname(os.path.abspath(__file__))
BASE_DIR: str = os.path.dirname(GUI_DIR)

CACHE_DIR: str = os.path.join(BASE_DIR, "cache")
OUTPUT_DIR: str = os.path.join(BASE_DIR, "output")
CONFIG_DIR: str = os.path.join(BASE_DIR, "config")
VIDEOS_DIR: str = os.path.join(BASE_DIR, "videos")
MUSIC_DIR: str = os.path.join(BASE_DIR, "music")
LOGS_DIR: str = os.path.join(BASE_DIR, "logs")
TEMP_DIR: str = os.path.join(BASE_DIR, "temp")

# Ensure all directories exist
for _dir in (CACHE_DIR, OUTPUT_DIR, CONFIG_DIR, VIDEOS_DIR, MUSIC_DIR, LOGS_DIR, TEMP_DIR):
    os.makedirs(_dir, exist_ok=True)

# --- Console ---

console: Console = Console()


# --- JSON log formatter ---


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            A JSON-encoded string with ``time``, ``level``, ``name``,
            ``message``, and optional ``exc_info`` keys.
        """
        log_record: dict[str, Any] = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


# --- Logger initialisation ---

logger: logging.Logger = logging.getLogger("shorts_creator")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    # Rich console handler
    rich_handler: RichHandler = RichHandler(
        console=console, rich_tracebacks=True, show_path=False
    )
    rich_handler.setLevel(logging.DEBUG)
    logger.addHandler(rich_handler)

    # JSON file handler (only on main process to avoid spawn-child truncation)
    json_log_file: str = os.path.join(LOGS_DIR, "server.json.log")
    app_log_file: str = os.path.join(LOGS_DIR, "app.log")

    if multiprocessing.current_process().name == "MainProcess":
        for f in (json_log_file, app_log_file):
            if not os.path.exists(f):
                open(f, "a").close()

    json_handler: RotatingFileHandler = RotatingFileHandler(
        json_log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    json_handler.setFormatter(JSONFormatter())
    json_handler.setLevel(logging.INFO)
    logger.addHandler(json_handler)

# --- File paths ---

SETTINGS_FILE: str = os.path.join(CONFIG_DIR, "settings.json")
PRESETS_FILE: str = os.path.join(CONFIG_DIR, "presets.json")
PROMPTS_FILE: str = os.path.join(CONFIG_DIR, "prompts.json")
EMOJIS_FILE: str = os.path.join(CONFIG_DIR, "emojis.json")

GUI_STATE_FILE: str = os.path.join(CONFIG_DIR, "gui_state.json")
BATCH_STATS_FILE: str = os.path.join(CONFIG_DIR, "batch_stats.json")
FAILED_CONFIGS_FILE: str = os.path.join(CONFIG_DIR, "failed_batch_configs.json")
CANCELLED_CONFIGS_FILE: str = os.path.join(CONFIG_DIR, "cancelled_batch_configs.json")
DISMISSED_JOBS_FILE: str = os.path.join(CONFIG_DIR, "dismissed_jobs.json")
THUMBNAIL_DIR: str = os.path.join(OUTPUT_DIR, "thumbnails")
FRONTEND_DIST_DIR: str = os.path.join(BASE_DIR, "gui/frontend/dist")

# Cache cleanup prefixes
CACHE_CLEANUP_PREFIXES: tuple[str, ...] = (
    "cached_audio_",
    "cached_words_",
    "sentence_audio_",
    "sentence_words_",
    "s_temp_",
    "audio_",
    "subs_",
)


# --- Cache cleanup ---


def clear_cache() -> None:
    """Remove cached audio / subtitle / temp files from the cache directory."""
    if os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            if any(f.startswith(p) for p in CACHE_CLEANUP_PREFIXES):
                fp: str = os.path.join(CACHE_DIR, f)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except Exception as e:
                        logger.debug("Failed to remove cache file %s: %s", fp, e)


if multiprocessing.current_process().name == "MainProcess":
    atexit.register(clear_cache)

# --- Module re-exports ---
# These are imported lazily (at the bottom of the module) to break circular
# dependencies — each sub-module imports only config constants/logging which
# are already defined before this point.

from gui.builtin_presets import (  # noqa: E402, F401
    BUILTIN_PRESETS,
    delete_custom_preset,
    load_presets,
    save_custom_preset,
)
from gui.emoji_map import (  # noqa: E402, F401
    DEFAULT_EMOJI_MAP,
    load_emoji_map,
    save_emoji_map,
)
from gui.prompts import (  # noqa: E402, F401
    DEFAULT_SCRIPT_SYSTEM_PROMPT,
    load_prompt_templates,
)
from gui.settings_manager import (  # noqa: E402, F401
    load_settings,
    save_settings,
)
