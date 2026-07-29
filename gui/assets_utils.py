"""Asset listing helpers for video and music files.

Extracted from duplicate inline logic across multiple modules.
"""

from __future__ import annotations

import os
from typing import Optional

from gui.config import MUSIC_DIR, VIDEOS_DIR

# --- File extension sets ---

VIDEO_EXTENSIONS: tuple[str, ...] = (".mp4", ".mov", ".mkv", ".webm", ".avi")
"""Recognised video file extensions (lowercase)."""

MUSIC_EXTENSIONS: tuple[str, ...] = (".mp3", ".wav", ".m4a", ".ogg", ".flac")
"""Recognised audio file extensions (lowercase)."""

SFX_EXCLUDE_KEYWORDS: tuple[str, ...] = ("sound effect", "sfx")
"""Substrings that identify sound-effect files to exclude from video listings."""


# --- Public helpers ---


def list_video_files(
    directory: Optional[str] = None, exclude_sfx: bool = True
) -> list[str]:
    """List video files in a directory, sorted by modification time (newest first).

    Args:
        directory: Directory to scan.  Defaults to :data:`VIDEOS_DIR`.
        exclude_sfx: If ``True``, skip files whose names contain
            ``"sound effect"`` or ``"sfx"``.

    Returns:
        List of full file paths, newest first.
    """
    if directory is None:
        directory = VIDEOS_DIR
    if not os.path.exists(directory):
        return []

    files: list[tuple[str, float]] = []
    for f in os.listdir(directory):
        if exclude_sfx and _is_sfx_file(f):
            continue
        if f.lower().endswith(VIDEO_EXTENSIONS):
            fp: str = os.path.join(directory, f)
            files.append((fp, os.path.getmtime(fp)))

    files.sort(key=lambda x: x[1], reverse=True)
    return [fp for fp, _ in files]


def list_music_files(directory: Optional[str] = None) -> list[str]:
    """List music/audio files in a directory, sorted by modification time (newest first).

    Args:
        directory: Directory to scan.  Defaults to :data:`MUSIC_DIR`.

    Returns:
        List of full file paths, newest first.
    """
    if directory is None:
        directory = MUSIC_DIR
    if not os.path.exists(directory):
        return []

    files: list[tuple[str, float]] = []
    for f in os.listdir(directory):
        if f.lower().endswith(MUSIC_EXTENSIONS):
            fp: str = os.path.join(directory, f)
            files.append((fp, os.path.getmtime(fp)))

    files.sort(key=lambda x: x[1], reverse=True)
    return [fp for fp, _ in files]


# --- Internal helpers ---


def _is_sfx_file(filename: str) -> bool:
    """Check whether a filename matches known sound-effect patterns.

    Args:
        filename: The file name to check (case-insensitive).

    Returns:
        ``True`` if the filename contains a sound-effect keyword.
    """
    lower: str = filename.lower()
    return any(keyword in lower for keyword in SFX_EXCLUDE_KEYWORDS)
