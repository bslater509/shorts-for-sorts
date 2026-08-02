"""Batch generation engine — orchestrates multi-job batches with LLM and video workers.

Contains the batch state dictionary, phase tracking constants, ETA computation
helpers with similarity-weighted duration prediction, phase weight persistence,
and the main ``batch_worker_thread`` orchestrator.
"""

from __future__ import annotations

import datetime
import json
import os
import random
import re
import statistics
import threading
import time
from typing import Any

import gui.state as shared_state
from gui.assets_utils import list_music_files
from gui.config import (
    BASE_DIR,
    BATCH_STATS_FILE,
    CANCELLED_CONFIGS_FILE,
    FAILED_CONFIGS_FILE,
    MUSIC_DIR,
    logger,
)
from gui.ws_manager import broadcast_batch_status, notify_clients

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LLM_MODEL: str = "gpt-4o-mini"
"""Default model for LLM script generation in batch mode."""

# Video pipeline phases (sequential, after LLM): (name, start_pct, end_pct)
VIDEO_PHASES: list[tuple[str, int, int]] = [
    ("Voice", 20, 45),
    ("Transcribe", 45, 55),
    ("Render", 55, 100),
]

DEFAULT_VIDEO_WEIGHTS: dict[str, float] = {
    "Voice": 0.35,
    "Transcribe": 0.10,
    "Render": 0.55,
}
"""Default time-weight distribution for the video pipeline phases."""

# Overall phase ratios (including LLM) stored in batch_stats.json
DEFAULT_PHASE_WEIGHTS: dict[str, float] = {
    "LLM": 0.05,
    "Voice": 0.30,
    "Transcribe": 0.10,
    "Render": 0.55,
}

# Phase tracking keys — set by batch_worker_thread (llm_end) or ProgressConsole (rest)
_PHASE_TRACKING_KEYS: list[str] = [
    "_phase_llm_end",
    "_phase_voice_start",
    "_phase_transcribe_start",
    "_phase_render_start",
]

# ETA smoothing factor (0.0 = no smoothing, 1.0 = instant)
ETA_SMOOTHING_ALPHA: float = 0.3

# Number of candidates used for similarity-weighted ETA prediction
SIMILARITY_CANDIDATES: int = 10

# Blend factor threshold for few-candidate blending
SIMILARITY_MIN_CANDIDATES: int = 3

# Same-voice weight multiplier for similarity scoring
SAME_VOICE_BONUS: float = 1.5

# Minimum samples before blending learned phase weights
PHASE_WEIGHT_MIN_SAMPLES: int = 3

# Blend factor for phase weight merging
PHASE_WEIGHT_BLEND_RATE: float = 0.8
PHASE_WEIGHT_MAX_BLEND: float = 0.8

# Per-job stats cap
_PER_JOB_STATS_MAX: int = 500

# Poll interval for the pipeline loop
PIPELINE_POLL_INTERVAL: float = 0.1

# Blend factor for rate-based prediction vs similarity-based prediction
RATE_BLEND_ALPHA: float = 0.7

# Default duration estimates for ETA prediction
DEFAULT_LLM_DURATION: float = 30.0
DEFAULT_VIDEO_DURATION: float = 60.0

# Low-memory warning threshold (MB)
LOW_MEMORY_THRESHOLD_MB: int = 1024

# Pipeline progress: LLM-end threshold for video phase
LLM_VIDEO_THRESHOLD: float = 20.0

# ---------------------------------------------------------------------------
# Batch state
# ---------------------------------------------------------------------------

_batch_lock: threading.Lock = threading.Lock()
"""Guards ``batch_state["in_progress"]`` TOCTOU."""

_batch_state_lock: threading.RLock = threading.RLock()
"""Guards all other batch_state read/write operations."""

batch_state: dict[str, Any] = {
    "in_progress": False,
    "num_shorts": 0,
    "progress_dict": {},
    "job_details": {},
    "should_cancel": False,
    "futures": [],
    "executor": None,
    "manager": None,
    "shared_progress": None,
    "batch_results": [],
    "failed_job_configs": [],
    "_cancelled_job_configs": [],
    "_dismissed_jobs": set(),
    "max_workers": 1,
    "llm_max_workers": 5,
    "_smoothed_eta": {},
    "_phase_weights": None,
    "_phase_rates": {},
}
"""Thread-safe batch state shared across modules."""


# ---------------------------------------------------------------------------
# Worker count resolution
# ---------------------------------------------------------------------------


def _resolve_worker_count(key: str, default: int, min_val: int = 1) -> int:
    """Resolve a worker count from settings with a fallback default.

    Args:
        key: Settings key for the worker count.
        default: Default value if the setting is missing or invalid.
        min_val: Minimum acceptable value.

    Returns:
        The resolved integer worker count.
    """
    val: Any = shared_state.settings.get(key)
    if val:
        try:
            return max(min_val, int(val))
        except (ValueError, TypeError):
            return default
    return default


# ---------------------------------------------------------------------------
# Progress / ETA helpers
# ---------------------------------------------------------------------------


def compute_video_progress(
    pct: float | None, weights: dict[str, float] | None = None
) -> float:
    """Convert a raw progress percentage to a time-weighted fraction of the video pipeline.

    Covers Voice/Transcribe/Render phases only (LLM runs in parallel with
    different timing characteristics).

    Args:
        pct: Raw progress percentage (0–100, or ``None``).
        weights: Optional time-weight dict per phase.

    Returns:
        Fraction ``[0.0, 1.0]`` representing video pipeline progress.
    """
    if not pct or pct <= LLM_VIDEO_THRESHOLD:
        return 0.0
    w: dict[str, float] = weights if weights else DEFAULT_VIDEO_WEIGHTS
    completed: float = 0.0
    for name, p_start, p_end in VIDEO_PHASES:
        span: int = p_end - p_start
        if pct >= p_end:
            completed += w.get(name, 0.30)
        elif pct > p_start:
            phase_pct: float = (pct - p_start) / span
            completed += w.get(name, 0.30) * phase_pct
    return min(completed, 1.0)


