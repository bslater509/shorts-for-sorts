"""Batch generation REST API routes."""

from __future__ import annotations

import json
import multiprocessing
import os
import re
import threading
import time
from typing import Any

import psutil
from fastapi import APIRouter, HTTPException

from gui.batch_engine import (
    _PHASE_TRACKING_KEYS,
    _batch_lock,
    _batch_state_lock,
    _compute_eta,
    _log_memory_warning,
    batch_state,
    batch_worker_thread,
)
from gui.config import (
    CANCELLED_CONFIGS_FILE,
    DISMISSED_JOBS_FILE,
    FAILED_CONFIGS_FILE,
    logger,
)
from gui.models import BatchStartRequest

router: APIRouter = APIRouter()

# --- Constants ---

MAX_SHORTS: int = 100
"""Maximum number of shorts allowed in a single batch."""

MIN_SHORTS: int = 1

# Pipeline progress segment boundaries (for frontend display)
PROGRESS_SEGMENTS: list[dict[str, Any]] = [
    {"name": "LLM", "start": 0, "end": 20},
    {"name": "Voice", "start": 20, "end": 45},
    {"name": "Transcribe", "start": 45, "end": 55},
    {"name": "Render", "start": 55, "end": 100},
]


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _load_dismissed_jobs() -> set[int]:
    """Load dismissed job IDs from disk.

    Returns:
        Set of job IDs, or an empty set on any failure.
    """
    try:
        if os.path.exists(DISMISSED_JOBS_FILE):
            with open(DISMISSED_JOBS_FILE) as f:
                data: Any = json.load(f)
            if isinstance(data, list):
                return set(data)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load dismissed jobs: %s", e)
    return set()


def _save_dismissed_jobs(job_ids: set[int]) -> None:
    """Persist dismissed job IDs to disk as a JSON array of ints.

    Args:
        job_ids: Set of dismissed job IDs.
    """
    try:
        os.makedirs(os.path.dirname(DISMISSED_JOBS_FILE), exist_ok=True)
        with open(DISMISSED_JOBS_FILE, "w") as f:
            json.dump(sorted(job_ids), f, indent=2)
    except OSError as e:
        logger.warning("Failed to save dismissed jobs: %s", e)


def _load_cancelled_configs() -> list[dict[str, Any]]:
    """Load cancelled job configs from disk.

    Returns:
        List of config dicts, or an empty list on failure.
    """
    try:
        if os.path.exists(CANCELLED_CONFIGS_FILE):
            with open(CANCELLED_CONFIGS_FILE) as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load cancelled configs: %s", e)
    return []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api/prompts")
def get_prompts() -> dict[str, str]:
    """Return the library of prompt templates."""
    from gui.config import load_prompt_templates

    return load_prompt_templates()


@router.post("/api/batch/start")
def start_batch(data: BatchStartRequest) -> dict[str, str]:
    """Start a new batch generation run.

    Args:
        data: Batch parameters including number of shorts and optional overrides.

    Returns:
        Status message indicating the batch has started.
    """
    _log_memory_warning()
    num_shorts: int = data.num_shorts
    if num_shorts < MIN_SHORTS or num_shorts > MAX_SHORTS:
        raise HTTPException(
            status_code=400,
            detail="Number of shorts must be between 1 and 100.",
        )

    # Validate TikTok session ID if posting is enabled
    if data.post_to_tiktok:
        sessionid: str = str(
            __import__("gui.state", fromlist=["settings"]).settings.get(
                "tiktok_sessionid", ""
            )
            or ""
        ).strip()
        if not sessionid:
            raise HTTPException(
                status_code=400,
                detail="TikTok session ID is missing. Add it in the Settings panel before enabling Post to TikTok.",
            )

    # Create expensive manager outside lock so we don't block for too long
    new_manager = multiprocessing.Manager()
    new_shared = new_manager.dict()

    with _batch_lock:
        if batch_state["in_progress"]:
            new_manager.shutdown()
            raise HTTPException(
                status_code=400, detail="A batch job is already running."
            )
        batch_state["in_progress"] = True
        batch_state["num_shorts"] = num_shorts
        batch_state["progress_dict"].clear()
        batch_state["job_configs"] = {}
        batch_state["manager"] = new_manager
        batch_state["shared_progress"] = new_shared

    t = threading.Thread(
        target=batch_worker_thread,
        args=(
            num_shorts,
            data.prompts,
            data.enable_emojis,
            data.enable_emoji_animation,
            data.emoji_scale_factor,
            data.emoji_hold_duration,
            data.emoji_throw_max_count,
            data.emoji_styles,
            data.layout,
            data.voice_id,
            data.sub_animation_style,
            data.words_per_screen,
            data.single_word_mode,
            data.bg_music_path,
            data.script_temp,
            data.meta_temp,
            data.max_workers,
            data.llm_max_workers,
            data.post_to_tiktok or False,
        ),
        daemon=True,
    )
    t.start()
    return {
        "status": "started",
        "message": f"Batch generation of {num_shorts} shorts started.",
    }


