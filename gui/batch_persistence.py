"""Phase-weight persistence and batch result collection.

Contains ``_load_phase_weights`` / ``_save_phase_weights`` (learned phase
timing ratios, duration averages, per-job stats, and processing rates) plus
``_collect_and_persist_results`` / ``_persist_phase_data`` which finalise a
batch run and write results to disk.

``batch_state`` and ``_sync_progress`` are imported lazily inside functions
to avoid a circular import with ``gui.batch_engine``.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

from gui.batch_eta import _compute_phase_rates
from gui.config import (
    BATCH_STATS_FILE,
    CANCELLED_CONFIGS_FILE,
    FAILED_CONFIGS_FILE,
    logger,
)
from gui.ws_manager import broadcast_batch_status, notify_clients

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Overall phase ratios (including LLM) stored in batch_stats.json
DEFAULT_PHASE_WEIGHTS: dict[str, float] = {
    "LLM": 0.05,
    "Voice": 0.30,
    "Transcribe": 0.10,
    "Render": 0.55,
}

# Minimum samples before blending learned phase weights
PHASE_WEIGHT_MIN_SAMPLES: int = 3

# Blend factor for phase weight merging
PHASE_WEIGHT_BLEND_RATE: float = 0.8
PHASE_WEIGHT_MAX_BLEND: float = 0.8

# Per-job stats cap
_PER_JOB_STATS_MAX: int = 500


# ---------------------------------------------------------------------------
# Phase weight persistence
# ---------------------------------------------------------------------------


def _load_phase_weights() -> dict[str, Any]:
    """Load learned phase weights, absolute duration averages, per-job stats, and rates.

    Returns:
        Dict with keys:
            - ``phase_ratios``: blended phase weight dict.
            - ``avg_llm_duration``: float seconds or ``None``.
            - ``avg_video_duration``: float seconds or ``None``.
            - ``per_job_stats``: list of per-job feature+duration dicts.
            - ``phase_rates``: dict of median processing rates (words/sec).
    """
    result: dict[str, Any] = {
        "phase_ratios": dict(DEFAULT_PHASE_WEIGHTS),
        "avg_llm_duration": None,
        "avg_video_duration": None,
        "per_job_stats": [],
        "phase_rates": {},
    }
    try:
        if os.path.exists(BATCH_STATS_FILE):
            with open(BATCH_STATS_FILE) as f:
                data: dict[str, Any] = json.load(f)
            stored: dict[str, float] = data.get("phase_ratios", {})
            sample_count: int = data.get("sample_count", 0)
            if sample_count >= PHASE_WEIGHT_MIN_SAMPLES:
                blend: float = min(
                    PHASE_WEIGHT_MAX_BLEND,
                    sample_count / (sample_count + 5),
                )
                for phase in result["phase_ratios"]:
                    if phase in stored:
                        result["phase_ratios"][phase] = (
                            blend * stored[phase]
                            + (1 - blend) * result["phase_ratios"][phase]
                        )
            result["avg_llm_duration"] = data.get("avg_llm_duration")
            result["avg_video_duration"] = data.get("avg_video_duration")
            result["per_job_stats"] = data.get("per_job_stats", [])
            result["phase_rates"] = data.get("phase_rates", {})
    except Exception as e:
        logger.warning("Failed to load batch stats: %s", e)
    return result


def _save_phase_weights(
    phase_ratios: dict[str, float],
    sample_count: int,
    avg_llm_duration: float | None = None,
    avg_video_duration: float | None = None,
    per_job_stats: list[dict[str, Any]] | None = None,
    phase_rates: dict[str, float] | None = None,
) -> None:
    """Persist learned phase weights, per-job stats, and processing rates to disk.

    Args:
        phase_ratios: Phase weight dictionary.
        sample_count: Number of samples used for the weights.
        avg_llm_duration: Average LLM phase duration.
        avg_video_duration: Average video pipeline duration.
        per_job_stats: Optional list of per-job feature+duration records.
        phase_rates: Optional dict of median processing rates (words/sec).
    """
    try:
        os.makedirs(os.path.dirname(BATCH_STATS_FILE), exist_ok=True)
        payload: dict[str, Any] = {
            "phase_ratios": phase_ratios,
            "sample_count": sample_count,
            "avg_llm_duration": avg_llm_duration,
            "avg_video_duration": avg_video_duration,
            "phase_rates": phase_rates or {},
        }
        if per_job_stats is not None:
            if len(per_job_stats) > _PER_JOB_STATS_MAX:
                per_job_stats = per_job_stats[-_PER_JOB_STATS_MAX:]
            payload["per_job_stats"] = per_job_stats
        with open(BATCH_STATS_FILE, "w") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        logger.warning("Failed to save batch stats: %s", e)


# ---------------------------------------------------------------------------
# Result collection and persistence
# ---------------------------------------------------------------------------


def _collect_and_persist_results(
    job_configs: dict[int, dict[str, Any]], num_shorts: int
) -> None:
    """Populate ``batch_results``, log a summary, and persist phase weights/stats.

    Args:
        job_configs: Job configuration dicts.
        num_shorts: Number of shorts in the batch.
    """
    from gui.batch_engine import _sync_progress, batch_state
    from gui.progress_utils import log_memory_usage

    _sync_progress(batch_state, num_shorts)
    log_memory_usage("All jobs complete (before cleanup)")

    batch_state["batch_results"] = []
    for i in range(1, num_shorts + 1):
        detail = batch_state["job_details"].get(i, {})
        status = batch_state["shared_progress"].get(i, "Unknown")
        config = job_configs.get(i, {})
        start = batch_state["shared_progress"].get(f"{i}_start")
        end = batch_state["shared_progress"].get(f"{i}_end")
        error = ""
        if str(status) == "Cancelled":
            error = "Cancelled by user"
        elif str(status).startswith("Failed:"):
            error = (
                str(status)[len("Failed: "):] if len(status) > 7 else status
            )
        batch_state["batch_results"].append(
            {
                "id": i,
                "topic": detail.get("topic", ""),
                "voice": detail.get("voice", ""),
                "layout": detail.get("layout", ""),
                "status": status,
                "error": error,
                "title": config.get("generated_title", ""),
                "hashtags": config.get("generated_hashtags", ""),
                "output_filename": config.get("output_filename", ""),
                "start_time": start,
                "end_time": end,
                "script_text": str(config.get("script_text", ""))[:200],
            }
        )

    done = sum(
        1
        for i in range(1, num_shorts + 1)
        if batch_state["shared_progress"].get(i) == "Done"
    )
    failed = sum(
        1
        for i in range(1, num_shorts + 1)
        if str(batch_state["shared_progress"].get(i, "")).startswith("Failed")
    )
    logger.info(
        "[Batch Thread] Batch complete: %d/%d done, %d failed",
        done,
        num_shorts,
        failed,
    )
    if failed == 0:
        notify_clients(
            "batch",
            "success",
            f"Batch completed successfully ({done}/{num_shorts})",
            "success",
        )
    elif done == 0:
        notify_clients(
            "batch",
            "error",
            f"Batch failed completely ({failed}/{num_shorts} failed)",
            "error",
        )
    else:
        notify_clients(
            "batch",
            "success",
            f"Batch partially completed ({done} done, {failed} failed)",
            "info",
        )

    # Persist phase timing ratios and duration averages
    _persist_phase_data(job_configs, num_shorts)

    # Broadcast final batch status snapshot
    from gui.routers.batch import build_batch_status
    broadcast_batch_status(build_batch_status())


def _persist_phase_data(
    job_configs: dict[int, dict[str, Any]], num_shorts: int
) -> None:
    """Collect phase timing data and persist to disk.

    Args:
        job_configs: Job configuration dicts.
        num_shorts: Number of shorts in the batch.
    """
    from gui.batch_engine import batch_state

    phase_durations: dict[str, list[float]] = {
        "LLM": [],
        "Voice": [],
        "Transcribe": [],
        "Render": [],
    }
    llm_durations: list[float] = []
    video_durations: list[float] = []

    for i in range(1, num_shorts + 1):
        st = batch_state["progress_dict"].get(f"{i}_start")
        et = batch_state["progress_dict"].get(f"{i}_end")
        vs = batch_state["progress_dict"].get(f"{i}_phase_voice_start")
        ts = batch_state["progress_dict"].get(f"{i}_phase_transcribe_start")
        rs = batch_state["progress_dict"].get(f"{i}_phase_render_start")
        llm_end = batch_state["progress_dict"].get(f"{i}_phase_llm_end")
        if (
            st
            and et
            and batch_state["progress_dict"].get(i) == "Done"
            and vs
            and ts
            and rs
        ):
            total = et - st
            if total > 0:
                phase_durations["LLM"].append((vs - st) / total)
                phase_durations["Voice"].append((ts - vs) / total)
                phase_durations["Transcribe"].append((rs - ts) / total)
                phase_durations["Render"].append((et - rs) / total)
            if llm_end:
                llm_durations.append(llm_end - st)
            video_durations.append(et - vs)

    batch_ratios: dict[str, float] = {}
    job_count: int = 0
    for phase in DEFAULT_PHASE_WEIGHTS:
        durs = phase_durations[phase]
        if durs:
            job_count = len(durs)
            batch_ratios[phase] = sum(durs) / len(durs)

    avg_llm_duration: float | None = (
        sum(llm_durations) / len(llm_durations) if llm_durations else None
    )
    avg_video_duration: float | None = (
        sum(video_durations) / len(video_durations) if video_durations else None
    )

    stored_data = _load_phase_weights()
    stored = stored_data.get("phase_ratios", {})
    merged = stored if stored else dict(DEFAULT_PHASE_WEIGHTS)

    job_features = batch_state.get("_job_features", {})
    new_job_stats: list[dict[str, Any]] = []
    for i in range(1, num_shorts + 1):
        features = job_features.get(i, {})
        if not features or not features.get("word_count"):
            continue
        st = batch_state["progress_dict"].get(f"{i}_start")
        vs = batch_state["progress_dict"].get(f"{i}_phase_voice_start")
        ts = batch_state["progress_dict"].get(f"{i}_phase_transcribe_start")
        rs = batch_state["progress_dict"].get(f"{i}_phase_render_start")
        et = batch_state["progress_dict"].get(f"{i}_end")
        llm_end = batch_state["progress_dict"].get(f"{i}_phase_llm_end")
        is_done = batch_state["progress_dict"].get(i) == "Done"

        record = dict(features)
        record["llm_duration"] = (llm_end - st) if (llm_end and st) else 0
        if is_done and st and et and vs and ts and rs:
            record["voice_duration"] = ts - vs
            record["transcribe_duration"] = rs - ts
            record["render_duration"] = et - rs
            record["video_duration"] = et - vs
            record["status"] = "success"
        else:
            record["voice_duration"] = (ts - vs) if (ts and vs) else 0
            record["transcribe_duration"] = (rs - ts) if (rs and ts) else 0
            record["render_duration"] = (et - rs) if (et and rs) else 0
            record["video_duration"] = (et - vs) if (et and vs) else 0
            record["status"] = "failed"
        record["started_at"] = (
            datetime.datetime.fromtimestamp(st, tz=datetime.timezone.utc).isoformat()
            if st
            else None
        )
        new_job_stats.append(record)

    per_job_stats = list(batch_state.get("_per_job_stats", []))
    per_job_stats.extend(new_job_stats)
    sample_count: int = len(per_job_stats)

    if batch_ratios and job_count >= 1:
        prev_avg_llm = stored_data.get("avg_llm_duration")
        prev_avg_video = stored_data.get("avg_video_duration")
        try:
            if os.path.exists(BATCH_STATS_FILE):
                with open(BATCH_STATS_FILE) as f:
                    raw = json.load(f)
                if "avg_llm_duration" in raw:
                    prev_avg_llm = raw["avg_llm_duration"]
                if "avg_video_duration" in raw:
                    prev_avg_video = raw["avg_video_duration"]
        except Exception:
            pass

        blend = min(0.5, job_count / (job_count + 3))
        merged = dict(stored) if stored else dict(DEFAULT_PHASE_WEIGHTS)
        for phase in merged:
            if phase in batch_ratios:
                merged[phase] = (
                    (1 - blend) * stored.get(phase, DEFAULT_PHASE_WEIGHTS[phase])
                    + blend * batch_ratios[phase]
                )

        merged_avg_llm: float | None = None
        if avg_llm_duration is not None:
            if prev_avg_llm is not None:
                merged_avg_llm = (1 - blend) * prev_avg_llm + blend * avg_llm_duration
            else:
                merged_avg_llm = avg_llm_duration

        merged_avg_video: float | None = None
        if avg_video_duration is not None:
            if prev_avg_video is not None:
                merged_avg_video = (
                    (1 - blend) * prev_avg_video + blend * avg_video_duration
                )
            else:
                merged_avg_video = avg_video_duration

        phase_rates: dict[str, float] = _compute_phase_rates(per_job_stats)
        _save_phase_weights(
            merged,
            sample_count,
            merged_avg_llm,
            merged_avg_video,
            per_job_stats=per_job_stats,
            phase_rates=phase_rates,
        )
    elif new_job_stats:
        stored = _load_phase_weights()
        phase_rates = _compute_phase_rates(per_job_stats)
        _save_phase_weights(
            stored.get("phase_ratios", dict(DEFAULT_PHASE_WEIGHTS)),
            sample_count,
            avg_llm_duration=stored.get("avg_llm_duration"),
            avg_video_duration=stored.get("avg_video_duration"),
            per_job_stats=per_job_stats,
            phase_rates=phase_rates,
        )

    # Persist failed job configs
    try:
        failed = batch_state.get("failed_job_configs", [])
        if failed:
            os.makedirs(os.path.dirname(FAILED_CONFIGS_FILE), exist_ok=True)
            with open(FAILED_CONFIGS_FILE, "w") as f:
                json.dump(failed, f, default=str, indent=2)
            logger.info(
                "[Batch Thread] Persisted %d failed configs to %s",
                len(failed),
                FAILED_CONFIGS_FILE,
            )
    except Exception as e:
        logger.warning("[Batch Thread] Failed to persist failed configs: %s", e)

    # Persist cancelled job configs
    try:
        cancelled = batch_state.get("_cancelled_job_configs", [])
        if cancelled:
            os.makedirs(os.path.dirname(CANCELLED_CONFIGS_FILE), exist_ok=True)
            with open(CANCELLED_CONFIGS_FILE, "w") as f:
                json.dump(cancelled, f, default=str, indent=2)
            logger.info(
                "[Batch Thread] Persisted %d cancelled configs to %s",
                len(cancelled),
                CANCELLED_CONFIGS_FILE,
            )
    except Exception as e:
        logger.warning("[Batch Thread] Failed to persist cancelled configs: %s", e)
