import os
import uuid
import json
import asyncio
import shutil
import random
import datetime
import logging
from logging.handlers import RotatingFileHandler
import yt_dlp
from openai import OpenAI
import questionary
from rich.console import Console
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from rich.table import Table
from rich.live import Live

from generator import generate_voice, generate_ass_subtitles, compile_video

# Directories Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
console = Console()

import atexit

def clear_cache():
    if os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            if f.startswith("cached_audio_") or f.startswith("cached_words_"):
                fp = os.path.join(CACHE_DIR, f)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except Exception as e:
                        logger.debug(f"Failed to remove cache file {fp}: {e}")

atexit.register(clear_cache)

class ProgressConsole:
    def __init__(self, idx, p_dict):
        self.idx = idx
        self.p_dict = p_dict
        
    def print(self, *args, **kwargs):
        msg = " ".join(str(a) for a in args)
        if "[1/4]" in msg:
            self.p_dict[self.idx] = "Voiceover"
        elif "[2/4]" in msg:
            self.p_dict[self.idx] = "Transcription"
        elif "[3/4]" in msg:
            self.p_dict[self.idx] = "Subtitles"
        elif "[4/4]" in msg:
            self.p_dict[self.idx] = "FFmpeg Rendering"
        elif "ℹ️ Found cached" in msg:
            self.p_dict[self.idx] = "Reusing Cache (Voice/Whisper)"
            
    def clear(self):
        pass

def display_progress_table(progress_dict, total_shorts, job_details):
    table = Table(
        title="[bold magenta]Concurrent Batch Generation Progress[/bold magenta]",
        show_header=True,
        header_style="bold cyan",
        expand=True
    )
    table.add_column("Short #", justify="center", style="dim", width=8)
    table.add_column("Category & Topic", justify="left")
    table.add_column("Voice & Layout", justify="left")
    table.add_column("Status / Progress", justify="left")
    
    for idx in range(1, total_shorts + 1):
        details = job_details.get(idx, {})
        topic = details.get("topic", "Unknown")
        voice_layout = f"{details.get('voice', 'Unknown')} | {details.get('layout', 'Unknown')}"
        status = progress_dict.get(idx, "Queued")
        
        if status == "Done":
            status_str = "[bold green]✓ Done[/]"
        elif status.startswith("Failed"):
            status_str = f"[bold red]✗ {status}[/]"
        elif status == "Queued":
            status_str = "[dim]Queued...[/]"
        else:
            status_str = f"[bold yellow]🔄 {status}...[/]"
            
        table.add_row(f"#{idx}", topic, voice_layout, status_str)
        
    return table

def batch_job_worker(job_config, progress_dict):
    import sys
    import os
    import atexit
    import traceback
    
    # Silence stdout/stderr to avoid CLI pollution
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
    
    # Disable cache clearing on exit for this process
    try:
        atexit.unregister(clear_cache)
    except Exception:
        pass
        
    idx = job_config["index"]
    output_filename = job_config["output_filename"]
    
    global state, settings, console
    
    # Update process-local state and settings dictionaries
    state = {
        "script_text": "",
        "selected_voice": job_config["voice_id"],
        "bg_video_path": job_config["bg_video_path"],
        "bg_video_bottom_path": job_config["bg_video_bottom_path"],
        "bg_music_path": job_config["bg_music_path"],
        "music_volume": job_config["music_volume"],
        "voice_volume": job_config["voice_volume"],
        "sub_font": job_config["sub_font"],
        "sub_size": job_config["sub_size"],
        "sub_color": job_config["sub_color"],
        "sub_highlight": job_config["sub_highlight"],
        "sub_outline": job_config["sub_outline"],
        "sub_outline_width": job_config["sub_outline_width"],
        "sub_bold": job_config["sub_bold"],
        "enable_emojis": job_config["enable_emojis"],
        "word_pop": job_config["word_pop"],
        "word_pop_scale": job_config["word_pop_scale"],
        "inactive_dim": job_config["inactive_dim"],
        "inactive_alpha": job_config["inactive_alpha"],
        "loaded_preset_name": "Randomized Batch Job",
    }
    settings = job_config["settings"]
    console = ProgressConsole(idx, progress_dict)
    
    try:
        progress_dict[idx] = "LLM Script"
        from openai import OpenAI
        api_key = settings.get("api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = settings.get("base_url") or os.environ.get("OPENAI_BASE_URL")
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        response = client.chat.completions.create(
            model=job_config["model"],
            messages=[
                {"role": "system", "content": job_config["system_prompt"]},
                {"role": "user", "content": job_config["prompt"]}
            ],
            temperature=job_config["script_temp"]
        )
        script_text = response.choices[0].message.content.strip()
        state["script_text"] = script_text
        
        success = compile_video_flow(skip_confirm=True, custom_output_filename=output_filename)
        if success:
            progress_dict[idx] = "Done"
            return (idx, True, output_filename)
        else:
            progress_dict[idx] = "Failed"
            return (idx, False, "Compilation failed (check logs/app.log)")
    except Exception as e:
        logger.error(f"Batch job {idx} exception: {e}\n{traceback.format_exc()}")
        progress_dict[idx] = f"Failed: {str(e)}"
        return (idx, False, str(e))

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

_WHISPER_MODEL = None
_WHISPER_MODEL_NAME = None

def make_preset_path_relative(path):
    if not path or path == "random":
        return path
    if path.startswith(BASE_DIR):
        return os.path.relpath(path, BASE_DIR)
    return path

def resolve_preset_path(path):
    if not path:
        return None
    if path == "random":
        return "random"
    if os.path.isabs(path):
        if os.path.exists(path):
            return path
        parts = path.split(os.sep)
        if "videos" in parts:
            idx = parts.index("videos")
            subpath = os.path.join(*parts[idx:])
            full = os.path.join(BASE_DIR, subpath)
            if os.path.exists(full):
                return full
        if "music" in parts:
            idx = parts.index("music")
            subpath = os.path.join(*parts[idx:])
            full = os.path.join(BASE_DIR, subpath)
            if os.path.exists(full):
                return full
        return path
    else:
        full = os.path.join(BASE_DIR, path)
        if os.path.exists(full):
            return full
        return path

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

EMOJIS_FILE = os.path.join(CONFIG_DIR, "emojis.json")

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

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load settings from {SETTINGS_FILE}: {e}", exc_info=True)
    return {}

def save_settings(settings_dict):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings_dict, f, indent=2)
        return True
    except Exception as e:
        logger.warning(f"Failed to save settings to {SETTINGS_FILE}: {e}", exc_info=True)
        return False

def refresh_opencode_token(auth_path, data):
    import urllib.request
    import urllib.parse
    import time
    openai_data = data.get("openai", {})
    refresh_token = openai_data.get("refresh")
    if not refresh_token:
        return None
        
    url = "https://auth.openai.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
        "refresh_token": refresh_token
    }
    try:
        req_data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            new_access = res_data.get("access_token")
            new_refresh = res_data.get("refresh_token")
            expires_in = res_data.get("expires_in", 3600)
            
            openai_data["access"] = new_access
            openai_data["refresh"] = new_refresh
            openai_data["expires"] = int((time.time() + expires_in) * 1000)
            data["openai"] = openai_data
            
            with open(auth_path, "w") as f:
                json.dump(data, f, indent=2)
            return new_access
    except Exception:
        pass
    return None

def discover_opencode_keys():
    import time
    opencode_auth_path = "/root/.local/share/opencode/auth.json"
    if os.path.exists(opencode_auth_path):
        try:
            with open(opencode_auth_path, "r") as f:
                data = json.load(f)
            opencode_key = data.get("opencode-go", {}).get("key")
            openai_data = data.get("openai", {})
            openai_token = openai_data.get("access")
            expires = openai_data.get("expires", 0)
            
            # If expired or close to expiring (within 2 minutes), refresh
            if openai_token and expires and (expires < time.time() * 1000 + 120000):
                new_token = refresh_opencode_token(opencode_auth_path, data)
                if new_token:
                    openai_token = new_token
            return opencode_key, openai_token
        except Exception:
            pass
    return None, None

VOICES = [
    ("Sarah (US Female)", "af_sarah"),
    ("Bella (US Female)", "af_bella"),
    ("Heart (US Female)", "af_heart"),
    ("Nicole (US Female)", "af_nicole"),
    ("Sky (US Female)", "af_sky"),
    ("Adam (US Male)", "am_adam"),
    ("Michael (US Male)", "am_michael"),
    ("Fenrir (US Male)", "am_fenrir"),
    ("Echo (US Male)", "am_echo"),
    ("Eric (US Male)", "am_eric"),
    ("Emma (UK Female)", "bf_emma"),
    ("Isabella (UK Female)", "bf_isabella"),
    ("George (UK Male)", "bm_george"),
    ("Lewis (UK Male)", "bm_lewis"),
]

# Application State
state = {
    "script_text": "",
    "bg_video_path": None,
    "bg_video_bottom_path": None,
    "selected_voice": "af_sarah",
    "bg_music_path": None,
    "music_volume": None,  # Will fallback to settings default if None
    "voice_volume": None,  # Will fallback to settings default if None
    "sub_font": None,
    "sub_size": None,
    "sub_color": None,
    "sub_highlight": None,
    "sub_outline": None,
    "sub_outline_width": None,
    "sub_bold": None,
    "word_pop": None,
    "word_pop_scale": None,
    "inactive_dim": None,
    "inactive_alpha": None,
    "enable_emojis": None,
    "loaded_preset_name": None,
}
settings = {}

def print_header():
    console.clear()
    console.print("[bold cyan]========================================[/]")
    console.print("[bold cyan]       AI TikTok Shorts Creator        [/]")
    console.print("[bold cyan]========================================[/]")
    console.print()