DURATION_RE: re.Pattern = re.compile(r"^Duration\s*:\s*([\d.]+)", re.I)


def _collect_system_stats() -> dict[str, Any]:
    """Gather host resource metrics, degrading gracefully on unsupported platforms.

    Each psutil/``os.getloadavg`` call is guarded so a missing capability on a
    given platform never crashes the status endpoint — the affected metric
    falls back to ``0.0`` (``1`` for ``cpu_count``).

    Returns:
        Dict of system metrics (CPU %, memory %, disk %, RSS in MB, swap %,
        1-minute load average, and CPU count).
    """
    from gui.config import OUTPUT_DIR

    stats: dict[str, Any] = {
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "disk_percent": 0.0,
        "rss_mb": 0.0,
        "swap_percent": 0.0,
        "load_avg": 0.0,
        "cpu_count": 1,
    }

    try:
        stats["cpu_percent"] = psutil.cpu_percent(interval=None)
    except Exception:
        pass
    try:
        stats["memory_percent"] = psutil.virtual_memory().percent
    except Exception:
        pass
    try:
        stats["rss_mb"] = psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    try:
        stats["swap_percent"] = psutil.swap_memory().percent
    except Exception:
        pass
    try:
        stats["cpu_count"] = psutil.cpu_count() or 1
    except Exception:
        pass
    try:
        stats["load_avg"] = os.getloadavg()[0]
    except (OSError, AttributeError):
        pass
    try:
        stats["disk_percent"] = psutil.disk_usage(OUTPUT_DIR).percent
    except Exception:
        # Fall back to the filesystem root, then give up silently.
        try:
            stats["disk_percent"] = psutil.disk_usage("/").percent
        except Exception:
            pass
    return stats


def _compute_net_io_rate(now: float) -> tuple[float, float]:
    """Compute per-second network throughput in KB/s.

    Derives the recv/sent rate from the delta between the current psutil
    counters and the previous snapshot stored in ``batch_state`` under
    ``_batch_state_lock``. The current counters and timestamp are persisted
    back to ``batch_state`` so the next call can compute its own rate.

    Args:
        now: Monotonic-ish wall-clock timestamp for the current sample.

    Returns:
        ``(recv_kbs, sent_kbs)`` in kilobytes per second, or ``(0.0, 0.0)``
        when counters are unavailable or no prior snapshot exists.
    """
    try:
        counters = psutil.net_io_counters()
        recv_bytes = counters.bytes_recv
        sent_bytes = counters.bytes_sent
    except Exception:
        return 0.0, 0.0

    prev_counters = batch_state.get("_net_counters")
    prev_time = batch_state.get("_net_time")
    batch_state["_net_counters"] = (recv_bytes, sent_bytes)
    batch_state["_net_time"] = now

    if not prev_counters or not prev_time or now <= prev_time:
        return 0.0, 0.0

    dt = now - prev_time
    if dt <= 0:
        return 0.0, 0.0
    recv_kbs = max(0.0, (recv_bytes - prev_counters[0]) / dt / 1024.0)
    sent_kbs = max(0.0, (sent_bytes - prev_counters[1]) / dt / 1024.0)
    return recv_kbs, sent_kbs


