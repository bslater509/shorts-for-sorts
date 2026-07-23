"""Batch generation REST API routes."""

import json
import multiprocessing
import os
import threading

import psutil
from fastapi import APIRouter, HTTPException

import gui.state as shared_state
from gui.batch_engine import (
    _batch_lock,
    _batch_state_lock,
    _compute_eta,
    _log_memory_warning,
    _PHASE_TRACKING_KEYS,
    batch_state,
    batch_worker_thread,
    DEFAULT_PHASE_WEIGHTS,
)
from gui.config import BATCH_STATS_FILE, FAILED_CONFIGS_FILE, logger
from gui.models import BatchStartRequest

router = APIRouter()


@router.get("/api/prompts")
def get_prompts():
    from gui.config import load_prompt_templates

    return load_prompt_templates()


@router.post("/api/batch/start")
def start_batch(data: BatchStartRequest):
    _log_memory_warning()
    num_shorts = data.num_shorts
    if num_shorts < 1 or num_shorts > 100:
        raise HTTPException(status_code=400, detail="Number of shorts must be between 1 and 100.")

    # Create expensive manager outside lock so we don't block for too long
    new_manager = multiprocessing.Manager()
    new_shared = new_manager.dict()

    with _batch_lock:
        if batch_state["in_progress"]:
            new_manager.shutdown()  # clean up the manager we just created
            raise HTTPException(status_code=400, detail="A batch job is already running.")
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
        ),
        daemon=True,
    )
    t.start()
    return {"status": "started", "message": f"Batch generation of {num_shorts} shorts started."}


@router.get("/api/batch/status")
def get_batch_status():
    from gui.batch import get_progress_percentage

    with _batch_state_lock:
        # Compute stats from completed jobs
        completed_durations = []
        for i in range(1, batch_state["num_shorts"] + 1):
            st = batch_state["progress_dict"].get(f"{i}_start")
            et = batch_state["progress_dict"].get(f"{i}_end")
            status_i = batch_state["progress_dict"].get(i, "Queued")
            if st and et and status_i == "Done":
                completed_durations.append(et - st)
        avg_completion_time = (
            sum(completed_durations) / len(completed_durations) if completed_durations else None
        )

        smoothed_etas = batch_state.get("_smoothed_eta", {})
        phase_weights = batch_state.get("_phase_weights")

        jobs = []
        for i in range(1, batch_state["num_shorts"] + 1):
            status = batch_state["progress_dict"].get(i, "Queued")
            pct = get_progress_percentage(status)

            start_time = batch_state["progress_dict"].get(f"{i}_start")
            end_time = batch_state["progress_dict"].get(f"{i}_end")

            # Gather phase entry timestamps for this job
            job_phase_times = {}
            for suffix in _PHASE_TRACKING_KEYS:
                val = batch_state["progress_dict"].get(f"{i}{suffix}")
                if val:
                    job_phase_times[suffix] = val

            eta_str, eta_seconds, elapsed_str, eta_llm, eta_video = _compute_eta(
                start_time, end_time, pct, status,
                job_phase_times, avg_completion_time, smoothed_etas, i,
                phase_weights=phase_weights,
                avg_llm_duration=batch_state.get("_avg_llm_duration"),
                avg_video_duration=batch_state.get("_avg_video_duration"),
                job_features=batch_state.get("_job_features", {}).get(i),
                per_job_stats=batch_state.get("_per_job_stats"),
            )

            detail = batch_state["job_details"].get(i, {})
            jobs.append(
                {
                    "id": i,
                    "topic": detail.get("topic", "Unknown"),
                    "voice": detail.get("voice", "Unknown"),
                    "layout": detail.get("layout", "Unknown"),
                    "enable_emojis": detail.get("enable_emojis", False),
                    "status": status,
                    "progress": pct if pct is not None else 0,
                    "failed": pct is None,
                    "elapsed": elapsed_str,
                    "eta": eta_str,
                    "eta_seconds": eta_seconds,
                    "eta_llm": round(eta_llm, 1) if eta_llm > 0 else 0,
                    "eta_video": round(eta_video, 1) if eta_video > 0 else 0,
                }
            )

        in_progress = batch_state["in_progress"]
        num_shorts = batch_state["num_shorts"]
        max_workers = batch_state.get("max_workers", 1)
        llm_max_workers = batch_state.get("llm_max_workers", 5)

        # Pipeline-aware global ETA
        # LLM runs in parallel (llm_max_workers), video runs sequentially (max_workers).
        # Total remaining ≈ sum(LLM remaining) / llm_max_workers + sum(video remaining) / max_workers
        avg_llm_dur = batch_state.get("_avg_llm_duration", 30) or 30
        avg_video_dur = batch_state.get("_avg_video_duration", 60) or 60
        total_llm = 0.0
        total_video = 0.0
        for j in jobs:
            s = j["status"]
            if s == "Done" or s.startswith("Failed"):
                continue
            if s != "Queued" and j.get("eta_llm") is not None:
                total_llm += j["eta_llm"]
                total_video += j["eta_video"]
            else:
                total_llm += avg_llm_dur
                total_video += avg_video_dur
        global_eta_seconds = (total_llm / max(1, llm_max_workers)) + (total_video / max(1, max_workers))

    return {
        "in_progress": in_progress,
        "num_shorts": num_shorts,
        "jobs": jobs,
        "max_workers": max_workers,
        "global_eta_seconds": round(global_eta_seconds, 1),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "progress_segments": [
            {"name": "LLM", "start": 0, "end": 20},
            {"name": "Voice", "start": 20, "end": 45},
            {"name": "Transcribe", "start": 45, "end": 55},
            {"name": "Render", "start": 55, "end": 100},
        ],
    }


