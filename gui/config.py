import atexit
import json
import logging
import multiprocessing
import os
from logging.handlers import RotatingFileHandler

import sentry_sdk
from rich.console import Console

from gui.state import settings

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

BUILTIN_PRESETS = {
    "Split-Screen Chill (Yellow Highlight)": {
        "name": "Split-Screen Chill (Yellow Highlight)",
        "selected_voice": "am_michael",
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
        "enable_emojis": True,
        "enable_emoji_animation": True,
        "emoji_scale_factor": 1.5,
        "emoji_hold_duration": 0.5,
        "emoji_throw_max_count": 3,
    },
    "Lofi Storyteller (Cyan Highlight)": {
        "name": "Lofi Storyteller (Cyan Highlight)",
        "selected_voice": "af_sarah",
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
        "enable_emojis": True,
        "enable_emoji_animation": True,
        "emoji_scale_factor": 1.5,
        "emoji_hold_duration": 0.5,
        "emoji_throw_max_count": 3,
    },
    "Fast-Paced Promo (Magenta Highlight)": {
        "name": "Fast-Paced Promo (Magenta Highlight)",
        "selected_voice": "am_adam",
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
        "enable_emojis": True,
        "enable_emoji_animation": True,
        "emoji_scale_factor": 1.5,
        "emoji_hold_duration": 0.5,
        "emoji_throw_max_count": 3,
    },
    "TikTok Kinetic Pop (Green Highlight)": {
        "name": "TikTok Kinetic Pop (Green Highlight)",
        "selected_voice": "af_bella",
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
        "enable_emojis": True,
        "enable_emoji_animation": True,
        "emoji_scale_factor": 1.5,
        "emoji_hold_duration": 0.5,
        "emoji_throw_max_count": 3,
    },
    "Retro Synthwave (Purple Highlight)": {
        "name": "Retro Synthwave (Purple Highlight)",
        "selected_voice": "bf_emma",
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
        "enable_emojis": True,
        "enable_emoji_animation": True,
        "emoji_scale_factor": 1.5,
        "emoji_hold_duration": 0.5,
        "emoji_throw_max_count": 3,
    },
    "Cinematic Documentary (Gold Highlight)": {
        "name": "Cinematic Documentary (Gold Highlight)",
        "selected_voice": "bm_george",
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
        "enable_emojis": False,
        "enable_emoji_animation": True,
        "emoji_scale_factor": 1.5,
        "emoji_hold_duration": 0.5,
        "emoji_throw_max_count": 3,
    },
    "Cyberpunk Red (Red Highlight)": {
        "name": "Cyberpunk Red (Red Highlight)",
        "selected_voice": "am_michael",
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
        "enable_emojis": False,
        "enable_emoji_animation": True,
        "emoji_scale_factor": 1.5,
        "emoji_hold_duration": 0.5,
        "emoji_throw_max_count": 3,
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
        "enable_emojis": True,
        "enable_emoji_animation": True,
        "emoji_scale_factor": 1.5,
        "emoji_hold_duration": 0.5,
        "emoji_throw_max_count": 3,
    },
}