def build_batch_status() -> dict[str, Any]:
    """Return the current batch status with per-job progress, ETAs, and pipeline stats."""
    from gui.config import OUTPUT_DIR
    from gui.progress_utils import get_progress_percentage

    with _batch_state_lock:
        if "_dismissed_jobs" not in batch_state:
            batch_state["_dismissed_jobs"] = _load_dismissed_jobs()
        dismissed: set[int] = batch_state.get("_dismissed_jobs", set())

        completed_durations: list[float] = []
        for i in range(1, batch_state["num_shorts"] + 1):
            st = batch_state["progress_dict"].get(f"{i}_start")
            et = batch_state["progress_dict"].get(f"{i}_end")
            status_i = batch_state["progress_dict"].get(i, "Queued")
            if st and et and status_i == "Done":
                completed_durations.append(et - st)
        avg_completion_time: float | None = (
            sum(completed_durations) / len(completed_durations)
            if completed_durations
            else None
        )

        smoothed_etas = batch_state.get("_smoothed_eta", {})
        phase_weights = batch_state.get("_phase_weights")

        cancelled_count: int = 0
        failed_count: int = 0
        jobs: list[dict[str, Any]] = []

        for i in range(1, batch_state["num_shorts"] + 1):
            status: str = batch_state["progress_dict"].get(i, "Queued")
            pct = get_progress_percentage(status)

            start_time = batch_state["progress_dict"].get(f"{i}_start")
            end_time = batch_state["progress_dict"].get(f"{i}_end")

            is_cancelled = status == "Cancelled"
            is_failed = status.startswith("Failed") and not is_cancelled
            if is_cancelled:
                cancelled_count += 1
            elif is_failed:
                failed_count += 1

            error_detail: str | None
            if is_cancelled:
                error_detail = "Cancelled by user"
            elif is_failed:
                error_detail = status
            else:
                error_detail = None

            is_dismissed = i in dismissed

            job_phase_times: dict[str, float] = {}
            for suffix in _PHASE_TRACKING_KEYS:
                val = batch_state["progress_dict"].get(f"{i}{suffix}")
                if val:
                    job_phase_times[suffix] = val

            eta_str, eta_seconds, elapsed_str, eta_llm, eta_video = _compute_eta(
                start_time,
                end_time,
                pct,
                status,
                job_phase_times,
                avg_completion_time,
                smoothed_etas,
                i,
                phase_weights=phase_weights,
                avg_llm_duration=batch_state.get("_avg_llm_duration"),
                avg_video_duration=batch_state.get("_avg_video_duration"),
                job_features=batch_state.get("_job_features", {}).get(i),
                per_job_stats=batch_state.get("_per_job_stats"),
            )

            detail = batch_state["job_details"].get(i, {})
            config = batch_state.get("job_configs", {}).get(i, {})

            out_filename = config.get("output_filename")
            video_url = None
            thumbnail = None
            size = None
            duration = None

            if out_filename:
                basename = os.path.splitext(out_filename)[0]
                thumbnail = f"/api/gallery/thumbnail/{basename}.jpg"
                out_path = os.path.join(OUTPUT_DIR, out_filename)
                if os.path.exists(out_path):
                    video_url = f"/output/{out_filename}"
                    try:
                        size = os.path.getsize(out_path)
                    except OSError:
                        pass

                txt_path = os.path.join(OUTPUT_DIR, f"{basename}.txt")
                if os.path.exists(txt_path):
                    try:
                        with open(txt_path, encoding="utf-8") as _f:
                            for _line in _f:
                                _m = DURATION_RE.match(_line.strip())
                                if _m:
                                    duration = float(_m.group(1))
                                    break
                    except Exception:
                        pass

            jobs.append(
                {
                    "id": i,
                    "topic": detail.get("topic", "Unknown"),
                    "voice": detail.get("voice", "Unknown"),
                    "layout": detail.get("layout", "Unknown"),
                    "enable_emojis": detail.get("enable_emojis", False),
                    "status": status,
                    "progress": pct if pct is not None else 0,
                    "failed": is_failed,
                    "cancelled": is_cancelled,
                    "error_detail": error_detail,
                    "dismissed": is_dismissed,
                    "elapsed": elapsed_str,
                    "eta": eta_str,
                    "eta_seconds": eta_seconds,
                    "eta_llm": round(eta_llm, 1) if eta_llm > 0 else 0,
                    "eta_video": round(eta_video, 1) if eta_video > 0 else 0,
                    "output_filename": out_filename,
                    "video_url": video_url,
                    "thumbnail": thumbnail,
                    "size": size,
                    "duration": duration,
                    "tiktok_posted": batch_state.get("tiktok_post_results", {}).get(i, {}).get("status") == "posted",
                    "tiktok_post_failed": batch_state.get("tiktok_post_results", {}).get(i, {}).get("status") == "failed",
                }
            )

        in_progress = batch_state["in_progress"]
        num_shorts = batch_state["num_shorts"]
        max_workers = batch_state.get("max_workers", 1)
        llm_max_workers = batch_state.get("llm_max_workers", 5)

        avg_llm_dur: float = batch_state.get("_avg_llm_duration", 30) or 30
        avg_video_dur: float = batch_state.get("_avg_video_duration", 60) or 60
        total_llm: float = 0.0
        total_video: float = 0.0
        for j in jobs:
            s = j["status"]
            if s == "Done" or s.startswith("Failed") or s == "Cancelled" or j.get("dismissed", False):
                continue
            if s != "Queued" and j.get("eta_llm") is not None:
                total_llm += j["eta_llm"]
                total_video += j["eta_video"]
            else:
                total_llm += avg_llm_dur
                total_video += avg_video_dur
        global_eta_seconds: float = (
            total_llm / max(1, llm_max_workers)
            + total_video / max(1, max_workers)
        )

        # System stats (network rate depends on batch_state counters, so this
        # must happen while holding the lock).
        now = time.time()
        sys_stats = _collect_system_stats()
        net_recv_kbs, net_sent_kbs = _compute_net_io_rate(now)

    return {
        "in_progress": in_progress,
        "num_shorts": num_shorts,
        "jobs": jobs,
        "max_workers": max_workers,
        "global_eta_seconds": round(global_eta_seconds, 1),
        "cpu_percent": round(sys_stats["cpu_percent"], 1),
        "memory_percent": round(sys_stats["memory_percent"], 1),
        "disk_percent": round(sys_stats["disk_percent"], 1),
        "rss_mb": round(sys_stats["rss_mb"], 1),
        "net_recv_kbs": round(net_recv_kbs, 2),
        "net_sent_kbs": round(net_sent_kbs, 2),
        "swap_percent": round(sys_stats["swap_percent"], 1),
        "load_avg": round(sys_stats["load_avg"], 2),
        "cpu_count": sys_stats["cpu_count"],
        "cancelledCount": cancelled_count,
        "failedCount": failed_count,
        "progress_segments": PROGRESS_SEGMENTS,
        "post_to_tiktok": batch_state.get("post_to_tiktok", False),
    }


