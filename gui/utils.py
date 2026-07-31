"""GUI utility functions: LLM profile resolution, path helpers, system dependency checks."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from gui.assets_utils import list_music_files, list_video_files
from gui.config import BASE_DIR, MUSIC_DIR, VIDEOS_DIR, console, logger
from gui.state import settings, state

# --- Constants ---

DEFAULT_MUSIC_URL: str = (
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
)
"""Default background music download URL used when no music files are found."""

RANDOM_PATH: str = "random"
"""Sentinel value meaning "pick a random file from the available assets"."""

# Substrings that identify process names using the server port
SERVER_PROCESS_NAMES: tuple[str, ...] = ("python", "uvicorn", "gunicorn", "hypercorn")
"""Process name substrings that identify our own server processes for port cleanup."""

# fontconfig search strings for emoji font detection
EMOJI_FONT_PATTERNS: tuple[str, ...] = ("symbola", "emoji")
"""Substrings to search for in ``fc-list`` output to detect emoji font support."""


# --- Public helpers ---


def get_active_llm_profile() -> dict[str, Any]:
    """Retrieve the currently active LLM profile from settings.

    Falls back to the first profile if the active ID is invalid,
    or returns an empty dict if no profiles exist.

    Returns:
        The active profile dictionary (may be empty).
    """
    profiles: list[dict[str, Any]] = settings.get("llm_profiles", [])
    active_id: str | None = settings.get("active_llm_profile_id")
    for profile in profiles:
        if profile.get("id") == active_id:
            return profile
    # Fallback to first profile if active is invalid
    if profiles:
        return profiles[0]
    return {}


def make_preset_path_relative(path: str | None) -> str | None:
    """Convert an absolute path to a relative path rooted at :data:`BASE_DIR`.

    Special values ``None`` and ``"random"`` are returned unchanged.

    Args:
        path: The filesystem path to relativize.

    Returns:
        Relative path, or the original value for sentinel cases.
    """
    if not path or path == RANDOM_PATH:
        return path
    if path.startswith(BASE_DIR):
        return os.path.relpath(path, BASE_DIR)
    return path


def resolve_preset_path(path: str | None) -> str | None:
    """Resolve a (possibly relative) preset path to an absolute filesystem path.

    Args:
        path: The path to resolve.  ``None`` and ``"random"`` are returned as-is.

    Returns:
        Absolute path, or the original value for sentinel cases.
    """
    if not path:
        return None
    if path == RANDOM_PATH:
        return RANDOM_PATH
    if os.path.isabs(path):
        return path
    full: str = os.path.join(BASE_DIR, path)
    return full


def check_system_dependencies() -> None:
    """Verify that required system tools (ffmpeg, ffprobe) are installed.

    Attempts auto-installation via ``apt-get`` on Debian-based systems when
    tools are missing.  Also checks for emoji font support and attempts
    to install ``fonts-symbola`` if needed.

    Raises:
        RuntimeError: If ffmpeg or ffprobe cannot be found and auto-installation
            fails.
    """
    ffmpeg_found: bool = shutil.which("ffmpeg") is not None
    ffprobe_found: bool = shutil.which("ffprobe") is not None

    # Check for emoji fonts to prevent square glyphs ("tofu")
    if shutil.which("fc-list") is not None:
        _check_emoji_fonts()

    if ffmpeg_found and ffprobe_found:
        return

    logger.error("System dependencies 'ffmpeg' or 'ffprobe' are missing.")
    console.print(
        "[bold yellow]System dependencies 'ffmpeg' or 'ffprobe' are missing.[/]"
    )

    apt_found: bool = shutil.which("apt-get") is not None
    if apt_found:
        _auto_install_ffmpeg()

    if shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None:
        return

    logger.error(
        "Required system packages 'ffmpeg' and 'ffprobe' "
        "could not be resolved automatically."
    )
    console.print(
        "[bold red]Please install ffmpeg and ffprobe manually to proceed.[/]"
    )
    console.print("Instructions:")
    console.print("- Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y ffmpeg")
    console.print("- macOS: brew install ffmpeg")
    console.print("- Windows: scoop install ffmpeg or choco install ffmpeg")
    raise RuntimeError("ffmpeg and ffprobe are required but not installed.")


def download_default_assets_if_empty() -> None:
    """Download default background music if the music directory is empty.

    Also logs a warning if no background videos are found and clears
    the corresponding state key.
    """
    from generator import download_file

    # Check background videos
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    video_files: list[str] = [
        os.path.basename(f) for f in list_video_files(VIDEOS_DIR, exclude_sfx=False)
    ]
    if not video_files:
        state["bg_video_path"] = None
        console.print(
            "[bold yellow]No background videos found. "
            "Add .mp4 files to videos/ directory, "
            "or the server will run without a default background.[/]"
        )
    elif not state.get("bg_video_path"):
        latest_video: str = sorted(
            video_files,
            key=lambda x: os.path.getmtime(os.path.join(VIDEOS_DIR, x)),
            reverse=True,
        )[0]
        state["bg_video_path"] = os.path.join(VIDEOS_DIR, latest_video)

    # Check background music
    os.makedirs(MUSIC_DIR, exist_ok=True)
    music_files: list[str] = [
        os.path.basename(f) for f in list_music_files(MUSIC_DIR)
    ]
    if not music_files:
        console.print(
            "[bold yellow]No music tracks found in music/. "
            "Downloading default background music...[/]"
        )
        dest_music: str = os.path.join(MUSIC_DIR, "default_music.mp3")
        try:
            download_file(
                DEFAULT_MUSIC_URL,
                dest_music,
                "Default Background Music (SoundHelix Song 1)",
            )
            state["bg_music_path"] = dest_music
            console.print("[green]Successfully downloaded and selected default music track.[/]")
        except Exception as e:
            logger.error(
                "Failed to download default music track from %s: %s",
                DEFAULT_MUSIC_URL,
                e,
                exc_info=True,
            )
            console.print(f"[red]Failed to download default music track: {e}[/]")
    elif not state.get("bg_music_path"):
        latest_music: str = sorted(
            music_files,
            key=lambda x: os.path.getmtime(os.path.join(MUSIC_DIR, x)),
            reverse=True,
        )[0]
        state["bg_music_path"] = os.path.join(MUSIC_DIR, latest_music)


# --- Internal helpers ---


def _check_emoji_fonts() -> None:
    """Check for emoji/symbol font support and attempt auto-installation if missing."""
    try:
        res: subprocess.CompletedProcess = subprocess.run(
            ["fc-list", ":", "family"], capture_output=True, text=True
        )
        families: str = res.stdout.lower()
        if not any(p in families for p in EMOJI_FONT_PATTERNS):
            console.print(
                "[bold yellow]Warning: No emoji or symbol fonts detected. "
                "Subtitle emojis may render as squares.[/]"
            )
            apt_found: bool = shutil.which("apt-get") is not None
            if apt_found:
                _auto_install_emoji_fonts()
    except Exception as e:
        logger.warning("Error checking system fonts: %s", e, exc_info=True)


def _auto_install_ffmpeg() -> None:
    """Attempt to install ffmpeg via apt-get."""
    console.print("[yellow]Attempting to install 'ffmpeg' using apt-get...[/]")
    try:
        _is_root: bool = hasattr(os, "getuid") and os.getuid() == 0
        cmd_prefix: list[str] = [] if _is_root else ["sudo"]

        console.print("[yellow]Running: apt-get update -y[/]")
        subprocess.run(
            cmd_prefix + ["apt-get", "update", "-y"], check=True, timeout=120
        )

        console.print("[yellow]Running: apt-get install -y ffmpeg[/]")
        subprocess.run(
            cmd_prefix + ["apt-get", "install", "-y", "ffmpeg"],
            check=True,
            timeout=300,
        )

        if shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None:
            console.print("[green]Successfully installed ffmpeg/ffprobe via apt-get.[/]")
    except Exception as e:
        logger.error(
            "Auto-installation of ffmpeg failed: %s", e, exc_info=True
        )
        console.print(f"[red]Auto-installation failed: {e}[/]")


def _auto_install_emoji_fonts() -> None:
    """Attempt to install fonts-symbola via apt-get."""
    console.print(
        "[yellow]Attempting to install 'fonts-symbola' via apt-get...[/]"
    )
    try:
        _is_root: bool = hasattr(os, "getuid") and os.getuid() == 0
        cmd_prefix: list[str] = [] if _is_root else ["sudo"]
        subprocess.run(
            cmd_prefix + ["apt-get", "update", "-y"],
            check=True,
            timeout=120,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            cmd_prefix + ["apt-get", "install", "-y", "fonts-symbola"],
            check=True,
            timeout=300,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        console.print("[green]Successfully installed 'fonts-symbola'![/]")
    except Exception as e:
        logger.warning(
            "Failed to auto-install 'fonts-symbola': %s", e, exc_info=True
        )
        console.print(
            "[yellow]Auto-installation of fonts-symbola failed. "
            "Emojis may render as squares.[/]"
        )
