"""Built-in video style presets and preset load/save/delete functions."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from gui.config import PRESETS_FILE, logger

# --- Built-in presets ---

BUILTIN_PRESETS: dict[str, dict[str, Any]] = {
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
"""Dictionary of built-in preset configurations.  Keys are preset display names."""


# --- Public API ---


def load_presets() -> dict[str, dict[str, Any]]:
    """Load all presets (built-in + custom) from disk.

    Custom presets are merged on top of built-ins, so a custom preset with
    the same name will override the built-in.

    Returns:
        Combined preset dictionary keyed by display name.
    """
    presets: dict[str, dict[str, Any]] = BUILTIN_PRESETS.copy()
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE) as f:
                custom_presets: dict[str, dict[str, Any]] = json.load(f)
                for name, p in custom_presets.items():
                    presets[name] = p
        except Exception as e:
            logger.warning(
                "Failed to load custom presets from %s: %s",
                PRESETS_FILE,
                e,
                exc_info=True,
            )
    return presets


def save_custom_preset(name: str, preset_dict: dict[str, Any]) -> bool:
    """Save a custom preset to disk.

    Args:
        name: Display name for the preset.
        preset_dict: Preset configuration dictionary.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    presets: dict[str, Any] = {}
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE) as f:
                presets = json.load(f)
        except Exception as e:
            logger.warning(
                "Failed to load presets file prior to saving preset '%s': %s",
                name,
                e,
                exc_info=True,
            )
    presets[name] = preset_dict
    try:
        with open(PRESETS_FILE, "w") as f:
            json.dump(presets, f, indent=2)
        return True
    except Exception as e:
        logger.warning(
            "Failed to save preset '%s' to custom presets file %s: %s",
            name,
            PRESETS_FILE,
            e,
            exc_info=True,
        )
        return False


def delete_custom_preset(name: str) -> bool:
    """Delete a custom preset from disk.

    Only custom presets (stored in the presets file) can be deleted;
    built-in presets are unaffected.

    Args:
        name: The display name of the preset to delete.

    Returns:
        ``True`` if the preset was deleted, ``False`` if it was not found
        or could not be deleted.
    """
    presets: dict[str, Any] = {}
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE) as f:
                presets = json.load(f)
        except Exception as e:
            logger.warning(
                "Failed to load presets file prior to deleting preset '%s': %s",
                name,
                e,
                exc_info=True,
            )
    if name in presets:
        del presets[name]
        try:
            with open(PRESETS_FILE, "w") as f:
                json.dump(presets, f, indent=2)
            return True
        except Exception as e:
            logger.warning(
                "Failed to save custom presets file after deleting preset '%s': %s",
                name,
                e,
                exc_info=True,
            )
            return False
    return False