@router.get("/api/batch/status")
def get_batch_status() -> dict[str, Any]:
    """Return the current batch status with per-job progress, ETAs, and pipeline stats."""
    return build_batch_status()


@router.get("/api/batch/job/{job_id}")
def get_batch_job_detail(job_id: int) -> dict[str, Any]:
    """Return detailed information about a specific batch job.

    Args:
        job_id: The 1-indexed job number.

    Returns:
        Job status, progress, ETA, and full configuration.
    """
    from gui.progress_utils import get_progress_percentage

    with _batch_state_lock:
        if job_id < 1 or job_id > batch_state["num_shorts"]:
            raise HTTPException(status_code=404, detail="Job not found")

        status = batch_state["progress_dict"].get(job_id, "Unknown")
        pct = get_progress_percentage(status)

        start_time = batch_state["progress_dict"].get(f"{job_id}_start")
        end_time = batch_state["progress_dict"].get(f"{job_id}_end")

        completed_durations = []
        for i in range(1, batch_state["num_shorts"] + 1):
            st = batch_state["progress_dict"].get(f"{i}_start")
            et = batch_state["progress_dict"].get(f"{i}_end")
            status_i = batch_state["progress_dict"].get(i, "Queued")
            if st and et and status_i == "Done":
                completed_durations.append(et - st)
        avg_completion_time = (
            sum(completed_durations) / len(completed_durations)
            if completed_durations
            else None
        )

        job_phase_times = {}
        for suffix in _PHASE_TRACKING_KEYS:
            val = batch_state["progress_dict"].get(f"{job_id}{suffix}")
            if val:
                job_phase_times[suffix] = val

        smoothed_etas = batch_state.get("_smoothed_eta", {})
        phase_weights = batch_state.get("_phase_weights")
        eta_str, eta_seconds, elapsed_str, eta_llm, eta_video = _compute_eta(
            start_time,
            end_time,
            pct,
            status,
            job_phase_times,
            avg_completion_time,
            smoothed_etas,
            job_id,
            phase_weights=phase_weights,
            avg_llm_duration=batch_state.get("_avg_llm_duration"),
            avg_video_duration=batch_state.get("_avg_video_duration"),
            job_features=batch_state.get("_job_features", {}).get(job_id),
            per_job_stats=batch_state.get("_per_job_stats"),
        )

        detail = batch_state["job_details"].get(job_id, {})
        config = batch_state.get("job_configs", {}).get(job_id, {})

    is_cancelled = status == "Cancelled"
    is_failed = status.startswith("Failed") and not is_cancelled

    if "_dismissed_jobs" not in batch_state:
        batch_state["_dismissed_jobs"] = _load_dismissed_jobs()
    is_dismissed = job_id in batch_state.get("_dismissed_jobs", set())

    if is_cancelled:
        error_detail = "Cancelled by user"
    elif is_failed:
        error_detail = status
    else:
        error_detail = None

    from gui.config import OUTPUT_DIR

    out_filename = config.get("output_filename")
    video_url = None
    thumbnail = None
    size = None
    duration = None

    if out_filename:
        basename = os.path.splitext(out_filename)[0]
        thumbnail = f"/api/gallery/thumbnail/{basename}.jpg"
        out_path = os.path.join(OUTPUT_DIR, out_filename)
        if os.path.exists(out_path):
            video_url = f"/output/{out_filename}"
            try:
                size = os.path.getsize(out_path)
            except OSError:
                pass

        txt_path = os.path.join(OUTPUT_DIR, f"{basename}.txt")
        if os.path.exists(txt_path):
            try:
                with open(txt_path, encoding="utf-8") as _f:
                    for _line in _f:
                        _m = DURATION_RE.match(_line.strip())
                        if _m:
                            duration = float(_m.group(1))
                            break
            except Exception:
                pass

    return {
        "id": job_id,
        "topic": detail.get("topic", ""),
        "voice_name": detail.get("voice", "Unknown"),
        "layout": detail.get("layout", "Unknown"),
        "enable_emojis": detail.get("enable_emojis", False),
        "status": status,
        "progress": pct if pct is not None else 0,
        "failed": is_failed,
        "cancelled": is_cancelled,
        "error_detail": error_detail,
        "dismissed": is_dismissed,
        "elapsed": elapsed_str,
        "eta": eta_str,
        "eta_seconds": eta_seconds,
        # Full config fields
        "prompt": config.get("prompt", ""),
        "voice_id": config.get("voice_id", ""),
        "bg_video_path": config.get("bg_video_path", ""),
        "bg_video_bottom_path": config.get("bg_video_bottom_path"),
        "bg_music_path": config.get("bg_music_path"),
        "music_volume": config.get("music_volume", 0),
        "voice_volume": config.get("voice_volume", 0),
        "sub_font": config.get("sub_font", ""),
        "sub_size": config.get("sub_size", 0),
        "sub_color": config.get("sub_color", ""),
        "sub_highlight": config.get("sub_highlight", ""),
        "sub_outline": config.get("sub_outline", ""),
        "sub_outline_width": config.get("sub_outline_width", 0),
        "sub_bold": config.get("sub_bold", False),
        "word_pop": config.get("word_pop", False),
        "word_pop_scale": config.get("word_pop_scale", 0),
        "inactive_dim": config.get("inactive_dim", False),
        "inactive_alpha": config.get("inactive_alpha", ""),
        "sub_uppercase": config.get("sub_uppercase", False),
        "voice_speed": config.get("voice_speed"),
        "sub_border_style": config.get("sub_border_style", 0),
        "sub_shadow_width": config.get("sub_shadow_width", 0),
        "sub_bg_color": config.get("sub_bg_color", ""),
        "sub_bg_alpha": config.get("sub_bg_alpha", ""),
        "single_word_mode": config.get("single_word_mode", False),
        "words_per_screen": config.get("words_per_screen", ""),
        "emoji_position": config.get("emoji_position", ""),
        "emoji_style": config.get("emoji_style", ""),
        "sub_animation_style": config.get("sub_animation_style", ""),
        "enable_emoji_animation": config.get("enable_emoji_animation", False),
        "emoji_scale_factor": config.get("emoji_scale_factor", 0),
        "emoji_hold_duration": config.get("emoji_hold_duration", 0),
        "emoji_throw_max_count": config.get("emoji_throw_max_count", 0),
        "script_temp": config.get("script_temp", 0),
        "meta_temp": config.get("meta_temp", 0),
        "model": config.get("model", ""),
        "system_prompt": config.get("system_prompt", ""),
        "output_filename": out_filename,
        "video_url": video_url,
        "thumbnail": thumbnail,
        "size": size,
        "duration": duration,
        "generated_title": config.get("generated_title", ""),
        "generated_hashtags": config.get("generated_hashtags", ""),
        "script_text": config.get("script_text", ""),
        "tiktok_posted": batch_state.get("tiktok_post_results", {}).get(job_id, {}).get("status") == "posted",
        "tiktok_post_failed": batch_state.get("tiktok_post_results", {}).get(job_id, {}).get("status") == "failed",
    }


