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
    "You are a versatile short-form scriptwriter creating content for TikTok and YouTube Shorts. "
    "Write a compelling vertical video script based on the user's topic.\n\n"
    "Guidelines:\n"
    "1. The Hook (First 5-10s): Start with a scroll-stopping statement, provocative question, or intriguing hook that grabs attention immediately. No slow introductions.\n"
    "2. Story Arc: Structure with a clear arc — setup, rising tension or details, and a strong payoff or conclusion. Let the content find its own natural shape.\n"
    "3. Length: Aim for approximately {max_words} words (approx. {max_words_seconds} seconds when spoken). Stay flexible — let the story dictate the exact length.\n"
    "4. Pacing: Vary sentence length. Use short punchy lines for impact and longer sentences for storytelling. Build momentum toward key reveals.\n"
    "5. Tone: Sound authentic and human — conversational but informed. Avoid robotic, academic, or cliché AI writing. Let your voice match the mood of the topic.\n"
    "6. Formatting: Output ONLY the exact spoken words. Do NOT include stage directions, timestamps, speaker tags, or brackets (e.g., no [Music], [Host], or [Visuals]).\n"
    "7. Chunks: Group every 2-4 sentences into a natural spoken chunk and separate each chunk with a blank line (\\n\\n). This improves voice audio quality significantly — do not skip this.\n"
    "8. Source: Follow the framing of the user's prompt. If they set a specific scene (Reddit post, historical event, personal story), lean into that framing. If no framing is given, tell the story directly without mentioning external sources."
)

