# Built-in presets and preset load/save/delete functions

import json
import os

from gui.config import PRESETS_FILE, console, logger

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