@router.post("/api/batch/cancel")
def cancel_batch() -> dict[str, str]:
    """Request cancellation of the running batch."""
    with _batch_state_lock:
        in_progress = batch_state["in_progress"]
        if in_progress:
            batch_state["should_cancel"] = True
    if in_progress:
        return {
            "status": "success",
            "message": "Cancellation requested. Waiting for active workers to terminate.",
        }
    return {"status": "ignored", "message": "No active batch to cancel."}


@router.post("/api/batch/cancel-job/{job_id}")
def cancel_single_job(job_id: int) -> dict[str, str]:
    """Cancel a single queued or waiting job in an active batch.

    Args:
        job_id: The 1-indexed job number to cancel.

    Raises:
        HTTPException: If no batch is running or the job cannot be cancelled.
    """
    with _batch_state_lock:
        if not batch_state["in_progress"]:
            raise HTTPException(
                status_code=400, detail="No active batch in progress."
            )

        status = batch_state["progress_dict"].get(job_id)
        if status not in ("Queued", "Waiting for LLM"):
            raise HTTPException(
                status_code=400,
                detail=f"Job #{job_id} is in status '{status}' "
                f"and cannot be cancelled. Only 'Queued' or "
                f"'Waiting for LLM' jobs can be cancelled.",
            )

        batch_state["progress_dict"][job_id] = "Cancelled"
        config = batch_state.get("job_configs", {}).get(job_id)
        if config is not None:
            if "_cancelled_job_configs" not in batch_state:
                batch_state["_cancelled_job_configs"] = []
            batch_state["_cancelled_job_configs"].append(config)

        return {"status": "success", "message": f"Job #{job_id} cancelled."}


