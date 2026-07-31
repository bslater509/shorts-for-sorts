"""Progress display utilities for batch job status reporting.

Provides functions to map job status strings to estimated completion
percentages, render visual progress bars, and log memory usage.
"""

from __future__ import annotations

import re

import psutil

from gui.config import logger

# --- Progress percentage constants ---

# LLM phase: 0–20%
PROGRESS_QUEUED: int = 0
PROGRESS_WAITING_LLM: int = 5
PROGRESS_LLM_SCRIPT_BASE: int = 5
PROGRESS_LLM_SCRIPT_MAX: int = 14
PROGRESS_LLM_METADATA: int = 15
PROGRESS_WAITING_COMPILE: int = 18

# Voice generation phase: 20–45%
PROGRESS_COMPILING: int = 20
PROGRESS_VOICE_BASE: int = 20
PROGRESS_VOICE_RANGE: int = 25

# Transcription phase: 45–55%
PROGRESS_TRANSCRIBE_BASE: int = 45
PROGRESS_TRANSCRIBE_RANGE: int = 10

# Subtitles / render phase: 55–100%
PROGRESS_SUBTITLES: int = 55
PROGRESS_RENDER_BASE: int = 55
PROGRESS_RENDER_RANGE: int = 45

PROGRESS_DONE: int = 100

# Number of words at which LLM script percentage is capped
LLM_SCRIPT_WORD_CAP: int = 400

# Regex patterns for extracting progress values from status strings
_WORD_COUNT_RE: re.Pattern = re.compile(r"\((\d+)\s*words\)")
_VOICE_FRACTION_RE: re.Pattern = re.compile(r"\((\d+)/(\d+)\)")
_TRANSCRIBE_PCT_RE: re.Pattern = re.compile(r"\((\d+)%\)")
_RENDER_PCT_RE: re.Pattern = re.compile(r"\((\d+\.?\d*)%\)")

# Progress bar rendering defaults
PROGRESS_BAR_WIDTH: int = 15


def log_memory_usage(stage: str) -> None:
    """Log current process RSS and system memory statistics.

    Args:
        stage: A label describing the current pipeline stage (e.g.
            ``"Video: after TTS generation"``).
    """
    proc: psutil.Process = psutil.Process()
    rss_mb: float = proc.memory_info().rss / 1024 / 1024
    mem: psutil.svmem = psutil.virtual_memory()
    logger.info(
        f"[Batch Memory] {stage}: RSS={rss_mb:.0f}MB | "
        f"Avail={mem.available / 1024 / 1024:.0f}MB / "
        f"{mem.total / 1024 / 1024:.0f}MB ({mem.percent:.1f}%)"
    )


def get_progress_percentage(status: str) -> int | None:
    """Map a job status string to an estimated completion percentage.

    Args:
        status: The job status string (e.g. ``"LLM Script (42 words)"``,
            ``"Voice Generation (3/6)"``).

    Returns:
        An integer percentage ``[0, 100]``, or ``None`` for terminal
        failed statuses.
    """
    if status == "Queued":
        return PROGRESS_QUEUED
    elif status.startswith("Connecting to LLM"):
        return 2
    elif status == "Waiting for LLM":
        return PROGRESS_WAITING_LLM
    elif status == "LLM Script (0 words)":
        return PROGRESS_WAITING_LLM
    elif status.startswith("LLM Script"):
        match = _WORD_COUNT_RE.search(status)
        if match:
            word_count: int = int(match.group(1))
            pct: int = min(
                PROGRESS_LLM_SCRIPT_MAX,
                PROGRESS_LLM_SCRIPT_BASE + int((word_count / LLM_SCRIPT_WORD_CAP) * 9),
            )
            return pct
        return PROGRESS_LLM_SCRIPT_BASE
    elif status == "LLM Metadata":
        return PROGRESS_LLM_METADATA
    elif status == "Waiting for Compilation":
        return PROGRESS_WAITING_COMPILE
    elif status == "Compiling":
        return PROGRESS_COMPILING
    elif status.startswith("Voice Generation"):
        match = _VOICE_FRACTION_RE.search(status)
        if match:
            s_idx: int = int(match.group(1))
            total: int = int(match.group(2))
            if total > 0:
                return PROGRESS_VOICE_BASE + int((s_idx / total) * PROGRESS_VOICE_RANGE)
        return PROGRESS_VOICE_BASE
    elif status == "Reusing Cache (Voice)":
        return PROGRESS_TRANSCRIBE_BASE
    elif status.startswith("Transcription"):
        match = _TRANSCRIBE_PCT_RE.search(status)
        if match:
            pct = int(match.group(1))
            return PROGRESS_TRANSCRIBE_BASE + int((pct / 100) * PROGRESS_TRANSCRIBE_RANGE)
        return PROGRESS_TRANSCRIBE_BASE
    elif status == "Subtitles":
        return PROGRESS_SUBTITLES
    elif status.startswith("FFmpeg Rendering"):
        match = _RENDER_PCT_RE.search(status)
        if match:
            pct = float(match.group(1))
            return PROGRESS_RENDER_BASE + int((pct / 100) * PROGRESS_RENDER_RANGE)
        return PROGRESS_RENDER_BASE
    elif status == "Done":
        return PROGRESS_DONE
    elif status == "Cancelled" or status.startswith("Failed"):
        return None
    return PROGRESS_QUEUED


def make_progress_bar(
    percentage: int, status: str, width: int = PROGRESS_BAR_WIDTH
) -> str:
    """Create a coloured Rich-compatible progress bar string.

    Args:
        percentage: Completion percentage (0–100).
        status: Job status string used to select the colour theme.
        width: Number of block characters in the bar.

    Returns:
        A Rich-markup string like ``"[cyan]████[/][grey37]░░░[/] 50% 🔄 Status..."``.
    """
    filled: int = int(width * percentage / 100)
    filled = max(0, min(width, filled))
    empty: int = width - filled

    if status == "Done":
        bar_color: str = "green"
        pct_color: str = "green"
        desc: str = "[bold green]✓ Done[/]"
    elif status == "Queued":
        bar_color = "grey37"
        pct_color = "grey37"
        desc = "[dim]Queued...[/]"
    else:
        bar_color = "cyan"
        pct_color = "yellow"
        desc = f"[bold yellow]🔄 {status}...[/]"

    bar: str = (
        f"[{bar_color}]" + "█" * filled + f"[/{bar_color}]"
        f"[grey37]" + "░" * empty + "[/grey37]"
    )
    return f"{bar} [{pct_color}]{percentage:3d}%[/{pct_color}] {desc}"


def format_elapsed(duration: float) -> str:
    """Format a duration in seconds as a human-readable string.

    Args:
        duration: Elapsed time in seconds (may be negative, treated as zero).

    Returns:
        Formatted string like ``"5s"``, ``"1m 35s"``, ``"61m 01s"``.
    """
    total_seconds: int = int(duration) if duration >= 0 else 0
    m: int = total_seconds // 60
    s: int = total_seconds % 60
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"
