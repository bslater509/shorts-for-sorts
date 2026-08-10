"""Progress/ETA helpers and duration prediction for batch runs.

Contains ``compute_video_progress``, ``_compute_eta``, job feature
extraction (``_extract_job_features``), and the similarity- and rate-based
duration predictors (``_compute_phase_rates``, ``_predict_by_rates``,
``_predict_phase_duration``), along with the ETA-related constants.

These functions are pure (no dependence on ``batch_state``), which keeps this
module import-safe relative to ``gui.batch_engine``.
"""

from __future__ import annotations

import re
import statistics
import time
from typing import Any

from gui.progress_utils import format_elapsed

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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

# ETA smoothing factor (0.0 = no smoothing, 1.0 = instant)
ETA_SMOOTHING_ALPHA: float = 0.3

# Number of candidates used for similarity-weighted ETA prediction
SIMILARITY_CANDIDATES: int = 10

# Blend factor threshold for few-candidate blending
SIMILARITY_MIN_CANDIDATES: int = 3

# Same-voice weight multiplier for similarity scoring
SAME_VOICE_BONUS: float = 1.5

# Blend factor for rate-based prediction vs similarity-based prediction
RATE_BLEND_ALPHA: float = 0.7

# Default duration estimates for ETA prediction
DEFAULT_LLM_DURATION: float = 30.0
DEFAULT_VIDEO_DURATION: float = 60.0

# Pipeline progress: LLM-end threshold for video phase
LLM_VIDEO_THRESHOLD: float = 20.0


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