@router.post("/api/batch/retry-cancelled")
def retry_cancelled_batch() -> dict[str, str]:
    """Retry all cancelled jobs from the last batch."""
    if batch_state["in_progress"]:
        raise HTTPException(
            status_code=400, detail="A batch is currently running."
        )

    cancelled_configs = batch_state.get("_cancelled_job_configs", [])
    if not cancelled_configs:
        cancelled_configs = _load_cancelled_configs()
    if not cancelled_configs:
        raise HTTPException(
            status_code=400, detail="No cancelled jobs to retry."
        )

    num_cancelled = len(cancelled_configs)
    new_manager = multiprocessing.Manager()
    new_shared = new_manager.dict()

    with _batch_lock:
        batch_state["in_progress"] = True
        batch_state["num_shorts"] = num_cancelled
        batch_state["progress_dict"].clear()
        batch_state["manager"] = new_manager
        batch_state["shared_progress"] = new_shared
        batch_state["_cancelled_job_configs"] = []
        batch_state["_retry_configs"] = cancelled_configs

    t = threading.Thread(
        target=batch_worker_thread, args=(num_cancelled, None), daemon=True
    )
    t.start()
    return {
        "status": "started",
        "message": f"Retrying {num_cancelled} cancelled jobs.",
    }


@router.post("/api/batch/dismiss-job/{job_id}")
def dismiss_job(job_id: int) -> dict[str, str]:
    """Dismiss a job so it is hidden from the active job list.

    Args:
        job_id: The job number to dismiss.
    """
    with _batch_state_lock:
        if "_dismissed_jobs" not in batch_state:
            batch_state["_dismissed_jobs"] = _load_dismissed_jobs()
        batch_state["_dismissed_jobs"].add(job_id)
        _save_dismissed_jobs(batch_state["_dismissed_jobs"])

    return {"status": "success", "message": f"Job #{job_id} dismissed."}