def _compute_eta(
    start_time: float | None,
    end_time: float | None,
    pct: int | None,
    status: str,
    job_phase_times: dict[str, float],
    avg_completion_time: float | None,
    smoothed_etas: dict[int, float] | None,
    job_id: int | None,
    phase_weights: dict[str, float] | None = None,
    avg_llm_duration: float | None = None,
    avg_video_duration: float | None = None,
    job_features: dict[str, Any] | None = None,
    per_job_stats: list[dict[str, Any]] | None = None,
) -> tuple[str, float, str, float, float]:
    """Compute ETA with phase weighting, blending, and smoothing.

    When ``job_features`` and ``per_job_stats`` are available, uses
    similarity-weighted prediction for job-specific duration estimates.

    Returns:
        Tuple of ``(eta_str, eta_seconds, elapsed_str, eta_llm, eta_video)``.
    """
    from gui.progress_utils import format_elapsed

    if not start_time:
        return "--", 0.0, "--", 0.0, 0.0

    now: float = time.time()
    duration: float = (end_time if end_time else now) - start_time
    elapsed_str: str = format_elapsed(duration)

    if status == "Done":
        return "0s", 0.0, elapsed_str + " (Done)", 0.0, 0.0

    if not (pct and pct > 0):
        return "--", 0.0, elapsed_str, 0.0, 0.0

    # Determine effective duration estimates
    effective_llm_dur: float | None = avg_llm_duration
    effective_video_dur: float | None = avg_video_duration
    if job_features and job_features.get("word_count") and per_job_stats:
        pred_llm, pred_video = _predict_phase_duration(job_features, per_job_stats)
        if pred_llm is not None:
            effective_llm_dur = pred_llm
        if pred_video is not None:
            effective_video_dur = pred_video

    # Pipeline-aware breakdown
    llm_done: bool = bool(
        job_phase_times and job_phase_times.get("_phase_llm_end") is not None
    )

    eta_llm: float
    eta_video: float

    if llm_done:
        llm_end: float = job_phase_times["_phase_llm_end"]
        video_elapsed: float = (end_time if end_time else now) - llm_end
        video_progress: float = compute_video_progress(
            pct, weights=phase_weights
        )
        if effective_video_dur is not None and video_progress < 0.3:
            eta_video = effective_video_dur * max(0, 1.0 - video_progress)
        elif video_progress > 0:
            eta_video = video_elapsed / video_progress * (1.0 - video_progress)
        else:
            eta_video = effective_video_dur if effective_video_dur else DEFAULT_VIDEO_DURATION
        eta_llm = 0.0
    else:
        effective_progress = compute_video_progress(pct, weights=phase_weights)
        if effective_progress > 0:
            eta_video = (
                duration / effective_progress * (1.0 - effective_progress)
            )
        else:
            eta_video = (
                effective_video_dur if effective_video_dur else DEFAULT_VIDEO_DURATION
            )
        llm_fraction: float = (
            min(1.0, (pct or 0) / LLM_VIDEO_THRESHOLD) if pct else 0
        )
        if llm_fraction > 0:
            eta_llm = duration / llm_fraction * (1.0 - llm_fraction)
        else:
            eta_llm = effective_llm_dur if effective_llm_dur else DEFAULT_LLM_DURATION

    # Total job-remaining for per-job display
    eta_seconds: float = eta_llm + eta_video

    # Apply exponential smoothing
    if smoothed_etas is not None and job_id is not None:
        prev: float = smoothed_etas.get(job_id, eta_seconds)
        smoothed: float = (
            ETA_SMOOTHING_ALPHA * eta_seconds + (1.0 - ETA_SMOOTHING_ALPHA) * prev
        )
        smoothed_etas[job_id] = smoothed
        eta_seconds = smoothed
        total_raw: float = eta_llm + eta_video
        if total_raw > 0:
            ratio: float = eta_seconds / total_raw
            eta_llm *= ratio
            eta_video *= ratio

    return format_elapsed(eta_seconds), eta_seconds, elapsed_str, eta_llm, eta_video


def _sync_progress(batch_state: dict[str, Any], num_shorts: int) -> None:
    """Copy ``shared_progress`` (Manager dict) to ``progress_dict`` for API access.

    Args:
        batch_state: The batch state dictionary (mutated in-place).
        num_shorts: Number of shorts in the current batch.
    """
    with _batch_state_lock:
        for i in range(1, num_shorts + 1):
            batch_state["progress_dict"][i] = batch_state["shared_progress"].get(
                i, "Queued"
            )
            for suffix in ["_start", "_end"] + _PHASE_TRACKING_KEYS:
                sk: str = f"{i}{suffix}"
                if sk in batch_state["shared_progress"]:
                    batch_state["progress_dict"][sk] = batch_state["shared_progress"][sk]


# ---------------------------------------------------------------------------
# Feature extraction / duration prediction
# ---------------------------------------------------------------------------


