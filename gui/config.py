import atexit
import json
import logging
import multiprocessing
import os
from logging.handlers import RotatingFileHandler

from rich.console import Console

# Free Zen LLM models — auto-populated into llm_profiles on startup.
# Models are removed from this list when no longer free.
ZEN_BASE_URL = "https://opencode.ai/zen/v1"

FREE_ZEN_MODELS = [
    {"id": "zen-deepseek-free", "name": "Zen DeepSeek V4 Flash Free", "model": "deepseek-v4-flash-free"},
    {"id": "zen-mimo-free", "name": "Zen MiMo-V2.5 Free", "model": "mimo-v2.5-free"},
    {"id": "zen-laguna-free", "name": "Zen Laguna S 2.1 Free", "model": "laguna-s-2.1-free"},
    {"id": "zen-north-code-free", "name": "Zen North Mini Code Free", "model": "north-mini-code-free"},
    {"id": "zen-nemotron-free", "name": "Zen Nemotron 3 Ultra Free", "model": "nemotron-3-ultra-free"},
    {"id": "zen-big-pickle", "name": "Zen Big Pickle", "model": "big-pickle"},
]

# Directories Setup
# Since config.py is inside gui,
# BASE_DIR should resolve to the project root
GUI_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(GUI_DIR)

CACHE_DIR = os.path.join(BASE_DIR, "cache")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")
MUSIC_DIR = os.path.join(BASE_DIR, "music")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

from rich.logging import RichHandler

console = Console()


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


# Logger Initialization
logger = logging.getLogger("shorts_creator")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    # Rich console handler
    rich_handler = RichHandler(console=console, rich_tracebacks=True, show_path=False)
    rich_handler.setLevel(logging.DEBUG)
    logger.addHandler(rich_handler)

    # JSON File handler (only on main process to avoid spawn-child truncation)
    json_log_file = os.path.join(LOGS_DIR, "server.json.log")
    app_log_file = os.path.join(LOGS_DIR, "app.log")
    if multiprocessing.current_process().name == "MainProcess":
        for f in (json_log_file, app_log_file):
            if not os.path.exists(f):
                open(f, "a").close()
    json_handler = RotatingFileHandler(
        json_log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    json_handler.setFormatter(JSONFormatter())
    json_handler.setLevel(logging.INFO)
    logger.addHandler(json_handler)

SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
PRESETS_FILE = os.path.join(CONFIG_DIR, "presets.json")
PROMPTS_FILE = os.path.join(CONFIG_DIR, "prompts.json")
EMOJIS_FILE = os.path.join(CONFIG_DIR, "emojis.json")

GUI_STATE_FILE = os.path.join(CONFIG_DIR, "gui_state.json")
BATCH_STATS_FILE = os.path.join(CONFIG_DIR, "batch_stats.json")
FAILED_CONFIGS_FILE = os.path.join(CONFIG_DIR, "failed_batch_configs.json")
THUMBNAIL_DIR = os.path.join(OUTPUT_DIR, "thumbnails")
FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "gui/frontend/dist")


def clear_cache():
    if os.path.exists(CACHE_DIR):
        prefixes = (
            "cached_audio_",
            "cached_words_",
            "sentence_audio_",
            "sentence_words_",
            "s_temp_",
            "audio_",
            "subs_",
        )
        for f in os.listdir(CACHE_DIR):
            if any(f.startswith(p) for p in prefixes):
                fp = os.path.join(CACHE_DIR, f)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except Exception as e:
                        logger.debug(f"Failed to remove cache file {fp}: {e}")


if multiprocessing.current_process().name == "MainProcess":
    atexit.register(clear_cache)

# Re-exports — preserve existing import paths so `from gui.config import ...` still works for
# all symbols that were previously defined here.  These are imported lazily (at the bottom of the
# module) to break circular dependencies — each sub-module imports only config constants/logging
# which are already defined before this point.

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
    DEFAULT_PROMPTS,
    load_prompt_templates,
)
from gui.settings_manager import (  # noqa: E402, F401
    load_settings,
    save_settings,
)
