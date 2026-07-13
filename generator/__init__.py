"""
Generator package for Shorts-for-Sorts video creation.

Provides TTS voice generation, ASS subtitle generation with emoji support,
and FFmpeg-based video compilation.
"""

from generator.utils import download_file, format_time, _release_memory_to_os
from generator.tts import (
    init_tts_session,
    generate_voice,
    unload_tts_model,
    MODEL_PATH,
    VOICES_PATH,
    MODEL_URL,
    VOICES_URL,
)
from generator.subtitles import (
    generate_ass_subtitles,
    find_emoji_for_word,
    hex_to_ass_color,
    hex_and_alpha_to_ass,
)
from generator.video import compile_video, get_video_info

__all__ = [
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