def _extract_job_features(
    script_text: str | None, job_config: dict[str, Any]
) -> dict[str, Any]:
    """Extract job characteristics from script text and config for ETA prediction.

    Args:
        script_text: The generated script text (may be ``None``).
        job_config: Job configuration dictionary.

    Returns:
        Feature dict with ``word_count``, ``sentence_count``, ``chunk_count``,
        ``emoji_count``, and layout/speed settings.  Empty dict if script is
        unavailable.
    """
    if not script_text:
        return {}

    words: list[str] = script_text.split()
    word_count: int = len(words)
    sentence_count: int = max(1, len(re.findall(r"[.!?]+", script_text)))
    chunks: list[str] = [
        c.strip() for c in re.split(r"\n\s*\n", script_text) if c.strip()
    ]
    chunk_count: int = len(chunks)

    # Count emoji characters
    try:
        import unicodedata

        emoji_count: int = sum(
            1 for c in script_text if unicodedata.category(c) == "So"
        )
    except Exception:
        emoji_count = 0

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "chunk_count": chunk_count,
        "emoji_count": emoji_count,
        "enable_emojis": bool(job_config.get("enable_emojis", False)),
        "voice_id": str(job_config.get("voice_id", "")),
        "model": str(job_config.get("model", "unknown")),
        "layout": "Split-Screen"
        if job_config.get("bg_video_bottom_path")
        else "Full Screen",
        "voice_speed": float(job_config.get("voice_speed", 1.0)),
        "words_per_screen": str(job_config.get("words_per_screen", "3")),
        "sub_animation_style": str(
            job_config.get("sub_animation_style", "fade_in_slide")
        ),
    }


