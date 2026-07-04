import os
import json
import logging
import atexit
from logging.handlers import RotatingFileHandler
from rich.console import Console

from cli.state import settings

# Directories Setup
# Since config.py is inside c:\Users\Brad\Documents\shorts-for-sorts\cli\,
# BASE_DIR should resolve to the project root c:\Users\Brad\Documents\shorts-for-sorts
CLI_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CLI_DIR)

CACHE_DIR = os.path.join(BASE_DIR, "cache")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")
MUSIC_DIR = os.path.join(BASE_DIR, "music")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Logger Initialization
logger = logging.getLogger("shorts_creator")
logger.setLevel(logging.WARNING)
if not logger.handlers:
    log_file = os.path.join(LOGS_DIR, "app.log")
    handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
PRESETS_FILE = os.path.join(CONFIG_DIR, "presets.json")
PROMPTS_FILE = os.path.join(CONFIG_DIR, "prompts.json")
EMOJIS_FILE = os.path.join(CONFIG_DIR, "emojis.json")

console = Console()

def clear_cache():
    if os.path.exists(CACHE_DIR):
        prefixes = (
            "cached_audio_", "cached_words_",
            "sentence_audio_", "sentence_words_",
            "s_temp_", "audio_", "subs_"
        )
        for f in os.listdir(CACHE_DIR):
            if any(f.startswith(p) for p in prefixes):
                fp = os.path.join(CACHE_DIR, f)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except Exception as e:
                        logger.debug(f"Failed to remove cache file {fp}: {e}")

atexit.register(clear_cache)

BUILTIN_PRESETS = {
    "Split-Screen Chill (Yellow Highlight)": {
        "name": "Split-Screen Chill (Yellow Highlight)",
        "selected_voice": "am_adam",
        "bg_video_path": "random",
        "bg_video_bottom_path": "random",
        "bg_music_path": "music/default_music.mp3",
        "music_volume": 0.15,
        "voice_volume": 1.2,
        "sub_font": "Arial",
        "sub_size": 76,
        "sub_color": "#FFFFFF",
        "sub_highlight": "#FFFF00",
        "sub_outline": "#000000",
        "sub_outline_width": 6,
        "sub_bold": True,
        "word_pop": True,
        "word_pop_scale": 1.15,
        "inactive_dim": True,
        "inactive_alpha": "88",
        "enable_emojis": True
    },
    "Lofi Storyteller (Cyan Highlight)": {
        "name": "Lofi Storyteller (Cyan Highlight)",
        "selected_voice": "af_bella",
        "bg_video_path": "random",
        "bg_video_bottom_path": None,
        "bg_music_path": "music/default_music.mp3",
        "music_volume": 0.10,
        "voice_volume": 1.0,
        "sub_font": "Arial",
        "sub_size": 68,
        "sub_color": "#FFFFFF",
        "sub_highlight": "#00FFFF",
        "sub_outline": "#000000",
        "sub_outline_width": 4,
        "sub_bold": True,
        "word_pop": True,
        "word_pop_scale": 1.15,
        "inactive_dim": True,
        "inactive_alpha": "88",
        "enable_emojis": True
    },
    "Fast-Paced Promo (Magenta Highlight)": {
        "name": "Fast-Paced Promo (Magenta Highlight)",
        "selected_voice": "bm_george",
        "bg_video_path": "random",
        "bg_video_bottom_path": None,
        "bg_music_path": "music/default_music.mp3",
        "music_volume": 0.20,
        "voice_volume": 1.1,
        "sub_font": "Impact",
        "sub_size": 80,
        "sub_color": "#FFFFFF",
        "sub_highlight": "#FF00FF",
        "sub_outline": "#000000",
        "sub_outline_width": 7,
        "sub_bold": True,
        "word_pop": True,
        "word_pop_scale": 1.15,
        "inactive_dim": True,
        "inactive_alpha": "88",
        "enable_emojis": True
    },
    "TikTok Kinetic Pop (Green Highlight)": {
        "name": "TikTok Kinetic Pop (Green Highlight)",
        "selected_voice": "af_sarah",
        "bg_video_path": "random",
        "bg_video_bottom_path": "random",
        "bg_music_path": "music/default_music.mp3",
        "music_volume": 0.15,
        "voice_volume": 1.2,
        "sub_font": "Arial",
        "sub_size": 80,
        "sub_color": "#FFFFFF",
        "sub_highlight": "#00FF00",
        "sub_outline": "#000000",
        "sub_outline_width": 6,
        "sub_bold": True,
        "word_pop": True,
        "word_pop_scale": 1.20,
        "inactive_dim": True,
        "inactive_alpha": "66",
        "enable_emojis": True
    },
    "Retro Synthwave (Purple Highlight)": {
        "name": "Retro Synthwave (Purple Highlight)",
        "selected_voice": "af_sky",
        "bg_video_path": "random",
        "bg_video_bottom_path": None,
        "bg_music_path": "music/default_music.mp3",
        "music_volume": 0.15,
        "voice_volume": 1.1,
        "sub_font": "Courier New",
        "sub_size": 70,
        "sub_color": "#FFFFFF",
        "sub_highlight": "#FF00FF",
        "sub_outline": "#3F007F",
        "sub_outline_width": 5,
        "sub_bold": True,
        "word_pop": True,
        "word_pop_scale": 1.20,
        "inactive_dim": True,
        "inactive_alpha": "AA",
        "enable_emojis": True
    },
    "Cinematic Documentary (Gold Highlight)": {
        "name": "Cinematic Documentary (Gold Highlight)",
        "selected_voice": "am_michael",
        "bg_video_path": "random",
        "bg_video_bottom_path": None,
        "bg_music_path": "music/default_music.mp3",
        "music_volume": 0.10,
        "voice_volume": 1.0,
        "sub_font": "Georgia",
        "sub_size": 64,
        "sub_color": "#FFFFFF",
        "sub_highlight": "#FFCC00",
        "sub_outline": "#000000",
        "sub_outline_width": 4,
        "sub_bold": True,
        "word_pop": False,
        "word_pop_scale": 1.0,
        "inactive_dim": False,
        "inactive_alpha": "FF",
        "enable_emojis": False
    },
    "Cyberpunk Red (Red Highlight)": {
        "name": "Cyberpunk Red (Red Highlight)",
        "selected_voice": "am_fenrir",
        "bg_video_path": "random",
        "bg_video_bottom_path": "random",
        "bg_music_path": "music/default_music.mp3",
        "music_volume": 0.20,
        "voice_volume": 1.2,
        "sub_font": "Impact",
        "sub_size": 84,
        "sub_color": "#FFFFFF",
        "sub_highlight": "#FF0000",
        "sub_outline": "#000000",
        "sub_outline_width": 7,
        "sub_bold": True,
        "word_pop": True,
        "word_pop_scale": 1.25,
        "inactive_dim": True,
        "inactive_alpha": "66",
        "enable_emojis": False
    },
    "Classic Serif Storyteller (Amber Highlight)": {
        "name": "Classic Serif Storyteller (Amber Highlight)",
        "selected_voice": "bf_emma",
        "bg_video_path": "random",
        "bg_video_bottom_path": None,
        "bg_music_path": "music/default_music.mp3",
        "music_volume": 0.12,
        "voice_volume": 1.0,
        "sub_font": "Times New Roman",
        "sub_size": 72,
        "sub_color": "#FFFFFF",
        "sub_highlight": "#FFBF00",
        "sub_outline": "#000000",
        "sub_outline_width": 5,
        "sub_bold": True,
        "word_pop": True,
        "word_pop_scale": 1.15,
        "inactive_dim": True,
        "inactive_alpha": "88",
        "enable_emojis": True
    }
}