DEFAULT_EMOJI_MAP = {
    "science": {"emoji": "🧪", "anim": "fade"},
    "scientific": {"emoji": "🧪", "anim": "fade"},
    "scientist": {"emoji": "🧪", "anim": "fade"},
    "physics": {"emoji": "⚛️", "anim": "fade"},
    "chemistry": {"emoji": "🧪", "anim": "fade"},
    "biology": {"emoji": "🧬", "anim": "fade"},
    "space": {"emoji": "🌌", "anim": "float_up"},
    "planet": {"emoji": "🪐", "anim": "float_up"},
    "star": {"emoji": "⭐", "anim": "pop_in"},
    "earth": {"emoji": "🌍", "anim": "fade"},
    "moon": {"emoji": "🌙", "anim": "float_up"},
    "sun": {"emoji": "☀️", "anim": "bounce"},
    "universe": {"emoji": "🌌", "anim": "float_up"},
    "galaxy": {"emoji": "🌌", "anim": "float_up"},
    "alien": {"emoji": "👽", "anim": "float_up"},
    "ufo": {"emoji": "🛸", "anim": "float_up"},
    "fact": {"emoji": "💡", "anim": "fade"},
    "facts": {"emoji": "💡", "anim": "fade"},
    "real": {"emoji": "✅", "anim": "pop_in"},
    "fake": {"emoji": "❌", "anim": "pop_in"},
    "true": {"emoji": "💯", "anim": "pop_in"},
    "false": {"emoji": "🚫", "anim": "pop_in"},
    "nature": {"emoji": "🌿", "anim": "fade"},
    "animal": {"emoji": "🐾", "anim": "fade"},
    "water": {"emoji": "💧", "anim": "fade"},
    "fire": {"emoji": "🔥", "anim": "bounce"},
    "ice": {"emoji": "❄️", "anim": "fade"},
    "history": {"emoji": "📜", "anim": "fade"},
    "historical": {"emoji": "📜", "anim": "fade"},
    "ancient": {"emoji": "🏛️", "anim": "fade"},
    "empire": {"emoji": "👑", "anim": "pop_in"},
    "king": {"emoji": "👑", "anim": "pop_in"},
    "queen": {"emoji": "👑", "anim": "pop_in"},
    "war": {"emoji": "⚔️", "anim": "shake"},
    "battle": {"emoji": "⚔️", "anim": "shake"},
    "soldier": {"emoji": "🪖", "anim": "shake"},
    "mystery": {"emoji": "❓", "anim": "fade"},
    "mysterious": {"emoji": "❓", "anim": "fade"},
    "secret": {"emoji": "🤫", "anim": "float_up"},
    "secrets": {"emoji": "🤫", "anim": "float_up"},
    "lost": {"emoji": "😵‍💫", "anim": "fade"},
    "find": {"emoji": "🔍", "anim": "fade"},
    "found": {"emoji": "🔍", "anim": "fade"},
    "search": {"emoji": "🔎", "anim": "fade"},
    "gold": {"emoji": "🪙", "anim": "pop_in"},
    "treasure": {"emoji": "💎", "anim": "pop_in"},
    "pirate": {"emoji": "🏴‍☠️", "anim": "pop_in"},
    "scary": {"emoji": "😨", "anim": "shake"},
    "creepy": {"emoji": "😰", "anim": "float_up"},
    "ghost": {"emoji": "👻", "anim": "float_up"},
    "dark": {"emoji": "🌑", "anim": "fade"},
    "phone": {"emoji": "📱", "anim": "bounce"},
    "call": {"emoji": "📞", "anim": "bounce"},
    "text": {"emoji": "💬", "anim": "bounce"},
    "message": {"emoji": "✉️", "anim": "bounce"},
    "number": {"emoji": "🔢", "anim": "bounce"},
    "cry": {"emoji": "😭", "anim": "fade"},
    "scream": {"emoji": "😱", "anim": "shake"},
    "run": {"emoji": "🏃", "anim": "bounce"},
    "fear": {"emoji": "😨", "anim": "shake"},
    "dead": {"emoji": "💀", "anim": "shake"},
    "death": {"emoji": "💀", "anim": "shake"},
    "kill": {"emoji": "🔪", "anim": "shake"},
    "killer": {"emoji": "🔪", "anim": "shake"},
    "blood": {"emoji": "🩸", "anim": "shake"},
    "night": {"emoji": "🌃", "anim": "float_up"},
    "shadow": {"emoji": "👤", "anim": "fade"},
    "monster": {"emoji": "👹", "anim": "shake"},
    "demon": {"emoji": "😈", "anim": "shake"},
    "money": {"emoji": "💵", "anim": "pop_in"},
    "rich": {"emoji": "🤑", "anim": "pop_in"},
    "poor": {"emoji": "💸", "anim": "pop_in"},
    "buy": {"emoji": "🛒", "anim": "pop_in"},
    "sell": {"emoji": "🏷️", "anim": "pop_in"},
    "dollar": {"emoji": "💵", "anim": "pop_in"},
    "dollars": {"emoji": "💵", "anim": "pop_in"},
    "cash": {"emoji": "💰", "anim": "pop_in"},
    "wealth": {"emoji": "💎", "anim": "pop_in"},
    "business": {"emoji": "💼", "anim": "pop_in"},
    "job": {"emoji": "💼", "anim": "pop_in"},
    "boss": {"emoji": "👔", "anim": "pop_in"},
    "office": {"emoji": "🏢", "anim": "pop_in"},
    "motivation": {"emoji": "🔥", "anim": "bounce"},
    "success": {"emoji": "🏆", "anim": "pop_in"},
    "lazy": {"emoji": "🛌", "anim": "fade"},
    "procrastinate": {"emoji": "⏳", "anim": "bounce"},
    "procrastination": {"emoji": "⏳", "anim": "bounce"},
    "work": {"emoji": "⚙️", "anim": "bounce"},
    "life": {"emoji": "🌱", "anim": "bounce"},
    "hack": {"emoji": "💡", "anim": "fade"},
    "hacks": {"emoji": "💡", "anim": "fade"},
    "morning": {"emoji": "🌅", "anim": "bounce"},
    "routine": {"emoji": "📅", "anim": "bounce"},
    "habit": {"emoji": "🔁", "anim": "bounce"},
    "habits": {"emoji": "🔁", "anim": "bounce"},
    "clock": {"emoji": "⏰", "anim": "bounce"},
    "time": {"emoji": "⏱️", "anim": "bounce"},
    "hour": {"emoji": "⏳", "anim": "bounce"},
    "day": {"emoji": "☀️", "anim": "bounce"},
    "school": {"emoji": "🏫", "anim": "fade"},
    "student": {"emoji": "🎓", "anim": "fade"},
    "learn": {"emoji": "📚", "anim": "fade"},
    "study": {"emoji": "📖", "anim": "fade"},
    "brain": {"emoji": "🧠", "anim": "fade"},
    "mind": {"emoji": "🧠", "anim": "fade"},
    "focus": {"emoji": "🎯", "anim": "bounce"},
    "goal": {"emoji": "🥅", "anim": "pop_in"},
    "win": {"emoji": "🥇", "anim": "pop_in"},
    "lose": {"emoji": "❌", "anim": "pop_in"},
    "computer": {"emoji": "💻", "anim": "bounce"},
    "internet": {"emoji": "🌐", "anim": "bounce"},
    "code": {"emoji": "💻", "anim": "bounce"},
    "ai": {"emoji": "🤖", "anim": "bounce"},
    "robot": {"emoji": "🤖", "anim": "bounce"},
    "game": {"emoji": "🎮", "anim": "bounce"},
    "gaming": {"emoji": "🎮", "anim": "bounce"},
    "play": {"emoji": "▶️", "anim": "bounce"},
    "music": {"emoji": "🎵", "anim": "bounce"},
    "song": {"emoji": "🎶", "anim": "bounce"},
    "video": {"emoji": "📹", "anim": "bounce"},
    "photo": {"emoji": "📷", "anim": "bounce"},
    "love": {"emoji": "❤️", "anim": "pop_in"},
    "friend": {"emoji": "🤝", "anim": "fade"},
    "people": {"emoji": "👥", "anim": "fade"},
    "man": {"emoji": "👨", "anim": "fade"},
    "woman": {"emoji": "👩", "anim": "fade"},
    "food": {"emoji": "🍔", "anim": "bounce"},
    "drink": {"emoji": "🥤", "anim": "bounce"},
    "coffee": {"emoji": "☕", "anim": "bounce"},
    "car": {"emoji": "🚗", "anim": "fade"},
    "plane": {"emoji": "✈️", "anim": "fade"},
    "house": {"emoji": "🏠", "anim": "fade"},
    "home": {"emoji": "🏠", "anim": "fade"},
    "city": {"emoji": "🏙️", "anim": "fade"},
    "world": {"emoji": "🌐", "anim": "fade"},
    "doctor": {"emoji": "👨‍⚕️", "anim": "shake"},
    "nurse": {"emoji": "👩‍⚕️", "anim": "shake"},
    "hospital": {"emoji": "🏥", "anim": "shake"},
    "medicine": {"emoji": "💊", "anim": "shake"},
    "pill": {"emoji": "💊", "anim": "shake"},
    "sick": {"emoji": "🤒", "anim": "shake"},
    "ill": {"emoji": "🤒", "anim": "shake"},
    "disease": {"emoji": "🦠", "anim": "shake"},
    "virus": {"emoji": "🦠", "anim": "shake"},
    "healthy": {"emoji": "💪", "anim": "shake"},
    "health": {"emoji": "❤️‍🩹", "anim": "shake"},
    "exercise": {"emoji": "🏋️", "anim": "bounce"},
    "gym": {"emoji": "🏋️", "anim": "bounce"},
    "workout": {"emoji": "🏋️", "anim": "bounce"},
    "injury": {"emoji": "🤕", "anim": "shake"},
    "pain": {"emoji": "😖", "anim": "shake"},
    "surgery": {"emoji": "🩺", "anim": "shake"},
    "tooth": {"emoji": "🦷", "anim": "shake"},
    "athlete": {"emoji": "🏃", "anim": "bounce"},
    "champion": {"emoji": "🏆", "anim": "pop_in"},
    "competition": {"emoji": "🤼", "anim": "shake"},
    "compete": {"emoji": "🤼", "anim": "shake"},
    "race": {"emoji": "🏁", "anim": "bounce"},
    "fight": {"emoji": "🤼‍♂️", "anim": "shake"},
    "strong": {"emoji": "💪", "anim": "bounce"},
    "football": {"emoji": "🏈", "anim": "bounce"},
    "basketball": {"emoji": "🏀", "anim": "bounce"},
    "soccer": {"emoji": "⚽", "anim": "bounce"},
    "tennis": {"emoji": "🎾", "anim": "bounce"},
    "baseball": {"emoji": "⚾", "anim": "bounce"},
    "boxing": {"emoji": "🥊", "anim": "shake"},
    "medal": {"emoji": "🥇", "anim": "pop_in"},
    "coach": {"emoji": "🧢", "anim": "bounce"},
    "trainer": {"emoji": "🧢", "anim": "bounce"},
    "happy": {"emoji": "😊", "anim": "bounce"},
    "sad": {"emoji": "😢", "anim": "fade"},
    "angry": {"emoji": "😡", "anim": "shake"},
    "anger": {"emoji": "😡", "anim": "shake"},
    "mad": {"emoji": "😡", "anim": "shake"},
    "surprised": {"emoji": "😲", "anim": "pop_in"},
    "shocked": {"emoji": "😱", "anim": "shake"},
    "laugh": {"emoji": "😂", "anim": "bounce"},
    "funny": {"emoji": "😂", "anim": "bounce"},
    "joke": {"emoji": "🤣", "anim": "bounce"},
    "crazy": {"emoji": "🤪", "anim": "bounce"},
    "confused": {"emoji": "😕", "anim": "fade"},
    "tired": {"emoji": "😩", "anim": "fade"},
    "exhausted": {"emoji": "😫", "anim": "fade"},
    "stressed": {"emoji": "😰", "anim": "shake"},
    "calm": {"emoji": "🧘", "anim": "fade"},
    "relax": {"emoji": "🧘", "anim": "fade"},
    "nervous": {"emoji": "😬", "anim": "shake"},
    "awkward": {"emoji": "😬", "anim": "shake"},
    "proud": {"emoji": "😌", "anim": "fade"},
    "embarrassed": {"emoji": "😳", "anim": "fade"},
    "shy": {"emoji": "🤭", "anim": "fade"},
    "bored": {"emoji": "🥱", "anim": "fade"},
    "lonely": {"emoji": "🥺", "anim": "fade"},
    "police": {"emoji": "👮", "anim": "shake"},
    "cop": {"emoji": "👮", "anim": "shake"},
    "lawyer": {"emoji": "⚖️", "anim": "shake"},
    "court": {"emoji": "⚖️", "anim": "shake"},
    "judge": {"emoji": "⚖️", "anim": "shake"},
    "prison": {"emoji": "⛓️", "anim": "shake"},
    "jail": {"emoji": "⛓️", "anim": "shake"},
    "thief": {"emoji": "🥷", "anim": "shake"},
    "steal": {"emoji": "🥷", "anim": "shake"},
    "stolen": {"emoji": "🥷", "anim": "shake"},
    "crime": {"emoji": "🔫", "anim": "shake"},
    "criminal": {"emoji": "⛓️", "anim": "shake"},
    "trial": {"emoji": "⚖️", "anim": "shake"},
    "arrest": {"emoji": "🚔", "anim": "shake"},
    "witness": {"emoji": "👀", "anim": "fade"},
    "lie": {"emoji": "🤥", "anim": "fade"},
    "liar": {"emoji": "🤥", "anim": "fade"},
    "innocent": {"emoji": "😇", "anim": "fade"},
    "guilty": {"emoji": "😈", "anim": "shake"},
    "family": {"emoji": "👨‍👩‍👧‍👦", "anim": "pop_in"},
    "baby": {"emoji": "👶", "anim": "pop_in"},
    "child": {"emoji": "🧒", "anim": "pop_in"},
    "parent": {"emoji": "👨‍👩‍👧", "anim": "pop_in"},
    "mother": {"emoji": "👩‍👧", "anim": "pop_in"},
    "father": {"emoji": "👨‍👧", "anim": "pop_in"},
    "mom": {"emoji": "👩‍👧", "anim": "pop_in"},
    "dad": {"emoji": "👨‍👧", "anim": "pop_in"},
    "wedding": {"emoji": "💍", "anim": "pop_in"},
    "married": {"emoji": "💍", "anim": "pop_in"},
    "couple": {"emoji": "💑", "anim": "pop_in"},
    "kiss": {"emoji": "💋", "anim": "pop_in"},
    "hug": {"emoji": "🤗", "anim": "pop_in"},
    "pet": {"emoji": "🐶", "anim": "bounce"},
    "dog": {"emoji": "🐶", "anim": "bounce"},
    "cat": {"emoji": "🐱", "anim": "bounce"},
    "broken": {"emoji": "💔", "anim": "shake"},
    "cheat": {"emoji": "🃏", "anim": "shake"},
    "alone": {"emoji": "🧍", "anim": "fade"},
    "storm": {"emoji": "🌩️", "anim": "shake"},
    "thunder": {"emoji": "⛈️", "anim": "shake"},
    "lightning": {"emoji": "⚡", "anim": "shake"},
    "rain": {"emoji": "🌧️", "anim": "fade"},
    "snowy": {"emoji": "🌨️", "anim": "float_up"},
    "tornado": {"emoji": "🌪️", "anim": "shake"},
    "wind": {"emoji": "💨", "anim": "float_up"},
    "rainbow": {"emoji": "🌈", "anim": "fade"},
    "flood": {"emoji": "🌊", "anim": "shake"},
    "disaster": {"emoji": "☄️", "anim": "shake"},
    "cloud": {"emoji": "☁️", "anim": "float_up"},
    "fog": {"emoji": "🌫️", "anim": "fade"},
    "volcano": {"emoji": "🌋", "anim": "shake"},
    "luck": {"emoji": "🍀", "anim": "pop_in"},
    "lucky": {"emoji": "🍀", "anim": "pop_in"},
    "magic": {"emoji": "✨", "anim": "pop_in"},
    "magical": {"emoji": "✨", "anim": "pop_in"},
    "dream": {"emoji": "💭", "anim": "float_up"},
    "nightmare": {"emoji": "👹", "anim": "shake"},
    "fate": {"emoji": "🔮", "anim": "fade"},
    "destiny": {"emoji": "🔮", "anim": "fade"},
    "miracle": {"emoji": "🙏", "anim": "fade"},
    "legendary": {"emoji": "🏆", "anim": "pop_in"},
    "myth": {"emoji": "🐉", "anim": "fade"},
    "fantasy": {"emoji": "🦄", "anim": "float_up"},
    "dragon": {"emoji": "🐉", "anim": "shake"},
    "unicorn": {"emoji": "🦄", "anim": "pop_in"},
    "castle": {"emoji": "🏰", "anim": "fade"},
    "hero": {"emoji": "🦸", "anim": "pop_in"},
    "villain": {"emoji": "🦹", "anim": "shake"},
    "brave": {"emoji": "🦁", "anim": "bounce"},
    "art": {"emoji": "🎨", "anim": "fade"},
    "paint": {"emoji": "🖌️", "anim": "fade"},
    "draw": {"emoji": "✍️", "anim": "fade"},
    "design": {"emoji": "🎨", "anim": "fade"},
    "creative": {"emoji": "💡", "anim": "bounce"},
    "imagine": {"emoji": "💭", "anim": "fade"},
    "write": {"emoji": "✍️", "anim": "fade"},
    "story": {"emoji": "📖", "anim": "fade"},
    "author": {"emoji": "✍️", "anim": "fade"},
    "poem": {"emoji": "📝", "anim": "fade"},
    "poetry": {"emoji": "📝", "anim": "fade"},
    "theater": {"emoji": "🎭", "anim": "fade"},
    "stage": {"emoji": "🎭", "anim": "fade"},
    "drama": {"emoji": "🎭", "anim": "shake"},
    "pizza": {"emoji": "🍕", "anim": "bounce"},
    "sushi": {"emoji": "🍣", "anim": "bounce"},
    "cake": {"emoji": "🎂", "anim": "pop_in"},
    "wine": {"emoji": "🍷", "anim": "bounce"},
    "beer": {"emoji": "🍺", "anim": "bounce"},
    "fruit": {"emoji": "🍎", "anim": "bounce"},
    "sweet": {"emoji": "🍬", "anim": "bounce"},
    "spicy": {"emoji": "🌶️", "anim": "shake"},
    "cook": {"emoji": "👨‍🍳", "anim": "bounce"},
    "chef": {"emoji": "👨‍🍳", "anim": "bounce"},
    "restaurant": {"emoji": "🍽️", "anim": "bounce"},
    "hungry": {"emoji": "🤤", "anim": "fade"},
    "taste": {"emoji": "👅", "anim": "bounce"},
    "delicious": {"emoji": "😋", "anim": "bounce"},
    "adventure": {"emoji": "🧭", "anim": "bounce"},
    "explore": {"emoji": "🔍", "anim": "fade"},
    "discover": {"emoji": "🔍", "anim": "fade"},
    "beach": {"emoji": "🏖️", "anim": "fade"},
    "mountain": {"emoji": "🏔️", "anim": "float_up"},
    "island": {"emoji": "🏝️", "anim": "fade"},
    "trip": {"emoji": "🧳", "anim": "fade"},
    "vacation": {"emoji": "🌴", "anim": "fade"},
    "camp": {"emoji": "🏕️", "anim": "fade"},
    "hike": {"emoji": "🥾", "anim": "bounce"},
    "hiking": {"emoji": "🥾", "anim": "bounce"},
    "ocean": {"emoji": "🌊", "anim": "bounce"},
    "forest": {"emoji": "🌲", "anim": "fade"},
    "river": {"emoji": "🏞️", "anim": "fade"},
    "desert": {"emoji": "🏜️", "anim": "shake"},
    "passport": {"emoji": "🛂", "anim": "fade"},
    "compass": {"emoji": "🧭", "anim": "fade"},
    "travel": {"emoji": "✈️", "anim": "fade"},
    "traveler": {"emoji": "🧳", "anim": "fade"},
    "dance": {"emoji": "💃", "anim": "bounce"},
    "dancer": {"emoji": "💃", "anim": "bounce"},
    "party": {"emoji": "🎉", "anim": "pop_in"},
    "celebrate": {"emoji": "🥳", "anim": "pop_in"},
    "celebration": {"emoji": "🎊", "anim": "pop_in"},
    "fashion": {"emoji": "👗", "anim": "fade"},
    "beauty": {"emoji": "💄", "anim": "fade"},
    "pray": {"emoji": "🙏", "anim": "fade"},
    "prayer": {"emoji": "🙏", "anim": "fade"},
    "bless": {"emoji": "✨", "anim": "fade"},
    "blessed": {"emoji": "✨", "anim": "fade"},
    "curse": {"emoji": "🤬", "anim": "shake"},
    "cursed": {"emoji": "😈", "anim": "shake"},
    "haunted": {"emoji": "🏚️", "anim": "shake"},
    "future": {"emoji": "🔮", "anim": "float_up"},
    "past": {"emoji": "⌛", "anim": "fade"},
    "energy": {"emoji": "⚡", "anim": "shake"},
    "energetic": {"emoji": "⚡", "anim": "shake"},
    "soul": {"emoji": "🕊️", "anim": "float_up"},
    "spirit": {"emoji": "✨", "anim": "float_up"},
    "spiritual": {"emoji": "🕯️", "anim": "fade"},
    "devil": {"emoji": "😈", "anim": "shake"},
    "angel": {"emoji": "😇", "anim": "fade"},
    "warrior": {"emoji": "⚔️", "anim": "shake"},
    "hunt": {"emoji": "🏹", "anim": "shake"},
    "hunter": {"emoji": "🏹", "anim": "shake"},
    "smile": {"emoji": "😊", "anim": "bounce"},
    "grin": {"emoji": "😁", "anim": "bounce"},
    "afraid": {"emoji": "😨", "anim": "shake"},
    "terrified": {"emoji": "😱", "anim": "shake"},
    "protect": {"emoji": "🛡️", "anim": "fade"},
    "protection": {"emoji": "🛡️", "anim": "fade"},
    "build": {"emoji": "🔧", "anim": "bounce"},
    "builder": {"emoji": "👷", "anim": "bounce"},
    "grow": {"emoji": "🌱", "anim": "float_up"},
    "growth": {"emoji": "📈", "anim": "float_up"},
    "fly": {"emoji": "🕊️", "anim": "float_up"},
    "swim": {"emoji": "🏊", "anim": "bounce"},
    "read": {"emoji": "📖", "anim": "fade"},
    "sing": {"emoji": "🎤", "anim": "bounce"},
    "singer": {"emoji": "🎤", "anim": "bounce"},
    "style": {"emoji": "💅", "anim": "fade"},
    "tears": {"emoji": "😭", "anim": "fade"},
}