@router.post("/api/batch/retry-failed")
def retry_failed_batch() -> dict[str, str]:
    """Retry all failed jobs from the last batch."""
    if batch_state["in_progress"]:
        raise HTTPException(
            status_code=400, detail="A batch is currently running."
        )

    failed_configs = batch_state.get("failed_job_configs", [])
    if not failed_configs and os.path.exists(FAILED_CONFIGS_FILE):
        try:
            with open(FAILED_CONFIGS_FILE) as f:
                failed_configs = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load persisted failed configs: %s", e)
    if not failed_configs:
        raise HTTPException(
            status_code=400, detail="No failed jobs to retry."
        )

    num_failed = len(failed_configs)
    new_manager = multiprocessing.Manager()
    new_shared = new_manager.dict()

    with _batch_lock:
        batch_state["in_progress"] = True
        batch_state["num_shorts"] = num_failed
        batch_state["progress_dict"].clear()
        batch_state["manager"] = new_manager
        batch_state["shared_progress"] = new_shared
        batch_state["failed_job_configs"] = []
        batch_state["_retry_configs"] = failed_configs

    t = threading.Thread(
        target=batch_worker_thread, args=(num_failed, None), daemon=True
    )
    t.start()
    return {
        "status": "started",
        "message": f"Retrying {num_failed} failed jobs.",
    }


@router.post("/api/batch/retry-job/{job_id}")
def retry_single_job(job_id: int) -> dict[str, str]:
    """Retry a single failed job by ID.

    Args:
        job_id: The job number to retry.
    """
    if batch_state["in_progress"]:
        raise HTTPException(
            status_code=400, detail="A batch is currently running."
        )

    failed_configs = batch_state.get("failed_job_configs", [])
    if not failed_configs and os.path.exists(FAILED_CONFIGS_FILE):
        try:
            with open(FAILED_CONFIGS_FILE) as f:
                failed_configs = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load persisted failed configs: %s", e)
    target = None
    for cfg in failed_configs:
        if cfg.get("index") == job_id:
            target = cfg
            break

    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"No failed job #{job_id} found to retry.",
        )

    new_manager = multiprocessing.Manager()
    new_shared = new_manager.dict()

    with _batch_lock:
        batch_state["in_progress"] = True
        batch_state["num_shorts"] = 1
        batch_state["progress_dict"].clear()
        batch_state["manager"] = new_manager
        batch_state["shared_progress"] = new_shared
        batch_state["failed_job_configs"] = []
        batch_state["_retry_configs"] = [target]

    t = threading.Thread(
        target=batch_worker_thread, args=(1, None), daemon=True
    )
    t.start()
    return {"status": "started", "message": f"Retrying job #{job_id}."}


@router.get("/api/batch/report")
def get_batch_report() -> dict[str, Any]:
    """Return the completed batch report.

    Returns:
        Summary and per-job results from the last batch.
    """
    with _batch_state_lock:
        results = batch_state.get("batch_results", [])
    if not results:
        raise HTTPException(
            status_code=404, detail="No batch results available."
        )

    total: int = len(results)
    succeeded: int = sum(1 for r in results if r["status"] == "Done")
    cancelled: int = sum(1 for r in results if r["status"] == "Cancelled")
    failed: int = sum(
        1
        for r in results
        if r["status"].startswith("Failed") and r["status"] != "Cancelled"
    )

    return {
        "summary": {
            "total": total,
            "succeeded": succeeded,
            "cancelled": cancelled,
            "failed": failed,
        },
        "jobs": results,
    }