DEFAULT_EMOJI_MAP = {
    "science": "🧪", "scientific": "🧪", "scientist": "🧪",
    "physics": "⚛️", "chemistry": "🧪", "biology": "🧬",
    "space": "🌌", "planet": "🪐", "star": "⭐", "earth": "🌍", "moon": "🌙", "sun": "☀️",
    "universe": "🌌", "galaxy": "🌌", "alien": "👽", "ufo": "🛸",
    "fact": "💡", "facts": "💡", "real": "✅", "fake": "❌", "true": "💯", "false": "🚫",
    "nature": "🌿", "animal": "🐾", "water": "💧", "fire": "🔥", "ice": "❄️",
    "history": "📜", "historical": "📜", "ancient": "🏛️", "empire": "👑", "king": "👑", "queen": "👑",
    "war": "⚔️", "battle": "⚔️", "soldier": "🪖",
    "mystery": "🕵️‍♂️", "mysterious": "🕵️‍♂️", "secret": "🤫", "secrets": "🤫",
    "lost": "🗺️", "find": "🔍", "found": "🔍", "search": "🔎",
    "gold": "🪙", "treasure": "🏴‍☠️", "pirate": "🏴‍☠️",
    "scary": "😨", "creepy": "😰", "ghost": "👻", "dark": "🌑", "phone": "📱", "call": "📞",
    "text": "💬", "message": "✉️", "number": "🔢", "cry": "😭", "scream": "😱", "run": "🏃",
    "fear": "😨", "dead": "💀", "death": "💀", "kill": "🔪", "killer": "🔪", "blood": "🩸",
    "night": "🌃", "shadow": "👤", "monster": "👹", "demon": "😈",
    "money": "💵", "rich": "🤑", "poor": "💸", "buy": "🛒", "sell": "🏷️",
    "dollar": "💵", "dollars": "💵", "cash": "💰", "wealth": "💎",
    "business": "💼", "job": "💼", "boss": "👔", "office": "🏢",
    "motivation": "🔥", "success": "🏆", "lazy": "🛌", "procrastinate": "⏳", "procrastination": "⏳",
    "work": "⚙️", "life": "🌱", "hack": "💡", "hacks": "💡", "morning": "🌅", "routine": "📅",
    "habit": "🔁", "habits": "🔁", "clock": "⏰", "time": "⏱️", "hour": "⏳", "day": "☀️",
    "school": "🏫", "student": "🎓", "learn": "📚", "study": "📖", "brain": "🧠", "mind": "🧠",
    "focus": "🎯", "goal": "🥅", "win": "🥇", "lose": "❌",
    "computer": "💻", "phone": "📱", "internet": "🌐", "code": "💻", "ai": "🤖", "robot": "🤖",
    "game": "🎮", "gaming": "🎮", "play": "▶️",
    "music": "🎵", "song": "🎶", "video": "📹", "photo": "📷",
    "love": "❤️", "friend": "🤝", "people": "👥", "man": "👨", "woman": "👩",
    "food": "🍔", "drink": "🥤", "coffee": "☕", "car": "🚗", "plane": "✈️",
    "house": "🏠", "home": "🏠", "city": "🏙️", "world": "🌐"
}

