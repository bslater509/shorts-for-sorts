"""
Generator package for Shorts-for-Sorts video creation.

Provides TTS voice generation, ASS subtitle generation with emoji support,
and FFmpeg-based video compilation.
"""

from generator.subtitles import (
    find_emoji_for_word,
    generate_ass_subtitles,
    hex_and_alpha_to_ass,
    hex_to_ass_color,
)
from generator.tts import (
    MODEL_PATH,
    MODEL_URL,
    VOICES_PATH,
    VOICES_URL,
    generate_voice,
    init_tts_session,
    unload_tts_model,
)
from generator.utils import _release_memory_to_os, download_file, format_time
from generator.video import compile_video, get_video_info

__all__ = [
    "MODEL_PATH",
    "MODEL_URL",
    "VOICES_PATH",
    "VOICES_URL",
    "_release_memory_to_os",
    "download_file",
    "format_time",
    "generate_voice",
    "init_tts_session",
    "unload_tts_model",
    "generate_ass_subtitles",
    "find_emoji_for_word",
    "hex_to_ass_color",
    "hex_and_alpha_to_ass",
    "compile_video",
    "get_video_info",
]
