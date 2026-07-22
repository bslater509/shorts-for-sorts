# Application State and Session Constants

# TTS Voice options
VOICES = [
    ("Bella (US Female)", "af_bella"),
    ("Sarah (US Female)", "af_sarah"),
    ("Adam (US Male)", "am_adam"),
    ("Michael (US Male)", "am_michael"),
    ("Emma (UK Female)", "bf_emma"),
    ("Isabella (UK Female)", "bf_isabella"),
    ("George (UK Male)", "bm_george"),
    ("Lewis (UK Male)", "bm_lewis"),
]

# Display name → Kokoro voice ID (for resolving user-facing names back to valid IDs)
VOICE_DISPLAY_TO_ID = {
    # Existing named mappings
    "Bella (US Female)": "af_bella",
    "Sarah (US Female)": "af_sarah",
    "Adam (US Male)": "am_adam",
    "Michael (US Male)": "am_michael",
    "Emma (UK Female)": "bf_emma",
    "Isabella (UK Female)": "bf_isabella",
    "George (UK Male)": "bm_george",
    "Lewis (UK Male)": "bm_lewis",
    # Additional Kokoro voices not in the GUI dropdown but valid in presets
    "af": "af",
    "af_nicole": "af_nicole",
    "af_sky": "af_sky",
    # Legacy preset names (used in BUILTIN_PRESETS)
    "Craig Gutsy": "am_michael",
    "Ana Florence": "af_sarah",
    "Zacharie Julian": "am_adam",
    "Claribel Dervla": "af_bella",
    "Gracie Wise": "bf_emma",
    "Badr Odhiambo": "bm_george",
    "Damien Black": "am_michael",
    "Tammie Ema": "bf_emma",
}

# Active Session State
# All keys that compiler.py and server.py access are declared here with None defaults
# so the schema is explicit and batch-mode jobs don't silently get missing keys.
state = {
    "script_text": "",
    "bg_video_path": None,
    "bg_video_bottom_path": None,
    "selected_voice": "af_bella",
    "bg_music_path": None,
    "music_volume": None,  # Falls back to settings default if None
    "voice_volume": None,  # Falls back to settings default if None
    "voice_speed": None,  # Falls back to settings default if None
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
    "sub_uppercase": None,
    "sub_border_style": None,
    "sub_shadow_width": None,
    "sub_bg_color": None,
    "sub_bg_alpha": None,
    "single_word_mode": None,
    "emoji_position": None,
    "emoji_style": None,
    "enable_emoji_animation": None,
    "emoji_scale_factor": None,
    "emoji_hold_duration": None,
    "emoji_throw_max_count": None,
    "sub_animation_style": None,
    "generated_title": None,
    "generated_hashtags": None,
}

# Global Settings (loaded from config/settings.json)
settings = {}