def load_presets():
    presets = BUILTIN_PRESETS.copy()
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r") as f:
                custom_presets = json.load(f)
                for name, p in custom_presets.items():
                    presets[name] = p
        except Exception as e:
            logger.warning(f"Failed to load custom presets from {PRESETS_FILE}: {e}", exc_info=True)
    return presets

def save_custom_preset(name, preset_dict):
    presets = {}
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r") as f:
                presets = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load presets file prior to saving preset '{name}': {e}", exc_info=True)
    presets[name] = preset_dict
    try:
        with open(PRESETS_FILE, "w") as f:
            json.dump(presets, f, indent=2)
        return True
    except Exception as e:
        logger.warning(f"Failed to save preset '{name}' to custom presets file {PRESETS_FILE}: {e}", exc_info=True)
        return False

def delete_custom_preset(name):
    presets = {}
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r") as f:
                presets = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load presets file prior to deleting preset '{name}': {e}", exc_info=True)
    if name in presets:
        del presets[name]
        try:
            with open(PRESETS_FILE, "w") as f:
                json.dump(presets, f, indent=2)
            return True
        except Exception as e:
            logger.warning(f"Failed to save custom presets file after deleting preset '{name}': {e}", exc_info=True)
            return False
    return False

def load_emoji_map():
    if not os.path.exists(EMOJIS_FILE):
        try:
            with open(EMOJIS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_EMOJI_MAP, f, indent=4, ensure_ascii=False)
            return DEFAULT_EMOJI_MAP
        except Exception as e:
            logger.warning(f"Failed to create default emoji map file at {EMOJIS_FILE}: {e}", exc_info=True)
            return DEFAULT_EMOJI_MAP
    try:
        with open(EMOJIS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load emoji map from {EMOJIS_FILE}: {e}", exc_info=True)
        return DEFAULT_EMOJI_MAP

def save_emoji_map(emoji_map):
    try:
        with open(EMOJIS_FILE, "w", encoding="utf-8") as f:
            json.dump(emoji_map, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.warning(f"Failed to save emoji map to {EMOJIS_FILE}: {e}", exc_info=True)
        return False

def load_settings():
    # Load defaults from the template file if it exists
    defaults = {}
    template_file = os.path.join(CONFIG_DIR, "settings.json.template")
    if os.path.exists(template_file):
        try:
            with open(template_file, "r") as f:
                defaults = json.load(f)
                if defaults.get("api_key") == "YOUR_API_KEY_HERE":
                    defaults["api_key"] = ""
        except Exception as e:
            logger.warning(f"Failed to load defaults from template {template_file}: {e}", exc_info=True)

    # Initialize settings with defaults
    settings.clear()
    settings.update(defaults)

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                new_settings = json.load(f)
                settings.update(new_settings)
        except Exception as e:
            logger.warning(f"Failed to load settings from {SETTINGS_FILE}: {e}", exc_info=True)
    else:
        # Create settings file with the default populated keys if it does not exist
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write default settings to {SETTINGS_FILE}: {e}", exc_info=True)
            
    return settings

def save_settings(settings_dict):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings_dict, f, indent=2)
        if settings is not settings_dict:
            settings.clear()
            settings.update(settings_dict)
        return True
    except Exception as e:
        logger.warning(f"Failed to save settings to {SETTINGS_FILE}: {e}", exc_info=True)
        return False

