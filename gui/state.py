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
    "enable_color_emoji": None,
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
    "loaded_preset_name": None,
    "batch_num_shorts": None,
    "generated_title": None,
    "generated_hashtags": None,
    "words_per_screen": None,
}

# Global Settings (loaded from config/settings.json)
settings = {}
