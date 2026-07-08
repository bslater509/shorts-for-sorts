import os
import json
import logging
import atexit
from logging.handlers import RotatingFileHandler
from rich.console import Console
import sentry_sdk

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
            "message": record.getMessage()
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

# Logger Initialization
logger = logging.getLogger("shorts_creator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    # Rich console handler
    rich_handler = RichHandler(console=console, rich_tracebacks=True, show_path=False)
    rich_handler.setLevel(logging.INFO)
    logger.addHandler(rich_handler)

    # JSON File handler
    json_log_file = os.path.join(LOGS_DIR, "server.json.log")
    json_handler = RotatingFileHandler(json_log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
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

import multiprocessing
if multiprocessing.current_process().name == "MainProcess":
    atexit.register(clear_cache)

BUILTIN_PRESETS = {
    "Split-Screen Chill (Yellow Highlight)": {
        "name": "Split-Screen Chill (Yellow Highlight)",
        "selected_voice": "Craig Gutsy",
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
        "selected_voice": "Ana Florence",
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
        "selected_voice": "Zacharie Julian",
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
        "selected_voice": "Claribel Dervla",
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
        "selected_voice": "Gracie Wise",
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
        "selected_voice": "Badr Odhiambo",
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
        "selected_voice": "Damien Black",
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
        "selected_voice": "Tammie Ema",
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

    # Auto-migrate legacy LLM config
    if "llm_profiles" not in settings:
        settings["llm_profiles"] = []
    
    has_legacy_keys = any(k in settings for k in ["api_key", "base_url", "model"])
    if has_legacy_keys and not settings.get("llm_profiles"):
        import uuid
        profile_id = str(uuid.uuid4())
        settings["llm_profiles"].append({
            "id": profile_id,
            "name": "Default Profile",
            "api_key": settings.get("api_key", ""),
            "base_url": settings.get("base_url", ""),
            "model": settings.get("model", "gpt-4o-mini")
        })
        settings["active_llm_profile_id"] = profile_id
        
    # Clean up legacy keys
    migrated = False
    for k in ["api_key", "base_url", "model"]:
        if k in settings:
            del settings[k]
            migrated = True
            
    if migrated:
        save_settings(settings)
        
    else:
        # Create settings file with the default populated keys if it does not exist
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write default settings to {SETTINGS_FILE}: {e}", exc_info=True)
            
    sentry_dsn = settings.get("sentry_dsn")
    if sentry_dsn:
        import multiprocessing
        if multiprocessing.current_process().name == 'MainProcess':
            try:
                sentry_sdk.init(
                    dsn=sentry_dsn,
                    traces_sample_rate=1.0,
                    profiles_sample_rate=1.0
                )
            except Exception as e:
                logger.error(f"Failed to initialize Sentry: {e}")
            
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
    "The Royal Impostor": "Tell the shocking story of a historical figure who successfully posed as a long-lost royal heir, living in luxury before their scandalous true identity was revealed."
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