@router.get("/api/batch/job/{job_id}")
def get_batch_job_detail(job_id: int):
    from gui.batch import get_progress_percentage

    with _batch_state_lock:
        # Check if the job exists
        if job_id < 1 or job_id > batch_state["num_shorts"]:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get progress info
        status = batch_state["progress_dict"].get(job_id, "Unknown")
        pct = get_progress_percentage(status)

        start_time = batch_state["progress_dict"].get(f"{job_id}_start")
        end_time = batch_state["progress_dict"].get(f"{job_id}_end")

        # Compute average completion time from finished jobs
        completed_durations = []
        for i in range(1, batch_state["num_shorts"] + 1):
            st = batch_state["progress_dict"].get(f"{i}_start")
            et = batch_state["progress_dict"].get(f"{i}_end")
            status_i = batch_state["progress_dict"].get(i, "Queued")
            if st and et and status_i == "Done":
                completed_durations.append(et - st)
        avg_completion_time = (
            sum(completed_durations) / len(completed_durations) if completed_durations else None
        )

        # Gather phase entry timestamps for this job
        job_phase_times = {}
        for suffix in _PHASE_TRACKING_KEYS:
            val = batch_state["progress_dict"].get(f"{job_id}{suffix}")
            if val:
                job_phase_times[suffix] = val

        smoothed_etas = batch_state.get("_smoothed_eta", {})
        phase_weights = batch_state.get("_phase_weights")
        eta_str, eta_seconds, elapsed_str, eta_llm, eta_video = _compute_eta(
            start_time, end_time, pct, status,
            job_phase_times, avg_completion_time, smoothed_etas, job_id,
            phase_weights=phase_weights,
            avg_llm_duration=batch_state.get("_avg_llm_duration"),
            avg_video_duration=batch_state.get("_avg_video_duration"),
            job_features=batch_state.get("_job_features", {}).get(job_id),
            per_job_stats=batch_state.get("_per_job_stats"),
        )

        # Get detail and config
        detail = batch_state["job_details"].get(job_id, {})
        config = batch_state.get("job_configs", {}).get(job_id, {})

    # Build response with ALL job settings
    return {
        "id": job_id,
        "topic": detail.get("topic", ""),
        "voice_name": detail.get("voice", "Unknown"),
        "layout": detail.get("layout", "Unknown"),
        "enable_emojis": detail.get("enable_emojis", False),
        "status": status,
        "progress": pct if pct is not None else 0,
        "failed": pct is None,
        "elapsed": elapsed_str,
        "eta": eta_str,
        "eta_seconds": eta_seconds,
        # Full config fields (all optional - use empty string/0/False defaults)
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
        "output_filename": config.get("output_filename", ""),
        "generated_title": config.get("generated_title", ""),
        "generated_hashtags": config.get("generated_hashtags", ""),
        "script_text": config.get("script_text", ""),
    }


@router.post("/api/batch/cancel")
def cancel_batch():
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


@router.post("/api/batch/retry-failed")
def retry_failed_batch():
    if batch_state["in_progress"]:
        raise HTTPException(status_code=400, detail="A batch is currently running.")

    failed_configs = batch_state.get("failed_job_configs", [])
    if not failed_configs:
        # Fall back to persisted configs from disk
        if os.path.exists(FAILED_CONFIGS_FILE):
            try:
                with open(FAILED_CONFIGS_FILE) as f:
                    failed_configs = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load persisted failed configs: %s", e)
    if not failed_configs:
        raise HTTPException(status_code=400, detail="No failed jobs to retry.")

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

    t = threading.Thread(target=batch_worker_thread, args=(num_failed, None), daemon=True)
    t.start()
    return {"status": "started", "message": f"Retrying {num_failed} failed jobs."}


@router.post("/api/batch/retry-job/{job_id}")
def retry_single_job(job_id: int):
    if batch_state["in_progress"]:
        raise HTTPException(status_code=400, detail="A batch is currently running.")

    # Find the failed job config by index
    failed_configs = batch_state.get("failed_job_configs", [])
    if not failed_configs:
        # Fall back to persisted configs from disk
        if os.path.exists(FAILED_CONFIGS_FILE):
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
        raise HTTPException(status_code=404, detail=f"No failed job #{job_id} found to retry.")

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

    t = threading.Thread(target=batch_worker_thread, args=(1, None), daemon=True)
    t.start()
    return {"status": "started", "message": f"Retrying job #{job_id}."}


@router.get("/api/batch/report")
def get_batch_report():
    with _batch_state_lock:
        results = batch_state.get("batch_results", [])
    if not results:
        raise HTTPException(status_code=404, detail="No batch results available.")

    total = len(results)
    succeeded = sum(1 for r in results if r["status"] == "Done")
    failed = sum(1 for r in results if r["status"].startswith("Failed"))

    return {
        "summary": {
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
        },
        "jobs": results,
    }