DEFAULT_PROMPTS = {
    "Romantic Drama": "Two people whose love is forbidden or tested by impossible circumstances. What stands between them? What are they willing to lose? Tell their story in a way that feels urgent and real — whether it ends in heartbreak, defiance, or something unexpected.",
    "Family Drama": "A family grappling with secrets, loss, betrayal, or a long-overdue reckoning. Zoom in on one charged moment — a reunion, a discovery, a confrontation — that forces buried tensions to the surface.",
    "Historical Drama": "Set a story in a pivotal moment in history where ordinary people faced extraordinary stakes. Don't lecture — make the era feel lived-in, the stakes personal, and the outcome anything but certain.",
    "Psychological Drama": "A character whose grip on reality is fraying — or is it? Plunge into their inner world as a buried memory, a moral dilemma, or a slow unraveling forces them to question everything they thought was true.",
    "Crime Drama": "A story of crime and consequence where guilt, justice, revenge, or a shot at redemption drives every choice. Start at the moment everything goes wrong and let the fallout unfold.",
    "Survival Drama": "Strip away comfort and put someone in a harsh, unforgiving situation — nature, circumstance, or other people. Show what they become when there is no way out but through.",
    "Political Drama": "Power, ambition, and betrayal — where every alliance has a price and ideals collide with corruption. Tell it from the perspective of someone who thought they could stay clean.",
    "Tragedy": "A character whose greatest strength becomes their fatal flaw. Let the audience see the fall coming and be powerless to stop it. The best tragedies feel inevitable but not predictable.",
    "Character Drama": "A single life-changing event that redefines who a person is. No elaborate plot — just someone at a crossroads, forced to confront who they have been and who they could become.",
    "Mystery Drama": "A dark secret buried just beneath the surface. One person starts pulling at a thread and slowly uncovers the truth — only to discover that knowing it may be worse than the not-knowing. Drip-feed the clues.",
    "Dark Comedy": "A story with a darkly comic edge where the sheer absurdity of a terrible situation becomes the point. Make the viewer uncomfortable and entertained in equal measure.",
    "Moral Dilemma": "A choice with no good options. Every path comes with a steep cost. Build the tension, show the stakes, and let the moment of decision land with real weight.",
    "Twist Ending": "Tell a story that builds toward a reveal — a single moment that completely reshapes everything the viewer thought they understood. The twist should feel surprising yet inevitable in hindsight.",
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
    "A Betrayal That Changed History": "A story of betrayal between two people who were once inseparable — a mentor and protégé, or a pair of allies who built something together. The betrayal is personal, political, and its consequences ripple far beyond just the two of them. Build the relationship first, then the moment of betrayal, then the devastating fallout.",
    "Hollywood's Most Dramatic Feud": "Two talented, ambitious people in the same industry develop a fierce rivalry that spans years. Their mutual hatred becomes as legendary as their work. Show the pettiness, the sabotage, and the uncomfortable complexity of hating someone who is also your equal.",
    "The Scandal That Shook a Monarchy": "A person in the highest position of power must choose between duty and something they want with their whole heart. Their decision throws an entire nation into crisis and forces them to give up everything. The stakes are historic and deeply personal.",
    "When Art Turned to Violence": "A fierce artistic rivalry between two performers escalates beyond the stage and spills into the streets. Egos clash, fans take sides, and what begins as creative competition turns into actual chaos. The line between art and violence disappears.",
    "The Mystery That Haunted a Family": "A person vanishes without a trace under strange circumstances. At first it seems like a simple case, but as the investigation deepens, family secrets and shocking theories surface. No one ever finds the full truth — and the mystery haunts those left behind.",
    "The Rivalry That Created Masterpieces": "Two creative geniuses working in the same city at the same time despise each other. Their intense hatred drives both to outdo the other, pushing each to create their greatest works. The competition is bitter, petty, and absolutely legendary.",
    "The War of the Currents": "Two brilliant inventors go to war over whose technology will power the world. One is a savvy businessman who plays dirty, the other a visionary idealist who can't compete in the arena of public opinion. The battle involves public stunts, sabotage, and the fight for the future itself.",
    "The Curse of the Pharaoh's Tomb": "The discovery of an ancient tomb filled with unimaginable treasure — but those who entered it begin to die one by one. Tell the story of the awe of the find, the wonder of the treasures, and the creeping dread as a so-called curse claims its victims.",
    "The Deadliest Rivalry in Medicine": "Two experts in the same field engage in a high-stakes battle of wits to prove who is superior. Ambition and pride drive one to set a treacherous trap for the other. But nothing goes as planned — and the outcome is shocking and deeply ironic.",
    "The Shipwreck That Became a Scandal": "A ship carrying hundreds of people meets a disastrous end at sea. The survivors are left adrift in horrific conditions — exposed, starving, and desperate. When rescue finally arrives, the truth of what happened and who was to blame sparks a national scandal.",
    "When Rivalry Turned Fatal": "A bitter personal and political rivalry between two formidable people builds for years. Insults, betrayals, and a clash of ambitions lead inexorably to a final, deadly confrontation. The buildup is as dramatic as the shot itself.",
    "Reddit Betrayal Story": "Write a dramatic Reddit-style story about a betrayal in a close relationship. Someone discovers a hidden truth about a partner, friend, or family member that shatters their trust. The confrontation is emotional and the stakes are deeply personal. Invent specific characters, a unique setting, and a fresh scenario — avoid overused plots.",
    "Reddit Workplace Justice": "Write a dramatic Reddit-style story from the workplace where someone in power is exposed for wrongdoing, or where an underdog gets satisfying revenge. The poster has evidence, a witness, or a clever plan. The ending should feel like justice — through official channels, public exposure, or poetic irony. Create fresh characters and a believable industry.",
    "Reddit Family Secret": "Write a dramatic Reddit-style post about the discovery of a long-hidden family secret that changes everything. The discovery happens accidentally — an old letter, a DNA test result, a diary, a slip of the tongue at a gathering. The secret is big enough to fracture relationships but the storyteller is still processing what it means. Avoid the most obvious DNA test plot lines.",
    "Reddit Entitlement Backfire": "Write a dramatic Reddit-style story about someone with unreasonable expectations who gets spectacular comeuppance. The entitled person could be a relative, neighbor, customer, or stranger. Their demand starts small and escalates. The payoff is deeply satisfying — malicious compliance, public embarrassment, or legal consequences.",
    "Reddit Twist of Fate": "Write a dramatic Reddit-style story that starts one way and takes an unexpected turn. A routine event, a small decision, or an everyday interaction leads somewhere completely unforeseen. The twist should feel surprising yet inevitable in hindsight. Could be funny, dramatic, suspenseful, or any blend.",
    "The Will That Changed Everything": "A wealthy person's last will and testament contains a shocking twist that no one saw coming. It pits family members against each other and against an unexpected stranger. Greed, long-buried secrets, and one final surprise from beyond the grave drive the story.",
    "Hollywood's Best-Kept Secret": "Two famous rivals in the entertainment industry have a secret that would destroy their carefully crafted public images. Behind the public feuding lies an unexpected truth about their relationship. Tell the story of the elaborate deception and the moment it almost unraveled.",
    "Reddit Stolen Credit": "Write a dramatic Reddit-style story about someone whose work, idea, or achievement was stolen by a colleague, boss, or even a friend. The theft is brazen and the victim has to decide whether to expose it quietly or go public with devastating proof. The reveal is tense and the fallout is massive.",
    "The Artist Who Vanished": "A brilliant creative mind disappears on the eve of their biggest moment. They leave behind one final work — and it contains clues that no one fully understands. The mystery of what happened to them endures for decades and becomes part of their legend.",
    "Reddit DNA Discovery": "Write a dramatic Reddit-style story where a casual DNA test or genealogy search uncovers a truth that reshapes someone's entire understanding of their family and identity. The discovery raises more questions than it answers. Focus on the emotional impact, not just the shock value.",
    "The Night Everything Went Wrong": "A highly anticipated event — a premiere, a launch, a grand opening — is targeted by a jealous rival. What was supposed to be a triumphant night turns into a disaster through clever, perfectly timed sabotage. The culprit's motive is revealed only at the end.",
    "Workplace Embezzlement Twist": "A low-level employee accidentally stumbles onto evidence of a massive financial crime orchestrated by someone at the very top of the company. Now they have to decide what to do with the information — and who to trust. The tension builds as they get closer to exposing the truth.",
    "Reddit Fake Friendship": "Write a dramatic Reddit-style story about a friendship that turns out to be built on a lie. Someone discovers that a close friend has been manipulating them, using them, or hiding a significant truth for years. The revelation forces them to question every moment they shared.",
    "The Impostor Who Fooled Everyone": "An ordinary person with audacity, charm, and nerve convinces a community — or an entire nation — that they are someone they are not. They live a life of luxury, power, and admiration until a small, careless mistake unravels everything. The fall is as spectacular as the rise.",
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