def load_presets():
    presets = BUILTIN_PRESETS.copy()
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE) as f:
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
            with open(PRESETS_FILE) as f:
                presets = json.load(f)
        except Exception as e:
            logger.warning(
                f"Failed to load presets file prior to saving preset '{name}': {e}", exc_info=True
            )
    presets[name] = preset_dict
    try:
        with open(PRESETS_FILE, "w") as f:
            json.dump(presets, f, indent=2)
        return True
    except Exception as e:
        logger.warning(
            f"Failed to save preset '{name}' to custom presets file {PRESETS_FILE}: {e}",
            exc_info=True,
        )
        return False


def delete_custom_preset(name):
    presets = {}
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE) as f:
                presets = json.load(f)
        except Exception as e:
            logger.warning(
                f"Failed to load presets file prior to deleting preset '{name}': {e}", exc_info=True
            )
    if name in presets:
        del presets[name]
        try:
            with open(PRESETS_FILE, "w") as f:
                json.dump(presets, f, indent=2)
            return True
        except Exception as e:
            logger.warning(
                f"Failed to save custom presets file after deleting preset '{name}': {e}",
                exc_info=True,
            )
            return False
    return False


def _normalize_emoji_map(raw_map: dict) -> dict:
    """Normalize emoji_map entries so each value is a dict with 'emoji' and 'anim' keys."""
    normalized = {}
    for key, value in raw_map.items():
        if isinstance(value, str):
            normalized[key] = {"emoji": value, "anim": "none"}
        elif isinstance(value, dict):
            normalized[key] = {
                "emoji": value.get("emoji", "❓"),
                "anim": value.get("anim", "none"),
            }
        else:
            normalized[key] = {"emoji": str(value), "anim": "none"}
    return normalized


