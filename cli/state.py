# Application State and Session Constants

# TTS Voice options
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

# Active Session State
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

# Global Settings (loaded from config/settings.json)
settings = {}