def _compute_phase_rates(
    per_job_stats: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute median processing rates (words/sec) per phase from historical stats.

    Uses median to avoid outlier influence.  Entries without ``word_count``
    or a particular phase duration are silently skipped.

    Args:
        per_job_stats: List of historical per-job stat dicts.

    Returns:
        Dict with keys ``llm_rate``, ``voice_rate``, ``transcribe_rate``,
        ``render_rate`` (only for phases with at least one valid entry),
        or empty dict if no valid data exists.
    """
    rate_lists: dict[str, list[float]] = {
        "llm": [],
        "voice": [],
        "transcribe": [],
        "render": [],
    }
    for s in per_job_stats:
        wc: float = s.get("word_count", 0)
        if not wc:
            continue
        llm_dur = s.get("llm_duration")
        if llm_dur and llm_dur > 0:
            rate_lists["llm"].append(wc / llm_dur)
        voice_dur = s.get("voice_duration")
        if voice_dur and voice_dur > 0:
            rate_lists["voice"].append(wc / voice_dur)
        transcribe_dur = s.get("transcribe_duration")
        if transcribe_dur and transcribe_dur > 0:
            rate_lists["transcribe"].append(wc / transcribe_dur)
        render_dur = s.get("render_duration")
        if render_dur and render_dur > 0:
            rate_lists["render"].append(wc / render_dur)

    result: dict[str, float] = {}
    for phase, values in rate_lists.items():
        if values:
            result[f"{phase}_rate"] = statistics.median(values)
    return result


def _predict_by_rates(
    features: dict[str, Any],
    rates: dict[str, float],
) -> tuple[float | None, float | None]:
    """Predict LLM and video durations from word count and median processing rates.

    Args:
        features: Feature dict from :func:`_extract_job_features`.
        rates: Rate dict from :func:`_compute_phase_rates`.

    Returns:
        Tuple of ``(predicted_llm_duration, predicted_video_duration)``
        in seconds, or ``(None, None)`` if rates are insufficient.
    """
    word_count = features.get("word_count", 0)
    if not word_count or not rates:
        return None, None

    llm_rate = rates.get("llm_rate")
    voice_rate = rates.get("voice_rate")
    transcribe_rate = rates.get("transcribe_rate")
    render_rate = rates.get("render_rate")

    pred_llm: float | None = (
        word_count / llm_rate if (llm_rate and llm_rate > 0) else None
    )
    pred_voice: float | None = (
        word_count / voice_rate if (voice_rate and voice_rate > 0) else None
    )
    pred_transcribe: float | None = (
        word_count / transcribe_rate if (transcribe_rate and transcribe_rate > 0) else None
    )
    pred_render: float | None = (
        word_count / render_rate if (render_rate and render_rate > 0) else None
    )

    pred_video: float | None = None
    if (
        pred_voice is not None
        and pred_transcribe is not None
        and pred_render is not None
    ):
        pred_video = pred_voice + pred_transcribe + pred_render

    return pred_llm, pred_video


def _predict_phase_duration(
    features: dict[str, Any],
    per_job_stats: list[dict[str, Any]],
) -> tuple[float | None, float | None]:
    """Predict LLM and video duration using similarity-weighted averages and rates.

    Uses normalised Euclidean distance on ``word_count``, ``chunk_count``,
    and ``sentence_count`` to find similar historical jobs.
    Blends with global averages when few matching jobs exist, and blends
    with rate-based prediction from :func:`_predict_by_rates`.

    Args:
        features: Feature dict from :func:`_extract_job_features`.
        per_job_stats: List of historical per-job stat dicts.

    Returns:
        Tuple of ``(predicted_llm_duration, predicted_video_duration)``
        in seconds, or ``(None, None)`` if insufficient data.
    """
    word_count: int = features.get("word_count", 0)
    chunk_count: int = features.get("chunk_count", 0)
    sentence_count: int = features.get("sentence_count", 0)
    if not word_count or not per_job_stats:
        return None, None

    wc_values: list[float] = [
        s.get("word_count", 0) for s in per_job_stats if s.get("word_count")
    ]
    cc_values: list[float] = [
        s.get("chunk_count", 0) for s in per_job_stats if s.get("chunk_count")
    ]
    # Extract sentence_count from historical entries that have it
    sc_values: list[float] = [
        float(s["sentence_count"]) for s in per_job_stats
        if isinstance(s.get("sentence_count"), (int, float)) and s["sentence_count"]
    ]
    has_sc: bool = bool(sc_values)

    if not wc_values:
        return None, None

    wc_mean: float = sum(wc_values) / len(wc_values)
    wc_var: float = sum((v - wc_mean) ** 2 for v in wc_values) / len(wc_values)
    wc_std: float = wc_var ** 0.5 or 1.0

    cc_mean: float = sum(cc_values) / len(cc_values) if cc_values else 0
    cc_var: float = (
        sum((v - cc_mean) ** 2 for v in cc_values) / len(cc_values)
        if cc_values
        else 0
    )
    cc_std: float = cc_var ** 0.5 or 1.0

    sc_mean: float = 0.0
    sc_std: float = 1.0
    target_sc_norm: float = 0.0
    if has_sc:
        sc_mean = sum(sc_values) / len(sc_values)
        sc_var: float = sum((v - sc_mean) ** 2 for v in sc_values) / len(sc_values)
        sc_std = sc_var ** 0.5 or 1.0
        target_sc_norm = (sentence_count - sc_mean) / sc_std

    target_wc_norm: float = (word_count - wc_mean) / wc_std
    target_cc_norm: float = (chunk_count - cc_mean) / cc_std if cc_values else 0.0

    scored: list[tuple[dict[str, Any], float, bool]] = []
    for s in per_job_stats:
        wc: float = s.get("word_count", 0)
        cc: float = s.get("chunk_count", 0)
        if not wc:
            continue

        wc_norm: float = (wc - wc_mean) / wc_std
        cc_norm: float = (cc - cc_mean) / cc_std if cc_values else 0.0
        # sentence_count contribution — neutral (norm=0) for entries lacking it
        sc_norm: float = (
            ((s.get("sentence_count") or sc_mean) - sc_mean) / sc_std
            if has_sc
            else 0.0
        )
        dist: float = (
            (target_wc_norm - wc_norm) ** 2
            + (target_cc_norm - cc_norm) ** 2
            + ((target_sc_norm - sc_norm) ** 2 if has_sc else 0.0)
        ) ** 0.5
        same_voice: bool = (
            s.get("voice_id", "") == features.get("voice_id", "")
        )
        scored.append((s, dist, same_voice))

    if not scored:
        return None, None

    scored.sort(key=lambda x: x[1])
    candidates: list[tuple[dict[str, Any], float, bool]] = scored[
        :SIMILARITY_CANDIDATES
    ]

    total_weight: float = 0.0
    sim_llm: float = 0.0
    sim_voice: float = 0.0
    sim_transcribe: float = 0.0
    sim_render: float = 0.0

    for s, dist, same_voice in candidates:
        weight: float = 1.0 / (1.0 + dist)
        if same_voice:
            weight *= SAME_VOICE_BONUS
        total_weight += weight
        if s.get("llm_duration"):
            sim_llm += weight * s["llm_duration"]
        if s.get("voice_duration"):
            sim_voice += weight * s["voice_duration"]
        if s.get("transcribe_duration"):
            sim_transcribe += weight * s["transcribe_duration"]
        if s.get("render_duration"):
            sim_render += weight * s["render_duration"]

    if total_weight <= 0:
        return None, None

    sim_llm /= total_weight
    sim_voice /= total_weight
    sim_transcribe /= total_weight
    sim_render /= total_weight

    n: int = len(candidates)
    if n < SIMILARITY_MIN_CANDIDATES:
        all_llm: list[float] = [
            float(s["llm_duration"]) for s in per_job_stats if s.get("llm_duration") is not None
        ]
        all_video: list[float] = [
            (
                s.get("voice_duration", 0)
                + s.get("transcribe_duration", 0)
                + s.get("render_duration", 0)
            )
            for s in per_job_stats
            if s.get("voice_duration")
        ]
        global_avg_llm: float | None = (
            sum(all_llm) / len(all_llm) if all_llm else None
        )
        global_avg_video: float | None = (
            sum(all_video) / len(all_video) if all_video else None
        )

        blend: float = n / SIMILARITY_MIN_CANDIDATES
        if global_avg_llm:
            sim_llm = blend * sim_llm + (1 - blend) * global_avg_llm
        if global_avg_video:
            sim_video: float = (
                blend * (sim_voice + sim_transcribe + sim_render)
                + (1 - blend) * global_avg_video
            )
        else:
            sim_video = sim_voice + sim_transcribe + sim_render
    else:
        sim_video = sim_voice + sim_transcribe + sim_render

    # Blend similarity prediction with rate-based prediction
    rates: dict[str, float] = _compute_phase_rates(per_job_stats)
    rate_llm, rate_video = _predict_by_rates(features, rates)

    pred_llm: float | None = sim_llm
    pred_video: float | None = sim_video

    if rate_llm is not None and pred_llm is not None:
        pred_llm = RATE_BLEND_ALPHA * pred_llm + (1.0 - RATE_BLEND_ALPHA) * rate_llm
    if rate_video is not None and pred_video is not None:
        pred_video = RATE_BLEND_ALPHA * pred_video + (1.0 - RATE_BLEND_ALPHA) * rate_video

    return pred_llm, pred_video


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
# Memory warning
# ---------------------------------------------------------------------------


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
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Job-config building
# ---------------------------------------------------------------------------


def _build_job_configs(
    num_shorts: int,
    selected_prompts: list[str] | None = None,
    enable_emojis: bool | None = None,
    enable_emoji_animation: bool | None = None,
    emoji_scale_factor: float | None = None,
    emoji_hold_duration: float | None = None,
    emoji_throw_max_count: int | None = None,
    emoji_styles: list[str] | None = None,
) -> tuple[dict[int, dict[str, Any]], str]:
    """Build job configuration dicts for a batch run.

    Handles retry configs (from ``_retry_configs``) and fresh configs built
    from templates, shuffled prompts, and randomised settings.

    Args:
        num_shorts: Number of shorts to generate.
        selected_prompts: Optional list of prompt titles to restrict to.
        enable_emojis: Override for emoji enablement.
        enable_emoji_animation: Override for emoji animation.
        emoji_scale_factor: Override for emoji scale.
        emoji_hold_duration: Override for emoji hold duration.
        emoji_throw_max_count: Override for emoji throw count.
        emoji_styles: Override list of emoji font styles.

    Returns:
        Tuple of ``(job_configs_dict, timestamp_str)``.
    """
    from gui.config import DEFAULT_SCRIPT_SYSTEM_PROMPT, load_prompt_templates
    from gui.utils import get_active_llm_profile

    templates: dict[str, str] = load_prompt_templates()
    timestamp: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    active_profile: dict[str, Any] = get_active_llm_profile()
    model: str = active_profile.get("model", DEFAULT_LLM_MODEL)

    default_system_prompt: str = DEFAULT_SCRIPT_SYSTEM_PROMPT
    max_words: int = shared_state.settings.get("max_words", 400)
    raw_system_prompt: str = shared_state.settings.get(
        "system_prompt", default_system_prompt
    )
    try:
        system_prompt: str = raw_system_prompt.format(
            max_words=max_words,
            max_words_seconds=int(max_words / 2.3),
        )
    except (KeyError, ValueError):
        system_prompt = raw_system_prompt

    # Append title/hashtag instructions
    system_prompt += (
        "\n\n9. After the script ends, include exactly one line "
        "'TITLE: <short catchy title under 5 words>' "
        "followed by one line 'HASHTAGS: <5 trending hashtags>' "
        "based on your script. "
        "Do not include these lines within the script body."
    )

    job_configs: dict[int, dict[str, Any]] = {}
    batch_state["job_details"] = {}

    # Check if we have retry configs
    retry_configs: list[dict[str, Any]] | None = batch_state.get("_retry_configs")
    if retry_configs:
        job_configs = {i + 1: cfg for i, cfg in enumerate(retry_configs)}
        for idx, cfg in job_configs.items():
            cfg["index"] = idx
        batch_state["_retry_configs"] = None
        batch_state["job_details"] = {}
        for idx, cfg in job_configs.items():
            batch_state["job_details"][idx] = {
                "topic": (
                    cfg.get("prompt", "Retry")[:40]
                    if isinstance(cfg.get("prompt"), str)
                    else "Retry"
                ),
                "voice": (
                    cfg.get("voice_id", "unknown")
                    if isinstance(cfg.get("voice_id"), str)
                    else "unknown"
                ),
                "layout": "Split-Screen"
                if cfg.get("bg_video_bottom_path")
                else "Full Screen",
            }
        return job_configs, timestamp

    # Build fresh configs
    pool: dict[str, str] = templates
    if selected_prompts and templates:
        pool = {k: v for k, v in templates.items() if k in selected_prompts}
        if not pool:
            pool = templates
    prompt_items: list[tuple[str, str]] = (
        list(pool.items()) if pool else [("Random", "A surprising fact about space.")]
    )
    random.shuffle(prompt_items)

    def _resolve_music(path: str | None) -> str | None:
        if not path:
            return None
        if os.path.exists(path):
            return path
        if os.path.exists(os.path.join(BASE_DIR, path)):
            return os.path.join(BASE_DIR, path)
        return path

    vibrant_colors: list[str] = [
        "#FFFF00", "#00FFFF", "#00FF00", "#FF00FF",
        "#FF3333", "#FF9900", "#0080FF", "#FF55BB", "#33FF33",
    ]
    font_options: list[str] = [
        "Arial", "Impact", "Georgia", "Courier New", "Times New Roman",
    ]
    animation_options: list[str] = [
        "tiktok_pop", "karaoke_sweep", "bouncy_bounce",
        "cinematic_zoom", "glow_shake", "neon_flicker",
        "pulse_grow", "fade_in_slide", "typewriter_swipe",
    ]
    setting_options: list[str] = [
        "Set this story in a small coastal town.",
        "Set this story in a bustling metropolis.",
        "Set this story in a remote mountain village.",
        "Set this story in a decaying industrial city.",
        "Set this story in the desert southwest.",
        "Set this story in a small Midwestern farm town.",
        "Set this story on a humid tropical island.",
        "Set this story in a historic European city.",
        "Set this story in a quiet suburban neighborhood.",
        "Set this story in a frozen northern wilderness.",
    ]
    tone_options: list[str] = [
        "Tell this with a melancholic, reflective tone.",
        "Tell this with a darkly humorous edge.",
        "Tell this with a tense, urgent feel.",
        "Tell this with a warm, hopeful tone.",
        "Tell this with a cynical, gritty tone.",
        "Tell this with a nostalgic, bittersweet feel.",
        "", "", "",
    ]
    inactive_alpha_options: list[str] = ["44", "66", "88", "AA"]

    for i in range(1, num_shorts + 1):
        template_title, prompt = prompt_items[(i - 1) % len(prompt_items)]
        voice_name, voice_id = random.choice(shared_state.VOICES)
        is_split: bool = random.choice([True, False])
        top_video: str = "random"
        bottom_video: str = "random" if is_split else ""

        os.makedirs(MUSIC_DIR, exist_ok=True)
        music_files: list[str] = [
            os.path.basename(f) for f in list_music_files(MUSIC_DIR)
        ]
        chosen_music: str | None = (
            os.path.join(MUSIC_DIR, random.choice(music_files))
            if music_files
            else _resolve_music("music/default_music.mp3")
        )

        sub_font: str = random.choice(font_options)
        sub_size: int = random.randint(64, 84)
        sub_highlight: str = random.choice(vibrant_colors)
        sub_outline_width: int = random.randint(4, 7)
        sub_bold: bool = random.choice([True, False])

        _enable_emojis: bool = (
            enable_emojis
            if enable_emojis is not None
            else shared_state.settings.get("enable_emojis", True)
        )
        word_pop: bool = random.choice([True, False])
        word_pop_scale: float = (
            round(random.uniform(1.10, 1.25), 2) if word_pop else 1.0
        )
        inactive_dim: bool = random.choice([True, False])
        inactive_alpha: str = (
            random.choice(inactive_alpha_options) if inactive_dim else "FF"
        )
        sub_animation_style: str = random.choice(animation_options)

        script_temp: float = shared_state.settings.get("llm_temp_script", 0.7)
        meta_temp: float = shared_state.settings.get("llm_temp_metadata", 0.7)
        output_filename: str = f"rendered_batch_{timestamp}_{i}.mp4"

        global_wps: str = shared_state.settings.get("words_per_screen", "3")
        words_per_screen_choice: str = (
            random.choice(["1", "3", "sentence"]) if global_wps == "random" else global_wps
        )

        random_setting: str = random.choice(setting_options)
        random_tone: str = random.choice(tone_options)
        prompt_modifier: str = " ".join(
            filter(None, [random_setting, random_tone])
        ).strip()

        job_configs[i] = {
            "index": i,
            "prompt": (
                f"[{template_title}] {prompt} {prompt_modifier}"
                if prompt_modifier
                else f"[{template_title}] {prompt}"
            ),
            "voice_id": voice_id,
            "bg_video_path": top_video,
            "bg_video_bottom_path": bottom_video,
            "bg_music_path": chosen_music,
            "music_volume": shared_state.settings.get("music_volume", 0.15),
            "voice_volume": shared_state.settings.get("voice_volume", 1.0),
            "sub_font": sub_font,
            "sub_size": sub_size,
            "sub_color": "#FFFFFF",
            "sub_highlight": sub_highlight,
            "sub_outline": "#000000",
            "sub_outline_width": sub_outline_width,
            "sub_bold": sub_bold,
            "enable_emojis": _enable_emojis,
            "emoji_scale_factor": (
                emoji_scale_factor
                if emoji_scale_factor is not None
                else shared_state.settings.get("emoji_scale_factor", 1.5)
            ),
            "emoji_hold_duration": (
                emoji_hold_duration
                if emoji_hold_duration is not None
                else shared_state.settings.get("emoji_hold_duration", 0.5)
            ),
            "enable_emoji_animation": (
                enable_emoji_animation
                if enable_emoji_animation is not None
                else shared_state.settings.get("enable_emoji_animation", True)
            ),
            "emoji_throw_max_count": (
                emoji_throw_max_count
                if emoji_throw_max_count is not None
                else shared_state.settings.get("emoji_throw_max_count", 3)
            ),
            "word_pop": word_pop,
            "word_pop_scale": word_pop_scale,
            "inactive_dim": inactive_dim,
            "inactive_alpha": inactive_alpha,
            "sub_uppercase": shared_state.settings.get("sub_uppercase", True),
            "voice_speed": shared_state.settings.get("voice_speed", 1.0),
            "sub_border_style": shared_state.settings.get("sub_border_style", 1),
            "sub_shadow_width": shared_state.settings.get("sub_shadow_width", 0),
            "sub_bg_color": shared_state.settings.get("sub_bg_color", "#000000"),
            "sub_bg_alpha": shared_state.settings.get("sub_bg_alpha", "80"),
            "single_word_mode": shared_state.settings.get("single_word_mode", False),
            "words_per_screen": words_per_screen_choice,
            "emoji_position": shared_state.settings.get("emoji_position", "above"),
            "emoji_style": (
                random.choice(emoji_styles)
                if emoji_styles
                else shared_state.settings.get("emoji_style", "apple")
            ),
            "sub_animation_style": sub_animation_style,
            "script_temp": script_temp,
            "meta_temp": meta_temp,
            "output_filename": output_filename,
            "model": model,
            "system_prompt": system_prompt,
            "settings": shared_state.settings.copy(),
        }

        batch_state["job_details"][i] = {
            "topic": f"[{template_title}] {prompt[:35]}...",
            "voice": voice_name,
            "layout": "Split-Screen" if is_split else "Full Screen",
            "enable_emojis": _enable_emojis,
            "emoji_style": job_configs[i]["emoji_style"],
        }

    return job_configs, timestamp


# ---------------------------------------------------------------------------
# Pipeline loop
# ---------------------------------------------------------------------------


def _run_pipeline(
    job_configs: dict[int, dict[str, Any]],
    num_shorts: int,
    failure_mode: str,
) -> None:
    """Main polling loop — two-phase: LLM then Video.

    Submits all LLM workers, then as each LLM finishes submits its video
    worker.  Returns when all futures complete or the batch is cancelled.

    Args:
        job_configs: Job configuration dicts keyed by index.
        num_shorts: Number of shorts in the batch.
        failure_mode: ``"stop_all"`` or ``"continue"`` on job failure.
    """
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

    from gui.batch import llm_job_worker, video_job_worker
    from gui.progress_utils import log_memory_usage

    import hashlib

    max_workers: int = _resolve_worker_count("max_workers", 1)
    llm_max_workers: int = _resolve_worker_count("llm_max_workers", 5)
    batch_state["max_workers"] = max_workers
    batch_state["llm_max_workers"] = llm_max_workers
    batch_state["_smoothed_eta"] = {}

    _last_digest: str = ""
    _last_broadcast: float = 0.0
    _broadcast_heartbeat: float = 5.0
    logger.info(
        "[Batch Thread] Starting %d shorts with %d video workers, %d LLM workers, "
        "failure_mode=%s",
        num_shorts,
        max_workers,
        llm_max_workers,
        failure_mode,
    )

    for i in range(1, num_shorts + 1):
        batch_state["shared_progress"][i] = "Queued"

    ctx = multiprocessing.get_context("spawn")
    batch_state["executor"] = ProcessPoolExecutor(
        max_workers=max_workers, mp_context=ctx, max_tasks_per_child=1
    )
    batch_state["llm_executor"] = ThreadPoolExecutor(max_workers=llm_max_workers)
    log_memory_usage("Before LLM phase")

    llm_futures: list[tuple[int, Any]] = []
    for i in range(1, num_shorts + 1):
        batch_state["shared_progress"][f"{i}_start"] = time.time()
        batch_state["shared_progress"][i] = "Connecting to LLM..."
        f = batch_state["llm_executor"].submit(
            llm_job_worker, job_configs[i], batch_state["shared_progress"]
        )
        llm_futures.append((i, f))

    video_futures: list[tuple[int, Any]] = []
    batch_state["futures"] = []

    _sync_progress(batch_state, num_shorts)
    while llm_futures or video_futures:
        if batch_state["should_cancel"]:
            for _, f in llm_futures:
                f.cancel()
            for _, f in video_futures:
                f.cancel()
            if "_cancelled_job_configs" not in batch_state:
                batch_state["_cancelled_job_configs"] = []
            for i in range(1, num_shorts + 1):
                status = batch_state["shared_progress"].get(i)
                if status in ("Queued", "Waiting for LLM"):
                    batch_state["shared_progress"][i] = "Cancelled"
                    if i in job_configs:
                        batch_state["_cancelled_job_configs"].append(
                            job_configs[i]
                        )
            break

        _sync_progress(batch_state, num_shorts)

        # Broadcast batch status when progress changes or on heartbeat
        now = time.time()
        status_digest = hashlib.md5(
            str([
                (j, batch_state["shared_progress"].get(j))
                for j in range(1, num_shorts + 1)
                for sk in ["_phase_llm_end", "_phase_voice_start",
                            "_phase_transcribe_start", "_phase_render_start"]
                if sk in batch_state["shared_progress"]
            ]).encode()
        ).hexdigest()
        if status_digest != _last_digest or (now - _last_broadcast) >= _broadcast_heartbeat:
            _last_digest = status_digest
            _last_broadcast = now
            from gui.routers.batch import build_batch_status
            broadcast_batch_status(build_batch_status())

        # Process completed LLM futures
        llm_futures = _process_llm_futures(
            llm_futures, video_futures, job_configs, failure_mode, batch_state
        )

        if not llm_futures and video_futures:
            log_memory_usage("LLM phase complete")

        if batch_state["should_cancel"]:
            continue

        # Process completed video futures
        video_futures = _process_video_futures(
            video_futures, job_configs, failure_mode
        )

        if batch_state["should_cancel"]:
            continue

        time.sleep(PIPELINE_POLL_INTERVAL)


def _process_llm_futures(
    llm_futures: list[tuple[int, Any]],
    video_futures: list[tuple[int, Any]],
    job_configs: dict[int, dict[str, Any]],
    failure_mode: str,
    batch_state: dict[str, Any],
) -> list[tuple[int, Any]]:
    """Process completed LLM futures, submitting video jobs for successful ones.

    Returns:
        Remaining (not-yet-complete) LLM futures.
    """
    still_llm: list[tuple[int, Any]] = []
    for i, f in llm_futures:
        if f.done():
            try:
                success, script_text, err_msg = f.result()
                if success:
                    job_configs[i]["script_text"] = script_text
                    logger.info(
                        "[Batch] Job #%d — LLM done: %d words, submitting to video phase",
                        i,
                        len(script_text.split()),
                    )
                    features = _extract_job_features(script_text, job_configs[i])
                    if features:
                        batch_state["_job_features"][i] = features
                    batch_state["shared_progress"][i] = "Waiting for Compilation"
                    batch_state["shared_progress"][f"{i}_phase_llm_end"] = time.time()
                    from gui.batch import video_job_worker
                    vf = batch_state["executor"].submit(
                        video_job_worker, job_configs[i], batch_state["shared_progress"]
                    )
                    video_futures.append((i, vf))
                else:
                    _handle_job_failure(
                        i, err_msg, job_configs, failure_mode, "LLM"
                    )
                    if batch_state["should_cancel"]:
                        break
            except Exception as e:
                logger.error("[Batch Thread] LLM job %d exception: %s", i, e)
                _handle_job_failure(
                    i, str(e), job_configs, failure_mode, "LLM"
                )
                if batch_state["should_cancel"]:
                    break
        else:
            still_llm.append((i, f))
    return still_llm


def _process_video_futures(
    video_futures: list[tuple[int, Any]],
    job_configs: dict[int, dict[str, Any]],
    failure_mode: str,
) -> list[tuple[int, Any]]:
    """Process completed video futures.

    Returns:
        Remaining (not-yet-complete) video futures.
    """
    still_video: list[tuple[int, Any]] = []
    for i, f in video_futures:
        if f.done():
            try:
                idx, success, msg = f.result()
                if success:
                    logger.info("[Batch] Job #%d — video done: %s", idx, msg)
                else:
                    logger.warning("[Batch] Job #%d — video failed: %s", idx, msg)
                    batch_state["failed_job_configs"].append(job_configs.get(i))
                    notify_clients(
                        "batch",
                        "job_failed",
                        f"Job #{idx} failed (Video): {msg}",
                        "error",
                        {"job_id": idx},
                    )
                    if failure_mode == "stop_all":
                        logger.error(
                            "[Batch Thread] Video job %d failed: %s. Cancelling batch.",
                            idx,
                            msg,
                        )
                        batch_state["should_cancel"] = True
                        batch_state["shared_progress"][idx] = f"Failed: {msg}"
                        break
            except Exception as e:
                logger.error("[Batch Thread] Video job %d exception: %s", i, e)
                batch_state["failed_job_configs"].append(job_configs.get(i))
                notify_clients(
                    "batch",
                    "job_failed",
                    f"Job #{i} failed (Video): {e}",
                    "error",
                    {"job_id": i},
                )
                if failure_mode == "stop_all":
                    batch_state["should_cancel"] = True
                    batch_state["shared_progress"][i] = f"Failed: {str(e)}"
                    break
        else:
            still_video.append((i, f))
    return still_video


def _handle_job_failure(
    job_id: int,
    err_msg: str | None,
    job_configs: dict[int, dict[str, Any]],
    failure_mode: str,
    phase: str,
) -> None:
    """Record a job failure and optionally cancel the batch.

    Args:
        job_id: The failing job index.
        err_msg: Error message.
        job_configs: Job config dictionary.
        failure_mode: ``"stop_all"`` or ``"continue"``.
        phase: Phase name (``"LLM"`` or ``"Video"``).
    """
    if err_msg:
        batch_state["shared_progress"][job_id] = f"Failed: {err_msg}"
    else:
        batch_state["shared_progress"][job_id] = f"Failed: {phase} error"
    batch_state["failed_job_configs"].append(job_configs.get(job_id))
    notify_clients(
        "batch",
        "job_failed",
        f"Job #{job_id} failed ({phase}): {err_msg}",
        "error",
        {"job_id": job_id},
    )
    if failure_mode == "stop_all":
        batch_state["should_cancel"] = True


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


# ---------------------------------------------------------------------------
# Main batch worker thread
# ---------------------------------------------------------------------------


def batch_worker_thread(
    num_shorts: int,
    selected_prompts: list[str] | None = None,
    enable_emojis: bool | None = None,
    enable_emoji_animation: bool | None = None,
    emoji_scale_factor: float | None = None,
    emoji_hold_duration: float | None = None,
    emoji_throw_max_count: int | None = None,
    emoji_styles: list[str] | None = None,
) -> None:
    """Entry point for the background batch worker thread.

    Loads learned phase weights, builds job configs, runs the pipeline,
    and persists results.

    Args:
        num_shorts: Number of shorts to generate.
        selected_prompts: Optional list of prompt titles to restrict to.
        enable_emojis: Override for emoji enablement.
        enable_emoji_animation: Override for emoji animation.
        emoji_scale_factor: Override for emoji scale.
        emoji_hold_duration: Override for emoji hold duration.
        emoji_throw_max_count: Override for emoji throw count.
        emoji_styles: Override list of emoji font styles.
    """
    batch_state["in_progress"] = True
    notify_clients(
        "batch",
        "started",
        f"Batch generation started for {num_shorts} shorts.",
        "info",
        {"total": num_shorts},
    )
    batch_state["should_cancel"] = False
    batch_state["failed_job_configs"] = []
    batch_state["batch_results"] = []
    loaded = _load_phase_weights()
    batch_state["_phase_weights"] = loaded["phase_ratios"]
    batch_state["_avg_llm_duration"] = loaded["avg_llm_duration"]
    batch_state["_avg_video_duration"] = loaded["avg_video_duration"]
    batch_state["_phase_rates"] = loaded.get("phase_rates", {})
    batch_state["_job_features"] = {}
    batch_state["_per_job_stats"] = loaded.get("per_job_stats", [])
    failure_mode: str = shared_state.settings.get("batch_failure_mode", "stop_all")

    _log_mem = None
    try:
        from gui.progress_utils import log_memory_usage

        _log_mem = log_memory_usage
        log_memory_usage("After model unloading")

        job_configs, _timestamp = _build_job_configs(
            num_shorts,
            selected_prompts=selected_prompts,
            enable_emojis=enable_emojis,
            enable_emoji_animation=enable_emoji_animation,
            emoji_scale_factor=emoji_scale_factor,
            emoji_hold_duration=emoji_hold_duration,
            emoji_throw_max_count=emoji_throw_max_count,
            emoji_styles=emoji_styles,
        )
        batch_state["job_configs"] = job_configs

        _run_pipeline(job_configs, num_shorts, failure_mode)
        _collect_and_persist_results(job_configs, num_shorts)

    except Exception as e:
        logger.error("[Batch Thread] Crash: %s", e)
        notify_clients(
            "batch", "error", f"Batch generation crashed: {e}", "error"
        )
        logger.exception("Exception occurred")
    finally:
        if batch_state.get("executor"):
            batch_state["executor"].shutdown(wait=True, cancel_futures=True)
        if batch_state.get("llm_executor"):
            batch_state["llm_executor"].shutdown(wait=True, cancel_futures=True)
        if batch_state.get("manager"):
            batch_state["manager"].shutdown()
        batch_state["in_progress"] = False

        from generator.utils import _release_memory_to_os

        _release_memory_to_os()
        if _log_mem is not None:
            _log_mem("After cleanup")