def load_emoji_map() -> dict:
    if not os.path.exists(EMOJIS_FILE):
        try:
            with open(EMOJIS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_EMOJI_MAP, f, indent=4, ensure_ascii=False)
            return _normalize_emoji_map(DEFAULT_EMOJI_MAP)
        except Exception as e:
            logger.warning(
                f"Failed to create default emoji map file at {EMOJIS_FILE}: {e}", exc_info=True
            )
            return _normalize_emoji_map(DEFAULT_EMOJI_MAP)
    try:
        with open(EMOJIS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
            return _normalize_emoji_map(raw)
    except Exception as e:
        logger.warning(f"Failed to load emoji map from {EMOJIS_FILE}: {e}", exc_info=True)
        return _normalize_emoji_map(DEFAULT_EMOJI_MAP)


def save_emoji_map(emoji_map: dict) -> bool:
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
            with open(template_file) as f:
                defaults = json.load(f)
                if defaults.get("api_key") == "YOUR_API_KEY_HERE":
                    defaults["api_key"] = ""
        except Exception as e:
            logger.warning(
                f"Failed to load defaults from template {template_file}: {e}", exc_info=True
            )

    # Build new settings dict first, then atomically swap
    new = {}
    new.update(defaults)

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                new_settings = json.load(f)
                new.update(new_settings)
        except Exception as e:
            logger.warning(f"Failed to load settings from {SETTINGS_FILE}: {e}", exc_info=True)

    settings.clear()
    settings.update(new)

    # Auto-migrate legacy LLM config
    if "llm_profiles" not in settings:
        settings["llm_profiles"] = []

    has_legacy_keys = any(k in settings for k in ["api_key", "base_url", "model"])
    if has_legacy_keys and not settings.get("llm_profiles"):
        import uuid

        profile_id = str(uuid.uuid4())
        settings["llm_profiles"].append(
            {
                "id": profile_id,
                "name": "Default Profile",
                "api_key": settings.get("api_key", ""),
                "base_url": settings.get("base_url", ""),
                "model": settings.get("model", "gpt-4o-mini"),
            }
        )
        settings["active_llm_profile_id"] = profile_id

    # Clean up legacy keys
    migrated = False
    for k in ["api_key", "base_url", "model"]:
        if k in settings:
            del settings[k]
            migrated = True

    if migrated:
        save_settings(settings)

    elif not os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.warning(
                f"Failed to write default settings to {SETTINGS_FILE}: {e}", exc_info=True
            )

    sentry_dsn = settings.get("sentry_dsn")
    if sentry_dsn:
        import multiprocessing

        if multiprocessing.current_process().name == "MainProcess":
            try:
                sentry_sdk.init(dsn=sentry_dsn, traces_sample_rate=1.0, profiles_sample_rate=1.0)
            except Exception as e:
                logger.error(f"Failed to initialize Sentry: {e}")

    return settings


def save_settings(settings_dict):
    # Prevent accidentally wiping llm_profiles — if the incoming dict has no
    # profiles but the in-memory settings (or disk) do, preserve the existing ones.
    incoming = settings_dict.get("llm_profiles")
    if not incoming:
        existing = settings.get("llm_profiles", [])
        if not existing:
            try:
                with open(SETTINGS_FILE) as f:
                    disk = json.load(f)
                    existing = disk.get("llm_profiles", [])
            except Exception:
                pass
        if existing:
            settings_dict["llm_profiles"] = existing
            settings_dict["active_llm_profile_id"] = (
                settings_dict.get("active_llm_profile_id")
                or settings.get("active_llm_profile_id")
                or (existing[0].get("id") if existing else "")
            )

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


DEFAULT_SCRIPT_SYSTEM_PROMPT = (
    "You are an elite TikTok and YouTube Shorts scriptwriter known for creating viral, high-retention content. "
    "Write a highly engaging vertical video script based on the user's topic.\n\n"
    "Strict Guidelines:\n"
    "1. The Hook (First 5-10s): Start immediately with a scroll-stopping statement, provocative question, or intriguing hook that grabs attention. No slow introductions.\n"
    "2. Story Arc: Structure with a clear narrative arc — setup, rising tension or details, and a strong payoff or conclusion. Use rich details and examples to make the content compelling.\n"
    "3. Length: Aim for approximately {max_words} words (approx. {max_words_seconds} seconds when spoken). This is a medium-to-long Short so pace the story naturally.\n"
    "4. Pacing: Vary sentence length. Use short punchy lines for impact and longer descriptive sentences for storytelling. Build momentum toward key reveals.\n"
    "5. Tone: Sound authentic and human — conversational but informed. Avoid robotic, academic, or overly dramatic AI clichés.\n"
    "6. Formatting: Output ONLY the exact spoken words. Do NOT include stage directions, timestamps, speaker tags, or brackets (e.g., no [Music], [Host], or [Visuals]).\n"
    "7. Chunks: Group every 2-4 sentences into a natural spoken chunk and separate each chunk with a blank line (\\n\\n). This improves voice audio quality significantly — do not skip this.\n"
    "8. Source: Never mention Reddit, subreddits, or forums. Tell the story directly as if it happened to someone."
)

DEFAULT_PROMPTS = {
    "History's Coolest Coincidences": "Tell the story of one of the most unbelievable coincidences in history that shaped the world.",
    "Space Is Way Bigger Than You Think": "Explain the scale of the universe using mind-bending analogies that will make the viewer feel tiny.",
    "Signs of High Intelligence": "Highlight 3 unusual behavioral traits or habits that are scientifically linked to high intelligence.",
    "The Mandela Effect Cases": "Explain the Mandela Effect and share 3 famous examples that will make viewers question their own memory.",
    "Unusual Jobs That Pay Well": "Introduce 3 weird or lesser-known jobs that pay surprisingly high salaries.",
    "How To Read Body Language": "Teach 3 quick tips to read someone's body language instantly, like detecting if they are lying or interested.",
    "Hidden Easter Eggs in Famous Art": "Reveal 3 hidden messages or secrets painted into famous historical artworks like the Mona Lisa or The Last Supper.",
    "The Origin of Common Phrases": "Explain the fascinating, sometimes dark origins of 3 everyday phrases we use without thinking.",
    "Why Time Feels Faster as We Age": "Explain the psychological theory of why years seem to speed up as we grow older, and how to slow it down.",
    "Incredible Animal Superpowers": "Describe 3 animals with incredible, real-life superpowers that seem straight out of comic books.",
    "Quick Memory Improvement Tricks": "Teach 2 memory techniques (like the Memory Palace) that anyone can use to remember lists or names instantly.",
    "Fascinating Psychological Phenomena": "Explain a strange psychological phenomenon, like the Baader-Meinhof phenomenon or Placebo Effect, with a cool example.",
    "Bizarre Science Theories": "Explain a mind-bending, scientifically plausible physics or cosmological theory (like the simulation hypothesis or multiverse) in a simple way.",
    "Ancient Mythological Beasts": "Describe 3 of the most terrifying or fascinating mythical creatures from ancient folklore and their origins.",
    "Stoicism & Mental Toughness": "Explain how to apply the ancient philosophy of Stoicism to manage modern stress and build mental resilience.",
    "How Caffeine Affects Your Brain": "Explain the science of what caffeine actually does to your brain and how to optimize your coffee intake.",
    "Hidden Symbols in Famous Logos": "Reveal the hidden meanings or visual secrets behind 3 famous company logos.",
    "History of the Internet": "Explain a surprising, lesser-known story about how the internet was created or its earliest days.",
    "The Betrayal That Ended an Empire": "Tell the dramatic story of Julius Caesar and Marcus Brutus, focusing on the ultimate betrayal and its shocking consequences.",
    "Hollywood's Most Dramatic Feud": "Describe the intense, decade-long rivalry between Joan Crawford and Bette Davis, and the lengths they went to sabotage each other.",
    "The Most Dramatic Royalty Scandal": "Tell the story of Edward VIII's decision to abdicate the British throne for Wallis Simpson, and the national crisis that followed.",
    "Behind the Scenes Theater Drama": "Tell the historical, dramatic story of the Astor Place Riot of 1849, where a rivalry between two Shakespearean actors led to actual violence in the streets of New York.",
    "The Mystery of the Missing Heiress": "Narrate the mysterious and dramatic disappearance of Dorothy Arnold in 1910, highlighting the shocking theories and family secrets.",
    "Famous Art World Rivals": "Describe the dramatic rivalry between Leonardo da Vinci and Michelangelo, and how their mutual dislike fueled some of the greatest art in history.",
    "The War of the Currents": "Tell the dramatic story of the brutal battle between Thomas Edison and Nikola Tesla over AC vs DC electricity, and the shocking PR stunts used to win.",
    "The Curse of Tutankhamun": "Narrate the drama and mystery surrounding the opening of King Tut's tomb in 1922, highlighting the tragic fates of those involved.",
    "The Poison Cup Duel": "Tell the dramatic, legendary story of the duel between two Renaissance doctors who tried to poison each other to prove whose antidote was superior.",
    "The Shipwreck of the Medusa": "Describe the harrowing, dramatic survival story of the French frigate Méduse in 1816, and the scandalous government cover-up that followed.",
    "The Duel of the Century": "Tell the intense, dramatic story of the fatal 1804 duel between Alexander Hamilton and Aaron Burr, focusing on the decades-long rivalry that led to it.",
    "Reddit AITA Wedding Drama": "Write a dramatic Reddit-style 'Am I the Asshole' post about a bride who cancels her wedding at the altar after finding out a secret about her groom from the maid of honor.",
    "Reddit Secret Inheritance": "Write a dramatic Reddit post from a user who discovered their late grandfather left a massive secret inheritance to them instead of their parents, causing a huge family feud.",
    "Reddit Family DNA Scandal": "Write a suspenseful Reddit post about a person who bought DNA test kits for the family for Christmas, only to accidentally uncover a long-hidden family secret.",
    "Reddit Malicious Compliance": "Write a dramatic Reddit story about a worker who used malicious compliance to expose their micromanaging boss, leading to a complete company restructure.",
    "Reddit Neighbor Property Feud": "Write a dramatic Reddit post about an escalating petty war between two neighbors over a property line that ends in a hilarious, unexpected twist.",
    "Reddit Entitled In-Laws": "Write a dramatic Reddit post about a spouse who finally stood up to their entitled in-laws who tried to take over their home, resulting in a dramatic confrontation.",
    "Reddit Fake Resume Chaos": "Write a dramatic Reddit story about a coworker who lied on their entire resume, got hired for a high-level job, and caused absolute chaos before being spectacularly caught.",
    "Reddit Secret Twin Revelation": "Write a suspenseful Reddit post about a person who discovered they had an identical twin they never knew about, leading to the exposure of a massive family cover-up.",
    "Reddit HOA Revenge": "Write a satisfying Reddit post about a homeowner who took brilliant, malicious compliance revenge against an overreaching, power-tripping HOA board president.",
    "Reddit Fake Lottery Ticket Prank": "Write a dramatic Reddit post about a prank that went way too far when a sibling gave their brother a fake winning lottery ticket, leading to a complete family breakdown.",
    "Reddit AITA Exposing a Liar": "Write an engaging Reddit-style 'Am I the Asshole' post about a user who exposed their friend's fake lifestyle and lies at a group dinner party, causing a split in their friend group.",
    "Reddit Wedding Dress Drama": "Write a dramatic Reddit post about a bride who discovered her future mother-in-law secretly bought a wedding dress identical to hers and planned to wear it to the ceremony.",
    "Reddit Secret Passage Discovery": "Write a suspenseful Reddit story about a tenant who found a hidden door behind a bookshelf in their apartment leading to a secret room containing mysterious items.",
    "Reddit Lottery Ticket Theft": "Write a dramatic Reddit post about a person who won a substantial lottery prize but had the ticket stolen by a trusted family member, resulting in a tense legal standoff.",
    "Reddit High School Reunion Revenge": "Write a satisfying Reddit post about a user who attended their high school reunion and dramatically exposed a former bully who was trying to pitch a fraudulent investment scheme to the attendees.",
    "Reddit Fake Sick Day Catastrophe": "Write a dramatic Reddit story about an employee who called in sick to attend a concert, only to be interviewed live on national television and spotted by their entire company.",
    "Reddit AITA Gender Reveal": "Write an engaging Reddit-style 'Am I the Asshole' post about a guest who accidentally revealed the baby's gender before the official announcement, leading to a massive family fallout.",
    "Reddit Secret Family Diary": "Write a suspenseful Reddit post about a user who finds their grandmother's locked diary, revealing a scandalous family secret that changes everything they knew about their parents.",
    "The Billionaire's Will": "Narrate the shocking story of a deceased billionaire whose last will and testament included a massive twist that pitted their family against a complete stranger.",
    "Hollywood's Hidden Marriage": "Describe the scandalous, suspenseful rumor of two Golden Age Hollywood stars who allegedly faked a hatred for each other to hide a secret marriage.",
    "Reddit Stolen Promotion": "Write a dramatic Reddit post about an employee who discovers their boss not only stole their work for a promotion but also has been secretly sabotaging the company, leading to a massive reveal.",
    "The Disappearing Artist": "Tell the suspenseful story of a famous painter who vanished on the eve of their biggest exhibition, leaving behind a scandalous final painting with hidden clues.",
    "Reddit DNA Betrayal": "Write an engaging Reddit story about someone who does a DNA test for fun and accidentally uncovers that their 'uncle' is actually their real father, blowing the family apart.",
    "The Sabotaged Premiere": "Narrate the dramatic historical event of a highly anticipated theater premiere that was sabotaged by a bitter rival, resulting in a shocking scandal.",
    "Workplace Embezzlement Twist": "Describe a suspenseful corporate drama where an entry-level employee accidentally uncovers a massive embezzlement scheme run by the CEO, leading to a tense standoff.",
    "Reddit Fake Friendship": "Write a suspenseful Reddit post where a user discovers their lifelong best friend has been secretly being paid by the user's parents to keep them out of trouble.",
    "The Royal Impostor": "Tell the shocking story of a historical figure who successfully posed as a long-lost royal heir, living in luxury before their scandalous true identity was revealed.",
}


def load_prompt_templates():
    if not os.path.exists(PROMPTS_FILE):
        try:
            with open(PROMPTS_FILE, "w") as f:
                json.dump(DEFAULT_PROMPTS, f, indent=4)
        except Exception as e:
            logger.warning(f"Could not initialize prompts file {PROMPTS_FILE}: {e}", exc_info=True)
            console.print(f"[red]Warning: Could not initialize prompts file: {e}[/]")
            return DEFAULT_PROMPTS
    try:
        with open(PROMPTS_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load prompts file {PROMPTS_FILE}: {e}", exc_info=True)
        console.print(f"[red]Warning: Could not load prompts file, using defaults: {e}[/]")
        return DEFAULT_PROMPTS
