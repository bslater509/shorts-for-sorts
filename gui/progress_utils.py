"""Progress display utilities for batch job status reporting.

Provides functions to map job status strings to estimated completion
percentages, render visual progress bars, and log memory usage.
"""

from __future__ import annotations

import os
import re
import time as _time
from collections.abc import Callable

import psutil

import time as _system_time

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

# Low-memory warning threshold (MB)
LOW_MEMORY_THRESHOLD_MB: int = 2000

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


def log_top_memory_processes(n: int = 5) -> None:
    """Log the top *n* processes by RSS for memory diagnostics.

    Args:
        n: Maximum number of processes to log.
    """
    procs: list[tuple[float, int, str]] = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            rss_mb: float = proc.info["memory_info"].rss / 1024 / 1024  # type: ignore[index]
            if rss_mb > 10.0:
                name: str = proc.info["name"] or "?"  # type: ignore[index]
                procs.append((rss_mb, proc.info["pid"], name))  # type: ignore[index]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(reverse=True)
    logger.info("[Batch Memory] Top %d processes by RSS:", min(n, len(procs)))
    for rss_mb, pid, name in procs[:n]:
        logger.info("  PID %d %s = %.0fMB", pid, name, rss_mb)


def log_self_oom_score() -> None:
    """Log this process's OOM score and adjustment value.

    Reads ``/proc/self/oom_score`` and ``/proc/self/oom_score_adj``.  Silently
    skips on permission or read errors.
    """
    try:
        with open("/proc/self/oom_score", encoding="utf-8") as fh:
            score: int = int(fh.read().strip())
        with open("/proc/self/oom_score_adj", encoding="utf-8") as fh:
            score_adj: int = int(fh.read().strip())
    except (OSError, ValueError):
        return
    logger.info(
        "[Batch Memory] Self OOM: score=%d, score_adj=%d", score, score_adj
    )


def _log_memory_warning() -> None:
    """Log a warning if available system memory is below the threshold."""
    try:
        with open("/proc/meminfo") as f:
            data: str = f.read()
        mem_map: dict[str, int] = {}
        for line in data.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                mem_map[parts[0].strip()] = int(parts[1].strip().split()[0])
        avail_mb: int = mem_map.get("MemAvailable", 0) // 1024
        total_mb: int = mem_map.get("MemTotal", 0) // 1024
        if avail_mb < LOW_MEMORY_THRESHOLD_MB:
            logger.warning(
                "Low memory: %dMB available / %dMB total — batch may risk OOM",
                avail_mb,
                total_mb,
            )
            log_top_memory_processes()
    except Exception:
        pass


def _wait_for_memory(threshold_mb: int = 3000, poll_interval: float = 5.0) -> None:
    """Block until available system memory is above ``threshold_mb``.

    Called before submitting a video compilation job to avoid OOM kills.
    Logs a warning on the first wait, then polls silently while re-logging
    top memory consumers and the self OOM score periodically.

    Args:
        threshold_mb: Minimum available MB required to proceed.
        poll_interval: Seconds between memory re-checks.
    """
    from gui.batch_engine import batch_state  # noqa: PLC0415
    from gui.exceptions import BatchCancelledError  # noqa: PLC0415

    warned = False
    _poll_count = 0
    while True:
        if batch_state["should_cancel"]:
            raise BatchCancelledError("Batch cancelled: low-memory wait interrupted")
        try:
            with open("/proc/meminfo") as f:
                data = f.read()
            mem_map: dict[str, int] = {}
            for line in data.splitlines():
                parts = line.split(":")
                if len(parts) == 2:
                    mem_map[parts[0].strip()] = int(parts[1].strip().split()[0])
            avail_mb: int = mem_map.get("MemAvailable", 0) // 1024
        except Exception:
            return  # can't read, proceed anyway
        if avail_mb >= threshold_mb:
            return
        if not warned:
            logger.warning(
                "Low memory (%dMB available) — pausing video job submission until %dMB is free",
                avail_mb,
                threshold_mb,
            )
            warned = True
        _poll_count += 1
        if _poll_count >= 12:
            _poll_count = 0
            log_top_memory_processes()
            log_self_oom_score()
        _time.sleep(poll_interval)