DEFAULT_PROMPTS = {
    "Mind-blowing Science Facts": "Write about 3 mind-blowing science facts that sound fake but are 100% real.",
    "Unsolved Historical Mystery": "Write a suspenseful, engaging mystery about the lost colony of Roanoke.",
    "Procrastination Motivation Hack": "Explain the 2-minute rule for beating procrastination and how to start applying it right now.",
    "Chilling Creepypasta Story": "Write a fast-paced, spine-chilling story about a person who gets a text message from their own number.",
    "Time-Saving Life Hacks": "Share 3 simple, practical life hacks that save time in the morning routine.",
    "Dark Psychology Tricks": "Explain 3 subtle dark psychology tricks people use to influence you, and how to defend against them.",
    "Strange Laws Around the World": "Share 3 of the most bizarre laws from different countries that are actually still on the books.",
    "Survival Hacks that Save Lives": "Describe 3 crucial survival tips for extreme scenarios that everyone should memorize.",
    "Mindless Consumerism Traps": "Reveal 3 clever tricks supermarkets and stores use to get you to spend more money without realizing it.",
    "The Paradox of Choice": "Explain the paradox of choice and why having too many options makes us unhappy, in a simple, relatable way.",
    "Bizarre Deep Sea Creatures": "Describe 3 of the weirdest, most terrifying creatures discovered in the deepest parts of the ocean.",
    "How the Pyramids Were Built": "Explain the most popular and fascinating theories about how the Ancient Egyptians constructed the Great Pyramids.",
    "Simple Sleep Hacks": "Share 3 science-backed tips to fall asleep in under 5 minutes and wake up feeling refreshed.",
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
    "History of the Internet": "Explain a surprising, lesser-known story about how the internet was created or its earliest days."
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
        with open(PROMPTS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load prompts file {PROMPTS_FILE}: {e}", exc_info=True)
        console.print(f"[red]Warning: Could not load prompts file, using defaults: {e}[/]")
        return DEFAULT_PROMPTS

def generate_script():
    console.print("[bold yellow]1. SCRIPT GENERATION[/]")
    templates = load_prompt_templates()
    choices = [questionary.Choice(title=k, value=v) for k, v in templates.items()]
    choices.append(questionary.Choice(title="Write Custom Prompt...", value="__custom__"))
    choices.append(questionary.Choice(title="<- Cancel", value="__cancel__"))
    
    selected_template = questionary.select("Select a prompt template or write custom:", choices=choices).ask()
    if not selected_template or selected_template == "__cancel__":
        console.print("[yellow]Generation cancelled.[/]")
        return
        
    if selected_template == "__custom__":
        prompt = questionary.text("Enter prompt/topic for the AI script:").ask()
        if not prompt:
            console.print("[yellow]Generation cancelled: prompt cannot be empty.[/]")
            return
    else:
        prompt = selected_template
        
    voice_choices = [questionary.Choice(title=name, value=val) for name, val in VOICES]
    voice = questionary.select("Select TTS Voice:", choices=voice_choices, default=state["selected_voice"]).ask()
    if not voice:
        return
    if voice != state["selected_voice"]:
        state["selected_voice"] = voice
        state["loaded_preset_name"] = None
    
    default_model = settings.get("model", "gpt-4o-mini")
    model_override = questionary.text(f"Script Model Name (optional, default: {default_model}):").ask()
    
    # Get settings values
    api_key = settings.get("api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = settings.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    model = model_override.strip() or default_model
    
    opencode_key, _ = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and not base_url:
            base_url = "https://opencode.ai/zen/go/v1"
            
    if not api_key:
        logger.error("API Key is missing when attempting script generation.")
        console.print("[red]Error: API Key is required to generate script. Set it in Settings.[/]")
        return
        
    if not model:
        if base_url and "opencode.ai" in base_url:
            model = "deepseek-v4-flash"
        else:
            model = "gpt-4o-mini"
            
    console.print(f"[yellow]Generating script using model '{model}'...[/]")
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    system_prompt = (
        "You are an expert TikTok and YouTube Shorts content creator. "
        "Write a highly engaging, viral vertical video script about the topic provided by the user. "
        "Guidelines:\n"
        "- Hook: Write a powerful hook in the first 3 seconds to grab attention.\n"
        "- Format: The script should be conversational, punchy, and fast-paced.\n"
        "- Length: Strictly under 130 words (approx. 50-60 seconds when spoken).\n"
        "- Content: Include 3 key points or a compelling narrative.\n"
        "- Formatting: Output ONLY the spoken words. Do NOT include sound effect cues, stage directions, or brackets like [Music] or [Host]."
    )
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        script_text = response.choices[0].message.content.strip()
        state["script_text"] = script_text
        console.print("\n[green]Script successfully generated![/]")
        console.print("[bold white]Preview of script:[/]")
        console.print(f"[italic]{script_text}[/]\n")
    except Exception as e:
        logger.error(f"Script generation failed for prompt '{prompt}': {e}", exc_info=True)
        console.print(f"[red]Script generation failed: {str(e)}[/]")
        console.print("[yellow]Detailed error logs are available in logs/app.log[/]")

def edit_script():
    console.print("[bold yellow]2. EDIT GENERATED SCRIPT (Strictly spoken words only)[/]")
    if not state["script_text"]:
        console.print("[yellow]No script generated yet. You can write a new script here or generate one first.[/]")
    
    edited_text = questionary.text(
        "Edit the script below (press Escape then Enter to save/confirm):",
        default=state["script_text"],
        multiline=True
    ).ask()
    
    if edited_text is not None:
        state["script_text"] = edited_text.strip()
        console.print("[green]Script updated successfully![/]")

def configure_background(position="top"):
    state_key = "bg_video_path" if position == "top" else "bg_video_bottom_path"
    pos_label = "TOP (Primary Video)" if position == "top" else "BOTTOM (Satisfying Loop)"
    
    console.print(f"[bold yellow]3. CONFIGURE BACKGROUND VIDEO - {pos_label}[/]")
    
    # Ensure videos directory exists
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    
    # Gather existing videos in VIDEOS_DIR
    video_files = []
    if os.path.exists(VIDEOS_DIR):
        video_files = [f for f in os.listdir(VIDEOS_DIR) if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.avi'))]
        video_files = sorted(video_files, key=lambda x: os.path.getmtime(os.path.join(VIDEOS_DIR, x)), reverse=True)
        
    choices = []
    current_val = state[state_key]
    current_name = "Random Selection" if current_val == "random" else (os.path.basename(current_val) if current_val else "None")
    console.print(f"Current Video: [cyan]{current_name}[/]\n")
    
    for f in video_files:
        size_mb = os.path.getsize(os.path.join(VIDEOS_DIR, f)) // (1024 * 1024)
        choices.append(questionary.Choice(title=f"📹 {f} ({size_mb} MB)", value=f"file:{f}"))
        
    choices.append(questionary.Choice(title="🎲 [Random Video from videos/]", value="random"))
    choices.append(questionary.Choice(title="➕ [Download a new video from YouTube]", value="youtube"))
    choices.append(questionary.Choice(title="📂 [Use an arbitrary local video path]", value="local"))
    choices.append(questionary.Choice(title="<- Back to Main Menu", value="back"))
    
    selected = questionary.select(f"Select background video source for {pos_label}:", choices=choices).ask()
    if not selected or selected == "back":
        return
        
    if selected == "random":
        state[state_key] = "random"
        console.print(f"[green]Successfully configured {pos_label} to select a random video on compilation.[/]")
        
    elif selected.startswith("file:"):
        filename = selected[len("file:"):]
        full_path = os.path.join(VIDEOS_DIR, filename)
        if not os.path.exists(full_path):
            console.print(f"[red]Error: Selected video file '{full_path}' does not exist.[/]")
            return
        state[state_key] = full_path
        console.print(f"[green]Successfully loaded video for {pos_label}: {filename}[/]")
        
    elif selected == "local":
        local_path = questionary.text("Enter Local File Path:").ask()
        if not local_path:
            return
        if not os.path.exists(local_path):
            console.print(f"[red]Error: Local file path '{local_path}' does not exist.[/]")
            return
        ext = os.path.splitext(local_path)[1].lower()
        if ext not in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
            console.print("[red]Error: Invalid video format. Must be mp4, mov, mkv, webm, or avi.[/]")
            return
            
        original_filename = os.path.basename(local_path)
        dest_path = os.path.join(VIDEOS_DIR, original_filename)
        
        # Avoid conflict by generating a unique name if it already exists
        if os.path.exists(dest_path):
            base, extension = os.path.splitext(original_filename)
            counter = 1
            while os.path.exists(os.path.join(VIDEOS_DIR, f"{base}_{counter}{extension}")):
                counter += 1
            dest_path = os.path.join(VIDEOS_DIR, f"{base}_{counter}{extension}")
            
        console.print(f"[yellow]Copying local video to videos folder: {os.path.basename(dest_path)}...[/]")
        try:
            shutil.copy2(local_path, dest_path)
            state[state_key] = dest_path
            console.print(f"[green]Successfully loaded local video for {pos_label}: {os.path.basename(dest_path)}[/]")
        except Exception as e:
            logger.error(f"Failed to copy local video from {local_path} to {dest_path}: {e}", exc_info=True)
            console.print(f"[red]Failed to copy local video: {str(e)}[/]")
            
    elif selected == "youtube":
        yt_url = questionary.text("Enter YouTube URL:").ask()
        if not yt_url:
            return
            
        console.print(f"[yellow]Analyzing YouTube video: {yt_url}...[/]")
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': os.path.join(VIDEOS_DIR, "%(title)s.%(ext)s"),
            'max_filesize': 500 * 1024 * 1024,
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(yt_url, download=False)
                dest_path = ydl.prepare_filename(info)
                
                if os.path.exists(dest_path):
                    console.print(f"[green]Video already exists: {os.path.basename(dest_path)}. Skipping download.[/]")
                    state[state_key] = dest_path
                    return
                
                console.print(f"[yellow]Downloading YouTube video: {info.get('title', 'Unknown Title')}...[/]")
                ydl.params['quiet'] = False
                ydl.params['no_warnings'] = False
                info = ydl.extract_info(yt_url, download=True)
                
                downloads = info.get('requested_downloads')
                if downloads and isinstance(downloads, list) and len(downloads) > 0:
                    first_download = downloads[0]
                    if isinstance(first_download, dict):
                        path = (first_download.get('filepath') or 
                                first_download.get('filename') or 
                                first_download.get('_filename'))
                else:
                    path = (info.get('filepath') or 
                            info.get('filename') or 
                            info.get('_filename') or 
                            ydl.prepare_filename(info))
                            
            if not os.path.exists(path) or path.endswith(".part"):
                filename = os.path.basename(dest_path)
                matching = [f for f in os.listdir(VIDEOS_DIR) if f.startswith(os.path.splitext(filename)[0]) and not f.endswith(".part")]
                if matching:
                    path = os.path.join(VIDEOS_DIR, matching[0])
                    
            if not os.path.exists(path) or path.endswith(".part"):
                raise FileNotFoundError("Downloaded YouTube file not found or is incomplete (.part).")
                
            state[state_key] = path
            console.print(f"[green]YouTube video downloaded and loaded for {pos_label}: {os.path.basename(path)}[/]")
        except Exception as e:
            logger.error(f"YouTube download failed for URL '{yt_url}': {e}", exc_info=True)
            console.print(f"[red]YouTube download failed: {str(e)}[/]")

def configure_background_music():
    console.print("[bold yellow]4. CONFIGURE BACKGROUND MUSIC[/]")
    
    # Gather existing music in MUSIC_DIR
    music_files = []
    if os.path.exists(MUSIC_DIR):
        music_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac'))]
        music_files = sorted(music_files, key=lambda x: os.path.getmtime(os.path.join(MUSIC_DIR, x)), reverse=True)
        
    choices = []
    current_music_name = os.path.basename(state["bg_music_path"]) if state["bg_music_path"] else "None"
    console.print(f"Current Background Music: [cyan]{current_music_name}[/]\n")
    
    for f in music_files:
        size_mb = os.path.getsize(os.path.join(MUSIC_DIR, f)) / (1024 * 1024)
        choices.append(questionary.Choice(title=f"🎵 {f} ({size_mb:.2f} MB)", value=f"file:{f}"))
        
    choices.append(questionary.Choice(title="➕ [Download music from URL]", value="download"))
    choices.append(questionary.Choice(title="📂 [Use an arbitrary local audio path]", value="local"))
    choices.append(questionary.Choice(title="❌ [Disable/Remove Background Music]", value="disable"))
    choices.append(questionary.Choice(title="<- Back to Main Menu", value="back"))
    
    selected = questionary.select("Select background music source:", choices=choices).ask()
    if not selected or selected == "back":
        return
        
    if selected.startswith("file:"):
        filename = selected[len("file:"):]
        full_path = os.path.join(MUSIC_DIR, filename)
        if not os.path.exists(full_path):
            console.print(f"[red]Error: Selected music file '{full_path}' does not exist.[/]")
            return
        state["bg_music_path"] = full_path
        console.print(f"[green]Successfully loaded background music: {filename}[/]")
        
    elif selected == "disable":
        state["bg_music_path"] = None
        console.print("[green]Background music disabled.[/]")
        
    elif selected == "local":
        local_path = questionary.text("Enter Local Audio File Path:").ask()
        if not local_path:
            return
        if not os.path.exists(local_path):
            console.print(f"[red]Error: Local file path '{local_path}' does not exist.[/]")
            return
        ext = os.path.splitext(local_path)[1].lower()
        if ext not in [".mp3", ".wav", ".m4a", ".ogg", ".flac"]:
            console.print("[red]Error: Invalid audio format. Must be mp3, wav, m4a, ogg, or flac.[/]")
            return
            
        original_filename = os.path.basename(local_path)
        dest_path = os.path.join(MUSIC_DIR, original_filename)
        
        if os.path.exists(dest_path):
            base, extension = os.path.splitext(original_filename)
            counter = 1
            while os.path.exists(os.path.join(MUSIC_DIR, f"{base}_{counter}{extension}")):
                counter += 1
            dest_path = os.path.join(MUSIC_DIR, f"{base}_{counter}{extension}")
            
        console.print(f"[yellow]Copying local audio to music folder: {os.path.basename(dest_path)}...[/]")
        try:
            shutil.copy2(local_path, dest_path)
            state["bg_music_path"] = dest_path
            console.print(f"[green]Successfully loaded local audio: {os.path.basename(dest_path)}[/]")
        except Exception as e:
            logger.error(f"Failed to copy local audio from {local_path} to {dest_path}: {e}", exc_info=True)
            console.print(f"[red]Failed to copy local audio: {str(e)}[/]")
            
    elif selected == "download":
        music_url = questionary.text("Enter Audio URL (or YouTube URL):").ask()
        if not music_url:
            return
            
        console.print(f"[yellow]Downloading audio: {music_url}...[/]")
        
        if "youtube.com" in music_url.lower() or "youtu.be" in music_url.lower():
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(MUSIC_DIR, "%(title)s.%(ext)s"),
                'max_filesize': 100 * 1024 * 1024,
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(music_url, download=True)
                    title = info.get('title', 'Downloaded Audio')
                    dest_path = os.path.join(MUSIC_DIR, f"{title}.mp3")
                    matching = [f for f in os.listdir(MUSIC_DIR) if f.startswith(title[:10]) and f.endswith(".mp3")]
                    if matching:
                        dest_path = os.path.join(MUSIC_DIR, matching[0])
                    
                    state["bg_music_path"] = dest_path
                    console.print(f"[green]Successfully downloaded YouTube audio: {os.path.basename(dest_path)}[/]")
            except Exception as e:
                logger.error(f"YouTube audio download failed for URL '{music_url}': {e}", exc_info=True)
                console.print(f"[red]Failed to download YouTube audio: {str(e)}[/]")
        else:
            try:
                import urllib.request
                import sys
                filename = music_url.split("/")[-1].split("?")[0]
                if not filename or not filename.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac')):
                    filename = "downloaded_music.mp3"
                dest_path = os.path.join(MUSIC_DIR, filename)
                
                def progress_hook(count, block_size, total_size):
                    if total_size > 0:
                        percent = min(100, int(count * block_size * 100 / total_size))
                        sys.stdout.write(f"\rDownloading... {percent}%")
                        sys.stdout.flush()
                        
                urllib.request.urlretrieve(music_url, dest_path, reporthook=progress_hook)
                print()
                state["bg_music_path"] = dest_path
                console.print(f"[green]Downloaded audio: {filename}[/]")
            except Exception as e:
                logger.error(f"Direct audio download failed for URL '{music_url}': {e}", exc_info=True)
                console.print(f"[red]Failed to download audio: {str(e)}[/]")
                
    if state["bg_music_path"]:
        default_music_vol = settings.get("music_volume", 0.15)
        default_voice_vol = settings.get("voice_volume", 1.0)
        custom_vols = questionary.confirm("Configure custom volume levels for this short?", default=False).ask()
        if custom_vols:
            voice_vol_str = questionary.text("Voiceover volume (0.0 to 2.0):", default=str(default_voice_vol)).ask()
            music_vol_str = questionary.text("Background music volume (0.0 to 1.0):", default=str(default_music_vol)).ask()
            try:
                state["voice_volume"] = float(voice_vol_str)
            except ValueError:
                state["voice_volume"] = default_voice_vol
            try:
                state["music_volume"] = float(music_vol_str)
            except ValueError:
                state["music_volume"] = default_music_vol
            console.print(f"[green]Volumes set: Voice={state['voice_volume']}, Music={state['music_volume']}[/]")
        else:
            state["voice_volume"] = None
            state["music_volume"] = None

def compile_video_flow(skip_confirm=False, custom_output_filename=None):
    console.print("[bold yellow]5. COMPILE TIKTOK SHORT[/]")
    script = state["script_text"].strip()
    voice = state["selected_voice"]
    
    if not script:
        console.print("[red]Error: Script is empty. Please generate or edit a script first.[/]")
        return False
        
    if not state["bg_video_path"]:
        console.print("[red]Error: No top/primary background video configured. Please configure it first.[/]")
        return False
        
    # Resolve random selections
    video_files = []
    if os.path.exists(VIDEOS_DIR):
        video_files = [
            os.path.join(VIDEOS_DIR, f) 
            for f in os.listdir(VIDEOS_DIR) 
            if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.avi'))
        ]
        
    resolved_top_path = state["bg_video_path"]
    resolved_bottom_path = state["bg_video_bottom_path"]
    
    if resolved_top_path == "random":
        if not video_files:
            console.print("[red]Error: No background videos found in videos/ folder to select from.[/]")
            return False
        resolved_top_path = random.choice(video_files)
        console.print(f"[yellow]Resolved Top Video: {os.path.basename(resolved_top_path)}[/]")
        
    if resolved_bottom_path == "random":
        if not video_files:
            console.print("[red]Error: No background videos found in videos/ folder to select from.[/]")
            return False
        # Try to select a different video than the top video if possible
        remaining = [v for v in video_files if v != resolved_top_path]
        if remaining:
            resolved_bottom_path = random.choice(remaining)
        else:
            resolved_bottom_path = random.choice(video_files)
        console.print(f"[yellow]Resolved Bottom Video: {os.path.basename(resolved_bottom_path)}[/]")
        
    # Validate final paths
    if not resolved_top_path or not os.path.exists(resolved_top_path):
        console.print(f"[red]Error: Top background video file '{resolved_top_path}' not found.[/]")
        return False
        
    if state["bg_video_bottom_path"] and (not resolved_bottom_path or not os.path.exists(resolved_bottom_path)):
        console.print(f"[red]Error: Bottom background video file '{resolved_bottom_path}' not found.[/]")
        return False
        
    # Get settings values
    api_key = settings.get("api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = settings.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    whisper_api_key = settings.get("whisper_api_key") or os.environ.get("WHISPER_API_KEY")
    whisper_base_url = settings.get("whisper_base_url") or os.environ.get("WHISPER_BASE_URL")
    use_local_whisper = settings.get("local_whisper", True)
    local_model_name = settings.get("local_whisper_model", "tiny")
    
    opencode_key, opencode_openai_token = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and not base_url:
            base_url = "https://opencode.ai/zen/go/v1"
            
    if not use_local_whisper and not api_key:
        console.print("[red]Error: API Key is required to transcribe audio when local Whisper is disabled. Configure it in Settings.[/]")
        return False
        
    if not skip_confirm:
        confirm = questionary.confirm("Are you sure you want to compile the TikTok Short now?").ask()
        if not confirm:
            return False
        
    job_id = str(uuid.uuid4())
    audio_path = os.path.join(CACHE_DIR, f"audio_{job_id}.wav")
    subs_path = os.path.join(CACHE_DIR, f"subs_{job_id}.ass")
    if custom_output_filename:
        output_filename = custom_output_filename
    else:
        output_filename = f"rendered_{job_id}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    try:
        # Load subtitle style settings
        sub_opts = {
            "font_name": state.get("sub_font") or settings.get("sub_font", "Arial"),
            "font_size": int(state.get("sub_size") or settings.get("sub_size", 72)),
            "primary_color": state.get("sub_color") or settings.get("sub_color", "#FFFFFF"),
            "highlight_color": state.get("sub_highlight") or settings.get("sub_highlight", "#00FFFF"),
            "outline_color": state.get("sub_outline") or settings.get("sub_outline", "#000000"),
            "outline_width": int(state.get("sub_outline_width") if state.get("sub_outline_width") is not None else settings.get("sub_outline_width", 5)),
            "bold": state.get("sub_bold") if state.get("sub_bold") is not None else settings.get("sub_bold", True),
            "word_pop": state.get("word_pop") if state.get("word_pop") is not None else settings.get("word_pop", True),
            "word_pop_scale": float(state.get("word_pop_scale") if state.get("word_pop_scale") is not None else settings.get("word_pop_scale", 1.15)),
            "inactive_dim": state.get("inactive_dim") if state.get("inactive_dim") is not None else settings.get("inactive_dim", True),
            "inactive_alpha": state.get("inactive_alpha") if state.get("inactive_alpha") is not None else settings.get("inactive_alpha", "88"),
            "enable_emojis": state.get("enable_emojis") if state.get("enable_emojis") is not None else settings.get("enable_emojis", True)
        }
        
        if state["bg_video_bottom_path"]:
            # Stacked split screen: position subtitle centered in the bottom video
            sub_opts["alignment"] = 2
            sub_opts["margin_v"] = 440
        else:
            # Full screen: standard Alignment 5 (Middle center)
            sub_opts["alignment"] = 5
            sub_opts["margin_v"] = 10
        
        # Load volume settings
        voice_vol = state["voice_volume"]
        if voice_vol is None:
            voice_vol = settings.get("voice_volume", 1.0)
        music_vol = state["music_volume"]
        if music_vol is None:
            music_vol = settings.get("music_volume", 0.15)

        # Compute cache key for audio & whisper transcription
        import hashlib
        cache_str = f"{voice}:{use_local_whisper}:{local_model_name}:{script}"
        cache_key = hashlib.md5(cache_str.encode("utf-8")).hexdigest()
        cached_audio_path = os.path.join(CACHE_DIR, f"cached_audio_{cache_key}.wav")
        cached_words_path = os.path.join(CACHE_DIR, f"cached_words_{cache_key}.json")
        
        words = []
        use_cached = os.path.exists(cached_audio_path) and os.path.exists(cached_words_path)
        
        if use_cached:
            console.print("[bold green]ℹ️ Found cached audio and transcription for this script. Reusing...[/]")
            try:
                # Copy cached audio to the temporary run path
                shutil.copy(cached_audio_path, audio_path)
                # Load words from cached json
                with open(cached_words_path, "r", encoding="utf-8") as f:
                    words = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read cached words json or copy audio, invalidating cache: {e}", exc_info=True)
                use_cached = False
                words = []
                
        if not use_cached:
            # 1. Kokoro ONNX Audio Generation
            console.print("[yellow][1/4] Generating voiceover audio locally using Kokoro ONNX...[/]")
            asyncio.run(generate_voice(script, voice, audio_path))
            console.print("[green]Voice audio generated successfully.[/]")
            
            # 2. Whisper Transcription
            global _WHISPER_MODEL, _WHISPER_MODEL_NAME
            if use_local_whisper:
                console.print(f"[yellow][2/4] Transcribing voiceover audio locally using faster-whisper ({local_model_name})...[/]")
                try:
                    from faster_whisper import WhisperModel
                    # Run the model locally
                    if _WHISPER_MODEL is None or _WHISPER_MODEL_NAME != local_model_name:
                        _WHISPER_MODEL = WhisperModel(local_model_name, device="cpu", compute_type="int8")
                        _WHISPER_MODEL_NAME = local_model_name
                    segments, info = _WHISPER_MODEL.transcribe(audio_path, word_timestamps=True)
                    for segment in segments:
                        if segment.words:
                            for w in segment.words:
                                words.append({
                                    "word": w.word,
                                    "start": w.start,
                                    "end": w.end
                                })
                    if not words:
                        raise ValueError("Local Whisper transcription did not return any words.")
                except Exception as e:
                    console.print(f"[red]Local Whisper transcription failed: {str(e)}[/]")
                    raise e
            else:
                console.print("[yellow][2/4] Transcribing voiceover audio for word-level timestamps (Whisper API)...[/]")
                try:
                    if whisper_api_key:
                        w_client = OpenAI(api_key=whisper_api_key, base_url=whisper_base_url)
                    elif whisper_base_url:
                        w_client = OpenAI(api_key=api_key, base_url=whisper_base_url)
                    elif base_url and "opencode.ai" in base_url:
                        w_key = opencode_openai_token or os.environ.get("OPENAI_API_KEY")
                        if w_key:
                            w_client = OpenAI(api_key=w_key, base_url="https://api.openai.com/v1")
                        else:
                            w_client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")
                    else:
                        w_client = OpenAI(api_key=api_key, base_url=base_url)
                        
                    with open(audio_path, "rb") as f:
                        transcription = w_client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                            response_format="verbose_json",
                            timestamp_granularities=["word"]
                        )
                        
                    if hasattr(transcription, "words") and transcription.words:
                        for w in transcription.words:
                            words.append({
                                "word": w.get("word") if isinstance(w, dict) else getattr(w, "word"),
                                "start": w.get("start") if isinstance(w, dict) else getattr(w, "start"),
                                "end": w.get("end") if isinstance(w, dict) else getattr(w, "end")
                            })
                    else:
                        raise ValueError("Whisper transcription did not return word-level timestamps.")
                except Exception as e:
                    console.print(f"[yellow]Whisper API transcription failed: {str(e)}. Falling back to local faster-whisper ({local_model_name})...[/]")
                    try:
                        from faster_whisper import WhisperModel
                        if _WHISPER_MODEL is None or _WHISPER_MODEL_NAME != local_model_name:
                            _WHISPER_MODEL = WhisperModel(local_model_name, device="cpu", compute_type="int8")
                            _WHISPER_MODEL_NAME = local_model_name
                        segments, info = _WHISPER_MODEL.transcribe(audio_path, word_timestamps=True)
                        for segment in segments:
                            if segment.words:
                                for w in segment.words:
                                    words.append({
                                        "word": w.word,
                                        "start": w.start,
                                        "end": w.end
                                    })
                        if not words:
                            raise ValueError("Local fallback Whisper transcription did not return any words.")
                    except Exception as local_e:
                        console.print(f"[red]Local Whisper fallback also failed: {str(local_e)}[/]")
                        raise e
                        
            # Save newly generated audio and words to cache
            try:
                shutil.copy(audio_path, cached_audio_path)
                with open(cached_words_path, "w", encoding="utf-8") as f:
                    json.dump(words, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to write audio/words to cache: {e}", exc_info=True)
            
        audio_duration = words[-1]["end"] + 0.5
        console.print(f"[green]Transcription complete: {len(words)} words. Duration: {audio_duration:.2f}s[/]")
        
        # 3. Create Styled Subtitles File
        console.print("[yellow][3/4] Generating ASS subtitle file with custom styling...[/]")
        generate_ass_subtitles(words, subs_path, style_opts=sub_opts, emoji_map=load_emoji_map())
        console.print("[green]ASS subtitles generated.[/]")
        
        # 4. Render video using FFmpeg
        console.print("[yellow][4/4] Rendering vertical video using FFmpeg (cropping 9:16, mixing audio, burning subtitles)...[/]")
        render_preset = settings.get("render_preset", "veryfast")
        render_res = settings.get("render_resolution", "1080p")
        compile_video(
            bg_video_path=resolved_top_path,
            audio_path=audio_path,
            subs_path=subs_path,
            output_path=output_path,
            audio_duration=audio_duration,
            music_path=state["bg_music_path"],
            voice_volume=voice_vol,
            music_volume=music_vol,
            bg_video_bottom_path=resolved_bottom_path,
            render_preset=render_preset,
            render_resolution=render_res
        )
        
        console.print(f"\n[green]🎉 RENDER SUCCESSFUL! Saved to output/{output_filename}[/]\n")
        return True
    except Exception as e:
        logger.error(f"Video compilation failed for job '{job_id}': {e}", exc_info=True)
        console.print(f"[red]Video compilation failed: {str(e)}[/]")
        console.print("[yellow]Detailed error logs are available in logs/app.log[/]")
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass
        return False
    finally:
        for p in [audio_path, subs_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

def generate_fully_random_short():
    console.print("[bold yellow]GENERATE FULLY RANDOM SHORT[/]")
    
    # 1. Check API Key
    api_key = settings.get("api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = settings.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    default_model = settings.get("model", "gpt-4o-mini")
    model = default_model
    
    opencode_key, _ = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and not base_url:
            base_url = "https://opencode.ai/zen/go/v1"
            
    if not api_key:
        console.print("[red]Error: API Key is required to generate script. Set it in Settings.[/]")
        return

    # Check background videos & music to make sure they are available or download defaults
    download_default_assets_if_empty()

    # Ask how many shorts to generate
    num_shorts_str = questionary.text("How many random shorts do you want to generate?", default="1").ask()
    if not num_shorts_str:
        return
    try:
        num_shorts = int(num_shorts_str)
        if num_shorts <= 0:
            console.print("[red]Please enter a positive integer.[/]")
            return
    except ValueError:
        console.print("[red]Invalid number entered.[/]")
        return

    if num_shorts == 1:
        # 2. Select a random topic
        templates = load_prompt_templates()
        if not templates:
            console.print("[red]Error: No prompt templates found.[/]")
            return
        template_title, prompt = random.choice(list(templates.items()))
        
        # 3. Select a random TTS voice
        voice_name, voice_id = random.choice(VOICES)
        
        # 4. Select a random preset
        presets = load_presets()
        if not presets:
            console.print("[red]Error: No presets found.[/]")
            return
        preset_name, preset = random.choice(list(presets.items()))
        
        # 5. Determine backgrounds & music
        # Randomize layout: choose split-screen or full-screen randomly
        is_split = random.choice([True, False])
        if is_split:
            top_video = "random"
            bottom_video = "random"
        else:
            top_video = "random"
            bottom_video = None
        
        # Select background music from music/ directory
        os.makedirs(MUSIC_DIR, exist_ok=True)
        music_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac'))]
        if music_files:
            chosen_music = os.path.join(MUSIC_DIR, random.choice(music_files))
        else:
            # Fall back to preset's music selection
            chosen_music = resolve_preset_path(preset.get("bg_music_path"))

        # Subtitle styling randomized
        sub_font = random.choice(["Arial", "Impact", "Georgia", "Courier New", "Times New Roman"])
        sub_size = random.randint(64, 84)
        sub_color = "#FFFFFF"
        vibrant_colors = ["#FFFF00", "#00FFFF", "#00FF00", "#FF00FF", "#FF3333", "#FF9900", "#0080FF", "#FF55BB", "#33FF33"]
        sub_highlight = random.choice(vibrant_colors)
        sub_outline = "#000000"
        sub_outline_width = random.randint(4, 7)
        sub_bold = random.choice([True, False])
        
        enable_emojis = random.choice([True, False])
        word_pop = random.choice([True, False])
        word_pop_scale = round(random.uniform(1.10, 1.25), 2) if word_pop else 1.0
        inactive_dim = random.choice([True, False])
        inactive_alpha = random.choice(["44", "66", "88", "AA"]) if inactive_dim else "FF"
        
        # Script temperature
        script_temp = round(random.uniform(0.5, 0.9), 2)

        # 6. Display a summary of the randomized choices
        console.print("\n[bold cyan]🎲 Randomized Choices Summary:[/]")
        console.print(f"  • [bold]Prompt Category:[/] {template_title}")
        console.print(f"  • [bold]Prompt/Topic:[/] [italic]{prompt}[/]")
        console.print(f"  • [bold]TTS Voice:[/] {voice_name} ({voice_id})")
        console.print(f"  • [bold]Preset Style (Base):[/] {preset_name}")
        console.print(f"  • [bold]Subtitle Font:[/] {sub_font} ({sub_size}px, Bold={sub_bold})")
        console.print(f"  • [bold]Subtitle Colors:[/] Text={sub_color} | Highlight={sub_highlight} | Outline={sub_outline} ({sub_outline_width}px)")
        console.print(f"  • [bold]Animations/Style:[/] Pop={word_pop} (x{word_pop_scale}) | Dim={inactive_dim} ({inactive_alpha}) | Emojis={enable_emojis}")
        console.print(f"  • [bold]LLM Temperature:[/] {script_temp}")
        
        if bottom_video:
            layout_str = f"Split-Screen (Top: {os.path.basename(top_video) if top_video and top_video != 'random' else top_video} | Bottom: {os.path.basename(bottom_video) if bottom_video and bottom_video != 'random' else bottom_video})"
        else:
            layout_str = f"Full Screen (Top: {os.path.basename(top_video) if top_video and top_video != 'random' else top_video})"
        console.print(f"  • [bold]Video Layout:[/] {layout_str}")
        console.print(f"  • [bold]Background Music:[/] {os.path.basename(chosen_music) if chosen_music else 'None'}")
        console.print()
        
        confirm = questionary.confirm("Do you want to proceed with generating and compiling this randomized short?").ask()
        if not confirm:
            console.print("[yellow]Cancelled random generation.[/]")
            return
            
        # 7. Apply to global state (overwrites active session state)
        state["selected_voice"] = voice_id
        state["bg_video_path"] = top_video
        state["bg_video_bottom_path"] = bottom_video
        state["bg_music_path"] = chosen_music
        state["music_volume"] = preset.get("music_volume")
        state["voice_volume"] = preset.get("voice_volume")
        state["loaded_preset_name"] = f"{preset_name} (Randomized)"
        
        # Subtitle styling loaded
        state["sub_font"] = sub_font
        state["sub_size"] = sub_size
        state["sub_color"] = sub_color
        state["sub_highlight"] = sub_highlight
        state["sub_outline"] = sub_outline
        state["sub_outline_width"] = sub_outline_width
        state["sub_bold"] = sub_bold
        state["enable_emojis"] = enable_emojis
        state["word_pop"] = word_pop
        state["word_pop_scale"] = word_pop_scale
        state["inactive_dim"] = inactive_dim
        state["inactive_alpha"] = inactive_alpha

        # 8. Generate the script using the OpenAI API
        if base_url and "opencode.ai" in base_url:
            model = "deepseek-v4-flash"
        else:
            model = "gpt-4o-mini"
            
        console.print(f"\n[yellow]Generating script using model '{model}'...[/]")
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        system_prompt = (
            "You are an expert TikTok and YouTube Shorts content creator. "
            "Write a highly engaging, viral vertical video script about the topic provided by the user. "
            "Guidelines:\n"
            "- Hook: Write a powerful hook in the first 3 seconds to grab attention.\n"
            "- Format: The script should be conversational, punchy, and fast-paced.\n"
            "- Length: Strictly under 130 words (approx. 50-60 seconds when spoken).\n"
            "- Content: Include 3 key points or a compelling narrative.\n"
            "- Formatting: Output ONLY the spoken words. Do NOT include sound effect cues, stage directions, or brackets like [Music] or [Host]."
        )
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=script_temp
            )
            script_text = response.choices[0].message.content.strip()
            state["script_text"] = script_text
            console.print("\n[green]Script successfully generated![/]")
            console.print("[bold white]Preview of script:[/]")
            console.print(f"[italic]{script_text}[/]\n")
        except Exception as e:
            logger.error(f"Random short script generation failed: {e}", exc_info=True)
            console.print(f"[red]Script generation failed: {str(e)}[/]")
            console.print("[yellow]Detailed error logs are available in logs/app.log[/]")
            return

        # 9. Trigger Compilation (skip secondary confirmation!)
        compile_video_flow(skip_confirm=True)
    else:
        # Batch generation flow
        confirm = questionary.confirm(f"Are you sure you want to generate and compile {num_shorts} randomized shorts in bulk?").ask()
        if not confirm:
            console.print("[yellow]Cancelled bulk random generation.[/]")
            return
            
        # Save active session state to restore later
        old_state = state.copy()
        
        templates = load_prompt_templates()
        if not templates:
            console.print("[red]Error: No prompt templates found.[/]")
            return
            
        presets = load_presets()
        if not presets:
            console.print("[red]Error: No presets found.[/]")
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        success_count = 0
        failed_videos = []
        successful_videos = []
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        system_prompt = (
            "You are an expert TikTok and YouTube Shorts content creator. "
            "Write a highly engaging, viral vertical video script about the topic provided by the user. "
            "Guidelines:\n"
            "- Hook: Write a powerful hook in the first 3 seconds to grab attention.\n"
            "- Format: The script should be conversational, punchy, and fast-paced.\n"
            "- Length: Strictly under 130 words (approx. 50-60 seconds when spoken).\n"
            "- Content: Include 3 key points or a compelling narrative.\n"
            "- Formatting: Output ONLY the spoken words. Do NOT include sound effect cues, stage directions, or brackets like [Music] or [Host]."
        )
        
        if base_url and "opencode.ai" in base_url:
            model = "deepseek-v4-flash"
        else:
            model = "gpt-4o-mini"
            
        # Prepare all job configurations
        job_configs = {}
        job_details = {}
        
        for i in range(1, num_shorts + 1):
            # 1. Random choices
            template_title, prompt = random.choice(list(templates.items()))
            voice_name, voice_id = random.choice(VOICES)
            preset_name, preset = random.choice(list(presets.items()))
            
            # Randomize layout: choose split-screen or full-screen randomly
            is_split = random.choice([True, False])
            if is_split:
                top_video = "random"
                bottom_video = "random"
            else:
                top_video = "random"
                bottom_video = None
                
            # Select background music from music/ directory
            os.makedirs(MUSIC_DIR, exist_ok=True)
            music_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac'))]
            if music_files:
                chosen_music = os.path.join(MUSIC_DIR, random.choice(music_files))
            else:
                chosen_music = resolve_preset_path(preset.get("bg_music_path"))
                
            # Randomize subtitle properties
            sub_font = random.choice(["Arial", "Impact", "Georgia", "Courier New", "Times New Roman"])
            sub_size = random.randint(64, 84)
            sub_color = "#FFFFFF"
            vibrant_colors = ["#FFFF00", "#00FFFF", "#00FF00", "#FF00FF", "#FF3333", "#FF9900", "#0080FF", "#FF55BB", "#33FF33"]
            sub_highlight = random.choice(vibrant_colors)
            sub_outline = "#000000"
            sub_outline_width = random.randint(4, 7)
            sub_bold = random.choice([True, False])
            
            enable_emojis = random.choice([True, False])
            word_pop = random.choice([True, False])
            word_pop_scale = round(random.uniform(1.10, 1.25), 2) if word_pop else 1.0
            inactive_dim = random.choice([True, False])
            inactive_alpha = random.choice(["44", "66", "88", "AA"]) if inactive_dim else "FF"
            
            # Script temperature
            script_temp = round(random.uniform(0.5, 0.9), 2)
            
            output_filename = f"rendered_batch_{timestamp}_{i}.mp4"
            
            job_configs[i] = {
                "index": i,
                "prompt": prompt,
                "voice_id": voice_id,
                "bg_video_path": top_video,
                "bg_video_bottom_path": bottom_video,
                "bg_music_path": chosen_music,
                "music_volume": preset.get("music_volume"),
                "voice_volume": preset.get("voice_volume"),
                "sub_font": sub_font,
                "sub_size": sub_size,
                "sub_color": sub_color,
                "sub_highlight": sub_highlight,
                "sub_outline": sub_outline,
                "sub_outline_width": sub_outline_width,
                "sub_bold": sub_bold,
                "enable_emojis": enable_emojis,
                "word_pop": word_pop,
                "word_pop_scale": word_pop_scale,
                "inactive_dim": inactive_dim,
                "inactive_alpha": inactive_alpha,
                "script_temp": script_temp,
                "output_filename": output_filename,
                "model": model,
                "system_prompt": system_prompt,
                "settings": settings.copy()
            }
            
            job_details[i] = {
                "topic": f"[{template_title}] {prompt[:35]}...",
                "voice": voice_name,
                "layout": "Split-Screen" if is_split else "Full Screen"
            }
            
        max_workers = settings.get("max_workers")
        if not max_workers:
            max_workers = os.cpu_count() or 1
        else:
            try:
                max_workers = int(max_workers)
            except ValueError:
                max_workers = os.cpu_count() or 1
        console.print(f"\n[bold yellow]Spawning {num_shorts} batch generation jobs in parallel (max_workers={max_workers})...[/]")
        
        try:
            with multiprocessing.Manager() as manager:
                progress_dict = manager.dict()
                for i in range(1, num_shorts + 1):
                    progress_dict[i] = "Queued"
                    
                with ProcessPoolExecutor(max_workers=max_workers) as executor:
                    futures = []
                    for i in range(1, num_shorts + 1):
                        futures.append(executor.submit(batch_job_worker, job_configs[i], progress_dict))
                        
                    with Live(display_progress_table(progress_dict, num_shorts, job_details), console=console, refresh_per_second=4) as live:
                        while not all(f.done() for f in futures):
                            time.sleep(0.25)
                            live.update(display_progress_table(progress_dict, num_shorts, job_details))
                        live.update(display_progress_table(progress_dict, num_shorts, job_details))
                        
                    # Collect results
                    for f in futures:
                        try:
                            idx, success, output_info = f.result()
                            if success:
                                success_count += 1
                                successful_videos.append(output_info)
                            else:
                                failed_videos.append(f"Short {idx} ({output_info})")
                        except Exception as e:
                            failed_videos.append(f"Execution error: {str(e)}")
        finally:
            # Restore state
            for k, v in old_state.items():
                state[k] = v
                
        # Batch Summary
        console.print(f"\n[bold green]========================================[/]")
        console.print(f"[bold green]🎉 BATCH RUN COMPLETED![/]")
        console.print(f"[bold green]========================================[/]")
        console.print(f"Successfully created: {success_count}/{num_shorts} videos.")
        if successful_videos:
            console.print("\n[bold white]Successful Videos (Saved in output/):[/]")
            for f in successful_videos:
                console.print(f"  • {f}")
        if failed_videos:
            console.print("\n[bold red]Failed Videos:[/]")
            for f in failed_videos:
                console.print(f"  • {f}")
        console.print(f"[bold green]========================================[/]\n")

def configure_settings():
    console.print("[bold yellow]6. SETTINGS MANAGEMENT[/]")
    
    current_key = settings.get("api_key", "")
    current_base = settings.get("base_url", "")
    current_model = settings.get("model", "gpt-4o-mini")
    current_w_key = settings.get("whisper_api_key", "")
    current_w_base = settings.get("whisper_base_url", "")
    current_local_whisper = settings.get("local_whisper", True)
    current_local_model = settings.get("local_whisper_model", "tiny")
    
    # Subtitle defaults
    current_voice_vol = settings.get("voice_volume", 1.0)
    current_music_vol = settings.get("music_volume", 0.15)
    current_sub_font = settings.get("sub_font", "Arial")
    current_sub_size = settings.get("sub_size", 72)
    current_sub_color = settings.get("sub_color", "#FFFFFF")
    current_sub_highlight = settings.get("sub_highlight", "#00FFFF")
    current_sub_outline = settings.get("sub_outline", "#000000")
    current_sub_outline_width = settings.get("sub_outline_width", 5)
    current_sub_bold = settings.get("sub_bold", True)
    
    # Subtitle Animation & Emojis defaults
    current_word_pop = settings.get("word_pop", True)
    current_word_pop_scale = settings.get("word_pop_scale", 1.15)
    current_inactive_dim = settings.get("inactive_dim", True)
    current_inactive_alpha = settings.get("inactive_alpha", "88")
    current_enable_emojis = settings.get("enable_emojis", True)

    settings_cat = questionary.select(
        "Select settings category to configure:",
        choices=[
            questionary.Choice("1. API Keys & AI Models", "api"),
            questionary.Choice("2. Subtitle Styling", "subtitles"),
            questionary.Choice("3. Default Audio Volumes", "volumes"),
            questionary.Choice("4. Subtitle Animations & Emojis", "animations"),
            questionary.Choice("5. Manage Emoji Dictionary", "emojis"),
            questionary.Choice("6. Video Rendering & Performance Settings", "rendering"),
            questionary.Choice("<- Back to Main Menu", "back")
        ]
    ).ask()
    
    if not settings_cat or settings_cat == "back":
        return
        
    if settings_cat == "api":
        api_key = questionary.password("OpenAI API Key (or OpenCode key):", default=current_key).ask()
        base_url = questionary.text("OpenAI Base URL (optional):", default=current_base).ask()
        model = questionary.text("Script Generation Model Name:", default=current_model).ask()
        whisper_key = questionary.password("Whisper API Key (optional fallback):", default=current_w_key).ask()
        whisper_base_url = questionary.text("Whisper Base URL (optional fallback):", default=current_w_base).ask()
        
        use_local = questionary.confirm("Use local Whisper for transcription?", default=current_local_whisper).ask()
        
        local_model = current_local_model
        if use_local:
            local_model = questionary.select(
                "Select local Whisper model:",
                choices=["tiny", "base", "small", "medium"],
                default=current_local_model
            ).ask()
        
        if api_key is not None: settings["api_key"] = api_key.strip()
        if base_url is not None: settings["base_url"] = base_url.strip()
        if model is not None: settings["model"] = model.strip() or "gpt-4o-mini"
        if whisper_key is not None: settings["whisper_api_key"] = whisper_key.strip()
        if whisper_base_url is not None: settings["whisper_base_url"] = whisper_base_url.strip()
        if use_local is not None: settings["local_whisper"] = use_local
        if local_model is not None: settings["local_whisper_model"] = local_model

    elif settings_cat == "subtitles":
        font_name = questionary.text("Font Family Name (e.g. Arial, Impact, Montserrat):", default=current_sub_font).ask()
        font_size = questionary.text("Font Size (e.g. 64, 72, 80):", default=str(current_sub_size)).ask()
        primary_color = questionary.text("Primary Text Color (HEX e.g. #FFFFFF):", default=current_sub_color).ask()
        highlight_color = questionary.text("Active Word Highlight Color (HEX e.g. #00FFFF):", default=current_sub_highlight).ask()
        outline_color = questionary.text("Outline Color (HEX e.g. #000000):", default=current_sub_outline).ask()
        outline_width = questionary.text("Outline Width (e.g. 3, 5, 8):", default=str(current_sub_outline_width)).ask()
        bold = questionary.confirm("Use Bold text?", default=current_sub_bold).ask()
        
        if font_name is not None: settings["sub_font"] = font_name.strip()
        if font_size is not None:
            try: settings["sub_size"] = int(font_size)
            except ValueError: pass
        if primary_color is not None: settings["sub_color"] = primary_color.strip()
        if highlight_color is not None: settings["sub_highlight"] = highlight_color.strip()
        if outline_color is not None: settings["sub_outline"] = outline_color.strip()
        if outline_width is not None:
            try: settings["sub_outline_width"] = int(outline_width)
            except ValueError: pass
        if bold is not None: settings["sub_bold"] = bold

    elif settings_cat == "volumes":
        voice_vol = questionary.text("Default Voiceover Volume (0.0 to 2.0):", default=str(current_voice_vol)).ask()
        music_vol = questionary.text("Default Background Music Volume (0.0 to 1.0):", default=str(current_music_vol)).ask()
        
        if voice_vol is not None:
            try: settings["voice_volume"] = float(voice_vol)
            except ValueError: pass
        if music_vol is not None:
            try: settings["music_volume"] = float(music_vol)
            except ValueError: pass

    elif settings_cat == "animations":
        word_pop = questionary.confirm("Enable Active Word Pop (scaling effect)?", default=current_word_pop).ask()
        word_pop_scale = current_word_pop_scale
        if word_pop:
            scale_str = questionary.text("Active Word Scaling Factor (e.g. 1.15, 1.20):", default=str(current_word_pop_scale)).ask()
            if scale_str:
                try: word_pop_scale = float(scale_str)
                except ValueError: pass
                
        inactive_dim = questionary.confirm("Enable Inactive Word Dimming?", default=current_inactive_dim).ask()
        inactive_alpha = current_inactive_alpha
        if inactive_dim:
            inactive_alpha = questionary.select(
                "Select Inactive Words Dimming Level:",
                choices=[
                    questionary.Choice("Light Dimming (approx. 73% Opacity) [alpha: 44]", "44"),
                    questionary.Choice("Medium Dimming (approx. 47% Opacity) [alpha: 88]", "88"),
                    questionary.Choice("Heavy Dimming (approx. 27% Opacity) [alpha: BB]", "BB")
                ],
                default=current_inactive_alpha
            ).ask()
            
        enable_emojis = questionary.confirm("Enable Contextual Dynamic Emoji Injection?", default=current_enable_emojis).ask()
        
        if word_pop is not None: settings["word_pop"] = word_pop
        if word_pop_scale is not None: settings["word_pop_scale"] = word_pop_scale
        if inactive_dim is not None: settings["inactive_dim"] = inactive_dim
        if inactive_alpha is not None: settings["inactive_alpha"] = inactive_alpha
        if enable_emojis is not None: settings["enable_emojis"] = enable_emojis

    elif settings_cat == "emojis":
        while True:
            emoji_map = load_emoji_map()
            console.clear()
            console.print("[bold yellow]Emoji Mapping Dictionary[/]")
            console.print(f"Total mappings: [cyan]{len(emoji_map)}[/]\n")
            
            sample_keys = list(emoji_map.keys())[:10]
            console.print("Sample mappings:")
            for k in sample_keys:
                console.print(f"  • {k} -> {emoji_map[k]}")
            if len(emoji_map) > 10:
                console.print(f"  ... and {len(emoji_map) - 10} more.")
            console.print()
            
            action = questionary.select(
                "Select emoji dictionary action:",
                choices=[
                    questionary.Choice("➕ Add New Mapping", "add"),
                    questionary.Choice("✏️ Edit/Remove Existing Mapping", "edit"),
                    questionary.Choice("🔄 Reset to Default Map", "reset"),
                    questionary.Choice("<- Back to Settings Menu", "back")
                ]
            ).ask()
            
            if not action or action == "back":
                break
                
            if action == "add":
                word_to_add = questionary.text("Enter lowercase word/stem (e.g. 'ghost'):").ask()
                if not word_to_add:
                    continue
                word_to_add = word_to_add.strip().lower()
                emoji_to_add = questionary.text("Enter emoji (e.g. '👻'):").ask()
                if not emoji_to_add:
                    continue
                emoji_map[word_to_add] = emoji_to_add.strip()
                if save_emoji_map(emoji_map):
                    console.print(f"[green]Added {word_to_add} -> {emoji_to_add}[/]")
                else:
                    console.print("[red]Error: Failed to save emoji map.[/]")
                questionary.press_any_key_to_continue().ask()
                
            elif action == "edit":
                if not emoji_map:
                    console.print("[yellow]Emoji dictionary is empty.[/]")
                    questionary.press_any_key_to_continue().ask()
                    continue
                sorted_keys = sorted(emoji_map.keys())
                choices = [questionary.Choice(f"{k} -> {emoji_map[k]}", k) for k in sorted_keys]
                choices.append(questionary.Choice("<- Back", "back"))
                
                selected_key = questionary.select("Select mapping to edit/delete:", choices=choices).ask()
                if not selected_key or selected_key == "back":
                    continue
                    
                edit_action = questionary.select(
                    f"Select action for '{selected_key}' mapping:",
                    choices=[
                        questionary.Choice("Edit Emoji", "edit_val"),
                        questionary.Choice("❌ Delete Mapping", "delete_val"),
                        questionary.Choice("<- Cancel", "cancel")
                    ]
                ).ask()
                
                if edit_action == "edit_val":
                    new_val = questionary.text(f"Enter new emoji for '{selected_key}' (current: {emoji_map[selected_key]}):").ask()
                    if new_val:
                        emoji_map[selected_key] = new_val.strip()
                        save_emoji_map(emoji_map)
                        console.print("[green]Mapping updated successfully![/]")
                elif edit_action == "delete_val":
                    del emoji_map[selected_key]
                    save_emoji_map(emoji_map)
                    console.print("[green]Mapping deleted successfully![/]")
                questionary.press_any_key_to_continue().ask()
                
            elif action == "reset":
                confirm = questionary.confirm("Are you sure you want to reset all mappings to defaults? Custom additions will be lost!").ask()
                if confirm:
                    if save_emoji_map(DEFAULT_EMOJI_MAP):
                        console.print("[green]Emoji dictionary successfully reset to defaults.[/]")
                    else:
                        console.print("[red]Failed to reset emoji dictionary.[/]")
                questionary.press_any_key_to_continue().ask()
            
    elif settings_cat == "rendering":
        current_preset = settings.get("render_preset", "veryfast")
        current_res = settings.get("render_resolution", "1080p")
        current_max_workers = settings.get("max_workers", os.cpu_count() or 1)
        
        render_preset = questionary.select(
            "Select FFmpeg rendering speed preset (faster presets compile quicker but have slightly larger size/lower quality):",
            choices=[
                questionary.Choice("ultrafast (Fastest render, largest file size)", "ultrafast"),
                questionary.Choice("superfast (Very fast render)", "superfast"),
                questionary.Choice("veryfast (Default fast render)", "veryfast"),
                questionary.Choice("faster (Medium-fast render)", "faster"),
                questionary.Choice("fast (Balanced render)", "fast"),
                questionary.Choice("medium (Standard render, best quality/size)", "medium")
            ],
            default=current_preset
        ).ask()
        
        render_resolution = questionary.select(
            "Select video output resolution (720p is ~2.25x faster to render than 1080p):",
            choices=[
                questionary.Choice("1080p (1080x1920 - Full HD)", "1080p"),
                questionary.Choice("720p (720x1280 - HD)", "720p")
            ],
            default=current_res
        ).ask()

        max_workers = questionary.text(
            f"Maximum parallel batch jobs (default is CPU count: {os.cpu_count()}):",
            default=str(current_max_workers)
        ).ask()
        
        if render_preset is not None:
            settings["render_preset"] = render_preset
        if render_resolution is not None:
            settings["render_resolution"] = render_resolution
        if max_workers is not None:
            try:
                settings["max_workers"] = int(max_workers)
            except ValueError:
                pass

    if save_settings(settings):
        console.print("[green]Settings saved successfully![/]")
    else:
        console.print("[red]Failed to save settings to disk.[/]")

def view_history():
    console.print("[bold yellow]7. VIEW HISTORY & MANAGE VIDEOS[/]")
    while True:
        if not os.path.exists(OUTPUT_DIR):
            console.print("[yellow]Output directory does not exist.[/]")
            break
            
        files = sorted(
            [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".mp4")],
            key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)),
            reverse=True
        )
        
        if not files:
            console.print("[yellow]No compiled videos found in output/ directory.[/]")
            break
            
        choices = []
        for f in files:
            full_path = os.path.join(OUTPUT_DIR, f)
            size_mb = os.path.getsize(full_path) // (1024 * 1024)
            choices.append(questionary.Choice(title=f"📹 {f} ({size_mb} MB)", value=f))
            
        choices.append(questionary.Choice(title="<- Back to Main Menu", value="back"))
        
        selected_file = questionary.select("Select a video to manage:", choices=choices).ask()
        if not selected_file or selected_file == "back":
            break
            
        # Manage single file
        full_path = os.path.join(OUTPUT_DIR, selected_file)
        console.print(f"\n[bold white]File Info:[/]")
        console.print(f"Name: {selected_file}")
        console.print(f"Path: {full_path}")
        console.print(f"Size: {os.path.getsize(full_path) // (1024 * 1024)} MB")
        
        action = questionary.select(
            "Select action:",
            choices=[
                questionary.Choice(title="❌ Delete File", value="delete"),
                questionary.Choice(title="<- Back to History", value="back")
            ]
        ).ask()
        
        if action == "delete":
            confirm = questionary.confirm(f"Are you sure you want to delete {selected_file}?").ask()
            if confirm:
                try:
                    os.remove(full_path)
                    console.print(f"[green]Successfully deleted {selected_file}.[/]")
                except Exception as e:
                    console.print(f"[red]Failed to delete file: {str(e)}[/]")

DEFAULT_VIDEO_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
DEFAULT_MUSIC_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"

def check_system_dependencies():
    import subprocess
    import shutil
    import sys
    
    ffmpeg_found = shutil.which("ffmpeg") is not None
    ffprobe_found = shutil.which("ffprobe") is not None
    
    # Check for emoji fonts to prevent square glyphs ("tofu")
    if shutil.which("fc-list") is not None:
        try:
            res = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True)
            families = res.stdout.lower()
            if not ("symbola" in families or "emoji" in families):
                console.print("[bold yellow]Warning: No emoji or symbol fonts detected. Subtitle emojis may render as squares.[/]")
                apt_found = shutil.which("apt-get") is not None
                if apt_found:
                    console.print("[yellow]Attempting to install 'fonts-symbola' via apt-get...[/]")
                    try:
                        is_root = os.getuid() == 0
                        cmd_prefix = [] if is_root else ["sudo"]
                        subprocess.run(cmd_prefix + ["apt-get", "update", "-y"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.run(cmd_prefix + ["apt-get", "install", "-y", "fonts-symbola"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        console.print("[green]Successfully installed 'fonts-symbola'![/]")
                    except Exception as e:
                        logger.warning(f"Failed to auto-install 'fonts-symbola': {e}", exc_info=True)
                        console.print(f"[yellow]Auto-installation of fonts-symbola failed. Emojis may render as squares.[/]")
        except Exception as e:
            logger.warning(f"Error checking system fonts: {e}", exc_info=True)

    if ffmpeg_found and ffprobe_found:
        return
        
    logger.error("System dependencies 'ffmpeg' or 'ffprobe' are missing.")
    console.print("[bold yellow]System dependencies 'ffmpeg' or 'ffprobe' are missing.[/]")
    
    apt_found = shutil.which("apt-get") is not None
    if apt_found:
        console.print("[yellow]Attempting to install 'ffmpeg' using apt-get...[/]")
        try:
            is_root = os.getuid() == 0
            cmd_prefix = [] if is_root else ["sudo"]
            
            console.print("[yellow]Running: apt-get update -y[/]")
            subprocess.run(cmd_prefix + ["apt-get", "update", "-y"], check=True)
            
            console.print("[yellow]Running: apt-get install -y ffmpeg[/]")
            subprocess.run(cmd_prefix + ["apt-get", "install", "-y", "ffmpeg"], check=True)
            
            # Recheck
            if shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None:
                console.print("[green]Successfully installed ffmpeg/ffprobe via apt-get.[/]")
                return
        except Exception as e:
            logger.error(f"Auto-installation of ffmpeg failed: {e}", exc_info=True)
            console.print(f"[red]Auto-installation failed: {e}[/]")
            
    logger.error("Required system packages 'ffmpeg' and 'ffprobe' could not be resolved automatically.")
    console.print("[bold red]Please install ffmpeg and ffprobe manually to proceed.[/]")
    console.print("Instructions:")
    console.print("- Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y ffmpeg")
    console.print("- macOS: brew install ffmpeg")
    console.print("- Windows: scoop install ffmpeg or choco install ffmpeg")
    sys.exit(1)

def download_default_assets_if_empty():
    import urllib.request
    from generator import download_file
    
    # Check background videos
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    video_files = [f for f in os.listdir(VIDEOS_DIR) if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.avi'))]
    if not video_files:
        console.print("[bold yellow]No background videos found in videos/. Downloading a default loop...[/]")
        dest_video = os.path.join(VIDEOS_DIR, "default_loop.mp4")
        try:
            download_file(DEFAULT_VIDEO_URL, dest_video, "Default Video Loop (Big Buck Bunny)")
            state["bg_video_path"] = dest_video
            console.print("[green]Successfully downloaded and selected default loop video.[/]")
        except Exception as e:
            logger.error(f"Failed to download default video loop from {DEFAULT_VIDEO_URL}: {e}", exc_info=True)
            console.print(f"[red]Failed to download default video loop: {e}[/]")
    else:
        # Default to the most recently modified video if not already set
        if not state.get("bg_video_path"):
            latest_video = sorted(video_files, key=lambda x: os.path.getmtime(os.path.join(VIDEOS_DIR, x)), reverse=True)[0]
            state["bg_video_path"] = os.path.join(VIDEOS_DIR, latest_video)
        
    # Check background music
    os.makedirs(MUSIC_DIR, exist_ok=True)
    music_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac'))]
    if not music_files:
        console.print("[bold yellow]No music tracks found in music/. Downloading default background music...[/]")
        dest_music = os.path.join(MUSIC_DIR, "default_music.mp3")
        try:
            download_file(DEFAULT_MUSIC_URL, dest_music, "Default Background Music (SoundHelix Song 1)")
            state["bg_music_path"] = dest_music
            console.print("[green]Successfully downloaded and selected default music track.[/]")
        except Exception as e:
            logger.error(f"Failed to download default music track from {DEFAULT_MUSIC_URL}: {e}", exc_info=True)
            console.print(f"[red]Failed to download default music track: {e}[/]")
    else:
        # Default to the most recently modified music track if not already set
        if not state.get("bg_music_path"):
            latest_music = sorted(music_files, key=lambda x: os.path.getmtime(os.path.join(MUSIC_DIR, x)), reverse=True)[0]
            state["bg_music_path"] = os.path.join(MUSIC_DIR, latest_music)

def manage_presets_menu():
    console.print("[bold yellow]8. PRESET TEMPLATES MANAGEMENT[/]")
    presets = load_presets()
    
    choices = [
        questionary.Choice("1. Load Preset Template", "load"),
        questionary.Choice("2. Save Current Config as Preset", "save"),
        questionary.Choice("3. Delete Custom Preset", "delete"),
        questionary.Choice("<- Back to Main Menu", "back")
    ]
    
    action = questionary.select("Select preset action:", choices=choices).ask()
    if not action or action == "back":
        return
        
    if action == "load":
        if not presets:
            console.print("[yellow]No presets found.[/]")
            return
            
        preset_choices = [questionary.Choice(name, name) for name in presets.keys()]
        preset_choices.append(questionary.Choice("<- Back", "back"))
        
        selected_preset_name = questionary.select("Select preset to load:", choices=preset_choices).ask()
        if not selected_preset_name or selected_preset_name == "back":
            return
            
        preset = presets[selected_preset_name]
        
        # Load simple state values
        state["selected_voice"] = preset.get("selected_voice", "af_sarah")
        state["bg_video_path"] = resolve_preset_path(preset.get("bg_video_path"))
        state["bg_video_bottom_path"] = resolve_preset_path(preset.get("bg_video_bottom_path"))
        state["bg_music_path"] = resolve_preset_path(preset.get("bg_music_path"))
        state["music_volume"] = preset.get("music_volume")
        state["voice_volume"] = preset.get("voice_volume")
        state["loaded_preset_name"] = selected_preset_name
        
        # Subtitle styling loaded
        preset_sub_font = preset.get("sub_font", "Arial")
        preset_sub_size = preset.get("sub_size", 72)
        preset_sub_color = preset.get("sub_color", "#FFFFFF")
        preset_sub_highlight = preset.get("sub_highlight", "#00FFFF")
        preset_sub_outline = preset.get("sub_outline", "#000000")
        preset_sub_outline_width = preset.get("sub_outline_width", 5)
        preset_sub_bold = preset.get("sub_bold", True)
        
        # Subtitle animation options loaded
        preset_word_pop = preset.get("word_pop", True)
        preset_word_pop_scale = preset.get("word_pop_scale", 1.15)
        preset_inactive_dim = preset.get("inactive_dim", True)
        preset_inactive_alpha = preset.get("inactive_alpha", "88")
        preset_enable_emojis = preset.get("enable_emojis", True)
        
        console.print(f"\n[cyan]Loaded preset properties for '{selected_preset_name}':[/]")
        console.print(f" Voice: {state['selected_voice']}")
        console.print(f" Video Top: {os.path.basename(state['bg_video_path']) if state['bg_video_path'] and state['bg_video_path'] != 'random' else state['bg_video_path']}")
        console.print(f" Video Bottom: {os.path.basename(state['bg_video_bottom_path']) if state['bg_video_bottom_path'] and state['bg_video_bottom_path'] != 'random' else state['bg_video_bottom_path']}")
        console.print(f" Music: {os.path.basename(state['bg_music_path']) if state['bg_music_path'] else 'None'}")
        console.print(f" Subtitle Style: {preset_sub_font} ({preset_sub_size}px, {preset_sub_color})")
        console.print(f" Animations: Pop={preset_word_pop} (x{preset_word_pop_scale}), Dim={preset_inactive_dim} ({preset_inactive_alpha}), Emojis={preset_enable_emojis}")
        
        sub_apply = questionary.select(
            "How would you like to apply the subtitle styling and animations of this preset?",
            choices=[
                questionary.Choice("Temporarily (only for this short)", "temp"),
                questionary.Choice("Globally (overwrite settings.json)", "global"),
                questionary.Choice("Keep current styling (ignore preset subtitle style)", "ignore")
            ]
        ).ask()
        
        if sub_apply == "global":
            settings["sub_font"] = preset_sub_font
            settings["sub_size"] = preset_sub_size
            settings["sub_color"] = preset_sub_color
            settings["sub_highlight"] = preset_sub_highlight
            settings["sub_outline"] = preset_sub_outline
            settings["sub_outline_width"] = preset_sub_outline_width
            settings["sub_bold"] = preset_sub_bold
            settings["word_pop"] = preset_word_pop
            settings["word_pop_scale"] = preset_word_pop_scale
            settings["inactive_dim"] = preset_inactive_dim
            settings["inactive_alpha"] = preset_inactive_alpha
            settings["enable_emojis"] = preset_enable_emojis
            save_settings(settings)
            
            # Clear temporary state overrides so settings.json is used
            state["sub_font"] = None
            state["sub_size"] = None
            state["sub_color"] = None
            state["sub_highlight"] = None
            state["sub_outline"] = None
            state["sub_outline_width"] = None
            state["sub_bold"] = None
            state["word_pop"] = None
            state["word_pop_scale"] = None
            state["inactive_dim"] = None
            state["inactive_alpha"] = None
            state["enable_emojis"] = None
            
            console.print("[green]Subtitle styles and animations applied globally to settings.json![/]")
        elif sub_apply == "temp":
            state["sub_font"] = preset_sub_font
            state["sub_size"] = preset_sub_size
            state["sub_color"] = preset_sub_color
            state["sub_highlight"] = preset_sub_highlight
            state["sub_outline"] = preset_sub_outline
            state["sub_outline_width"] = preset_sub_outline_width
            state["sub_bold"] = preset_sub_bold
            state["word_pop"] = preset_word_pop
            state["word_pop_scale"] = preset_word_pop_scale
            state["inactive_dim"] = preset_inactive_dim
            state["inactive_alpha"] = preset_inactive_alpha
            state["enable_emojis"] = preset_enable_emojis
            console.print("[green]Subtitle styles and animations applied temporarily for the next compile![/]")
        else:
            # Clear temporary state overrides
            state["sub_font"] = None
            state["sub_size"] = None
            state["sub_color"] = None
            state["sub_highlight"] = None
            state["sub_outline"] = None
            state["sub_outline_width"] = None
            state["sub_bold"] = None
            state["word_pop"] = None
            state["word_pop_scale"] = None
            state["inactive_dim"] = None
            state["inactive_alpha"] = None
            state["enable_emojis"] = None
            console.print("[yellow]Preset subtitle styling and animations ignored. Current styles kept.[/]")
            
        console.print(f"[green]Preset '{selected_preset_name}' successfully loaded![/]")
        
    elif action == "save":
        name = questionary.text("Enter a name for the new preset:").ask()
        if not name:
            console.print("[yellow]Save cancelled: name cannot be empty.[/]")
            return
            
        name = name.strip()
        if name in BUILTIN_PRESETS:
            console.print("[red]Error: Cannot overwrite built-in preset names.[/]")
            return
            
        preset_dict = {
            "name": name,
            "selected_voice": state["selected_voice"],
            "bg_video_path": make_preset_path_relative(state["bg_video_path"]),
            "bg_video_bottom_path": make_preset_path_relative(state["bg_video_bottom_path"]),
            "bg_music_path": make_preset_path_relative(state["bg_music_path"]),
            "music_volume": state["music_volume"] if state["music_volume"] is not None else settings.get("music_volume", 0.15),
            "voice_volume": state["voice_volume"] if state["voice_volume"] is not None else settings.get("voice_volume", 1.0),
            "sub_font": state.get("sub_font") or settings.get("sub_font", "Arial"),
            "sub_size": state.get("sub_size") or settings.get("sub_size", 72),
            "sub_color": state.get("sub_color") or settings.get("sub_color", "#FFFFFF"),
            "sub_highlight": state.get("sub_highlight") or settings.get("sub_highlight", "#00FFFF"),
            "sub_outline": state.get("sub_outline") or settings.get("sub_outline", "#000000"),
            "sub_outline_width": state.get("sub_outline_width") if state.get("sub_outline_width") is not None else settings.get("sub_outline_width", 5),
            "sub_bold": state.get("sub_bold") if state.get("sub_bold") is not None else settings.get("sub_bold", True),
            "word_pop": state.get("word_pop") if state.get("word_pop") is not None else settings.get("word_pop", True),
            "word_pop_scale": state.get("word_pop_scale") if state.get("word_pop_scale") is not None else settings.get("word_pop_scale", 1.15),
            "inactive_dim": state.get("inactive_dim") if state.get("inactive_dim") is not None else settings.get("inactive_dim", True),
            "inactive_alpha": state.get("inactive_alpha") if state.get("inactive_alpha") is not None else settings.get("inactive_alpha", "88"),
            "enable_emojis": state.get("enable_emojis") if state.get("enable_emojis") is not None else settings.get("enable_emojis", True)
        }
        
        if save_custom_preset(name, preset_dict):
            state["loaded_preset_name"] = name
            console.print(f"[green]Preset '{name}' saved successfully![/]")
        else:
            console.print("[red]Failed to save preset to disk.[/]")
            
    elif action == "delete":
        custom_presets = {}
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, "r") as f:
                    custom_presets = json.load(f)
            except Exception:
                pass
                
        if not custom_presets:
            console.print("[yellow]No custom presets available to delete. (Built-in presets cannot be deleted)[/]")
            return
            
        delete_choices = [questionary.Choice(name, name) for name in custom_presets.keys()]
        delete_choices.append(questionary.Choice("<- Back", "back"))
        
        to_delete = questionary.select("Select custom preset to delete:", choices=delete_choices).ask()
        if not to_delete or to_delete == "back":
            return
            
        confirm = questionary.confirm(f"Are you sure you want to delete custom preset '{to_delete}'?").ask()
        if confirm:
            if delete_custom_preset(to_delete):
                if state.get("loaded_preset_name") == to_delete:
                    state["loaded_preset_name"] = None
                console.print(f"[green]Deleted custom preset '{to_delete}' successfully.[/]")
            else:
                console.print("[red]Failed to delete custom preset.[/]")

def main():
    global settings
    
    # Clear any leftover cache from previous runs
    clear_cache()
    
    # Check system dependencies (FFmpeg/FFprobe)
    check_system_dependencies()
    
    settings = load_settings()
    
    # Ensure default assets exist and are loaded
    download_default_assets_if_empty()
    
    # Check if there are existing settings; auto-detect key if empty
    if not settings.get("api_key"):
        opencode_key, _ = discover_opencode_keys()
        if opencode_key:
            settings["api_key"] = opencode_key
            if not settings.get("base_url"):
                settings["base_url"] = "https://opencode.ai/zen/go/v1"
            save_settings(settings)
            
    while True:
        print_header()
        
        # Display current status in main menu
        script_status = "[green]Ready[/]" if state["script_text"] else "[red]Empty[/]"
        
        # Background video status string
        if state["bg_video_path"]:
            top_name = "Random Selection" if state["bg_video_path"] == "random" else os.path.basename(state["bg_video_path"])
            if state["bg_video_bottom_path"]:
                bot_name = "Random Selection" if state["bg_video_bottom_path"] == "random" else os.path.basename(state["bg_video_bottom_path"])
                bg_status = f"[green]Split Screen (Top: {top_name} | Bottom: {bot_name})[/]"
            else:
                bg_status = f"[green]Full Screen (Top: {top_name})[/]"
        else:
            bg_status = "[red]Not configured[/]"
            
        bg_music_status = f"[green]Loaded ({os.path.basename(state['bg_music_path'])})[/]" if state["bg_music_path"] else "[yellow]None[/]"
        
        preset_status = f"[green]{state['loaded_preset_name']}[/]" if state.get("loaded_preset_name") else "[yellow]None (Custom/Manual)[/]"
        active_font = state.get("sub_font") or settings.get("sub_font", "Arial")
        active_size = state.get("sub_size") or settings.get("sub_size", 72)
        active_color = state.get("sub_color") or settings.get("sub_color", "#FFFFFF")
        
        console.print(f"Active Preset/Template: {preset_status}")
        console.print(f"Active Subtitle Style: [cyan]{active_font} ({active_size}px, {active_color})[/]")
        console.print(f"Current Script Status: {script_status}")
        console.print(f"Background Video Loop: {bg_status}")
        console.print(f"Background Music Track: {bg_music_status}")
        console.print(f"TTS Voice: [cyan]{state['selected_voice']}[/]")
        console.print()
        
        menu_choices = [
            questionary.Choice(title="1. Generate Viral Script", value="generate"),
            questionary.Choice(title="2. Edit Current Script", value="edit"),
            questionary.Choice(title="3. Configure Background Video", value="bg"),
            questionary.Choice(title="4. Configure Background Music", value="music"),
            questionary.Choice(title="5. Compile TikTok Short", value="compile"),
            questionary.Choice(title="6. Generate Fully Random Short", value="random_short"),
            questionary.Choice(title="7. Configure App & API Settings", value="settings"),
            questionary.Choice(title="8. View History / Manage Videos", value="history"),
            questionary.Choice(title="9. Preset Templates", value="presets"),
            questionary.Choice(title="10. Exit", value="exit"),
        ]
        
        choice = questionary.select("Select an action:", choices=menu_choices).ask()
        
        if choice == "exit" or choice is None:
            console.print("[bold green]Goodbye![/]")
            break
            
        print_header()
        
        if choice == "generate":
            generate_script()
        elif choice == "edit":
            edit_script()
        elif choice == "bg":
            bg_submenu = questionary.select(
                "Configure Background Video Layout:",
                choices=[
                    questionary.Choice("1. Configure Top Video (Primary Content)", "top"),
                    questionary.Choice("2. Configure Bottom Video (Satisfying Loop / Split Screen)", "bottom"),
                    questionary.Choice("3. Disable Split Screen (Use Full Screen Top Video)", "disable_split"),
                    questionary.Choice("<- Back to Main Menu", "back")
                ]
            ).ask()
            if bg_submenu == "top":
                configure_background("top")
                state["loaded_preset_name"] = None
            elif bg_submenu == "bottom":
                configure_background("bottom")
                state["loaded_preset_name"] = None
            elif bg_submenu == "disable_split":
                state["bg_video_bottom_path"] = None
                state["loaded_preset_name"] = None
                console.print("[green]Split screen disabled. Video will render full screen using Top Video.[/]")
        elif choice == "music":
            configure_background_music()
            state["loaded_preset_name"] = None
        elif choice == "compile":
            compile_video_flow()
        elif choice == "random_short":
            generate_fully_random_short()
        elif choice == "settings":
            configure_settings()
            state["loaded_preset_name"] = None
        elif choice == "history":
            view_history()
        elif choice == "presets":
            manage_presets_menu()
            
        # Pause before returning to the main menu
        if choice != "history":
            questionary.press_any_key_to_continue("Press any key to return to the main menu...").ask()

if __name__ == "__main__":
    import multiprocessing
    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass
    main()