def wait_for_available_memory(
    threshold_mb: int = 2500,
    poll_interval: float = 5.0,
    abort_check: Callable[[], bool] | None = None,
    log_interval_seconds: float = 60.0,
) -> None:
    """Block until available system memory is above ``threshold_mb``.

    On the first wait iteration, logs a warning and the top memory-consuming
    processes for diagnostics.  Every ``log_interval_seconds`` worth of polling,
    re-logs the top memory processes and self OOM score.  Polls silently
    otherwise.

    Args:
        threshold_mb: Minimum available MB required to proceed.
        poll_interval: Seconds between memory re-checks.
        abort_check: Optional callback; if it returns ``True``, raises
            ``BatchCancelledError``.
        log_interval_seconds: Polling time (``poll_count * poll_interval``)
            after which to periodically re-log top memory processes and the
            self OOM score while still waiting.

    Raises:
        BatchCancelledError: If ``abort_check`` returns ``True``.
    """
    warned = False
    poll_count = 0
    while True:
        if abort_check is not None and abort_check():
            from gui.exceptions import BatchCancelledError  # noqa: PLC0415

            raise BatchCancelledError("Batch cancelled: low-memory wait interrupted")
        mem: psutil.svmem = psutil.virtual_memory()
        avail_mb: float = mem.available / 1024 / 1024
        if avail_mb >= threshold_mb:
            if warned:
                logger.info(
                    "[Batch Memory] Memory recovered to %.0fMB, proceeding",
                    avail_mb,
                )
            return
        if not warned:
            logger.warning(
                "Low memory (%.0fMB available) — pausing until %.0fMB is free (phase: transcription)",
                avail_mb,
                threshold_mb,
            )
            log_top_memory_processes()
            warned = True
        poll_count += 1
        if (poll_count * poll_interval) >= log_interval_seconds:
            log_top_memory_processes()
            log_self_oom_score()
            poll_count = 0
        _time.sleep(poll_interval)


def start_memory_telemetry(interval_seconds: float = 60.0) -> "threading.Event":
    """Start a background thread that periodically logs memory diagnostics.

    The daemon thread wakes every ``interval_seconds`` and logs RSS/available
    memory, the top *5* processes by RSS, this process's OOM score, and (when
    cgroup v2 is available) cgroup memory usage/peak.

    Args:
        interval_seconds: Seconds between telemetry log batches.

    Returns:
        A ``threading.Event`` used as the stop signal; pass it to
        :func:`stop_memory_telemetry` to stop the thread.
    """
    import threading

    stop_event: threading.Event = threading.Event()

    def _run() -> None:
        while not stop_event.wait(interval_seconds):
            log_memory_usage("telemetry")
            log_top_memory_processes(n=5)
            log_self_oom_score()
            if os.path.exists("/sys/fs/cgroup/memory.current"):
                try:
                    with open("/sys/fs/cgroup/memory.current", encoding="utf-8") as fh:
                        current: int = int(fh.read().strip())
                    with open("/sys/fs/cgroup/memory.peak", encoding="utf-8") as fh:
                        peak: int = int(fh.read().strip())
                except (OSError, ValueError):
                    continue
                logger.info(
                    "[Batch Memory] Cgroup memory.current=%.0fMB, memory.peak=%.0fMB",
                    current / 1024 / 1024,
                    peak / 1024 / 1024,
                )

    thread: threading.Thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return stop_event


def stop_memory_telemetry(stop_event: "threading.Event") -> None:
    """Stop the memory telemetry thread started by :func:`start_memory_telemetry`.

    Sets the stop event; does not join the (daemon) thread so shutdown is not
    blocked.

    Args:
        stop_event: The event returned by :func:`start_memory_telemetry`.
    """
    stop_event.set()
    logger.info("[Batch Memory] Memory telemetry stopped")


# --- Subprocess accounting helpers ---


def log_subprocess_start(name: str, cmd_preview: str = "") -> float:
    """Log the start of an external subprocess and return the start timestamp.

    Call :func:`log_subprocess_end` with the returned timestamp when the
    subprocess completes to log elapsed time and (optionally) the PID.

    Args:
        name: Human-readable subprocess label (e.g. ``"ffmpeg-thumbnail"``).
        cmd_preview: Optional truncated command for log context.

    Returns:
        The ``time.monotonic()`` value captured at call time.
    """
    start: float = _system_time.monotonic()
    logger.info(
        "[Subprocess] Starting %s%s", name, f" ({cmd_preview})" if cmd_preview else ""
    )
    return start


def log_subprocess_end(
    name: str, start: float, pid: int | None = None
) -> None:
    """Log subprocess completion with elapsed time and optional PID.

    Args:
        name: Same label passed to :func:`log_subprocess_start`.
        start: Timestamp returned by :func:`log_subprocess_start`.
        pid: Optional subprocess PID for process-tree identification.
    """
    elapsed: float = _system_time.monotonic() - start
    pid_info: str = f" (pid={pid})" if pid is not None else ""
    logger.info(
        "[Subprocess] Finished %s%s in %.1fs", name, pid_info, elapsed
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
    elif status == "Waiting for LLM" or status == "LLM Script (0 words)":
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
    elif status == "Done" or status.startswith("Posting to TikTok"):
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
