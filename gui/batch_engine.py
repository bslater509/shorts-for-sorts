"""Batch generation engine — extracted from server.py for modularity.

Contains the batch state, phase tracking constants, ETA computation helpers,
phase weight persistence, and the main batch_worker_thread orchestrator.
"""

import datetime
import json
import os
import random
import re
import threading
import time

import gui.state as shared_state
from gui.config import (
    BASE_DIR,
    BATCH_STATS_FILE,
    FAILED_CONFIGS_FILE,
    MUSIC_DIR,
    console,
    logger,
)
from gui.ws_manager import notify_clients

# ---------------------------------------------------------------------------
# Batch state (thread-safe via _batch_lock and _batch_state_lock)
# ---------------------------------------------------------------------------

_batch_lock = threading.Lock()  # Guards batch_state["in_progress"] TOCTOU
_batch_state_lock = threading.RLock()

batch_state = {
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
    "max_workers": 1,
    "llm_max_workers": 5,
    "_smoothed_eta": {},
    "_phase_weights": None,
}

# ---------------------------------------------------------------------------
# Worker count resolution
# ---------------------------------------------------------------------------


def _resolve_worker_count(key, default, min_val=1):
    """Resolve a worker count from settings with a fallback default."""
    val = shared_state.settings.get(key)
    if val:
        try:
            return max(min_val, int(val))
        except (ValueError, TypeError):
            return default
    return default


# ---------------------------------------------------------------------------
# Video pipeline phase constants (sequential, after LLM)
# ---------------------------------------------------------------------------

VIDEO_PHASES = [
    ("Voice", 20, 45),
    ("Transcribe", 45, 55),
    ("Render", 55, 100),
]
DEFAULT_VIDEO_WEIGHTS = {"Voice": 0.35, "Transcribe": 0.10, "Render": 0.55}

# Overall phase ratios (including LLM) stored in batch_stats.json
DEFAULT_PHASE_WEIGHTS = {"LLM": 0.05, "Voice": 0.30, "Transcribe": 0.10, "Render": 0.55}

# Phase tracking keys — set by batch_worker_thread (llm_end) or ProgressConsole (rest)
_PHASE_TRACKING_KEYS = [
    "_phase_llm_end",
    "_phase_voice_start",
    "_phase_transcribe_start",
    "_phase_render_start",
]


# ---------------------------------------------------------------------------
# Progress / ETA helpers
# ---------------------------------------------------------------------------


def compute_video_progress(pct, weights=None):
    """Convert raw progress percentage (0-100) to time-weighted fraction of the video pipeline (0-1).
    
    Only covers Voice/Transcribe/Render — excludes LLM (which runs in parallel
    across all jobs with different timing characteristics).
    Uses learned weights from completed batch runs when available.
    """
    if not pct or pct <= 20:
        return 0.0
    w = weights if weights else DEFAULT_VIDEO_WEIGHTS
    completed = 0.0
    for name, p_start, p_end in VIDEO_PHASES:
        span = p_end - p_start
        if pct >= p_end:
            completed += w.get(name, 0.30)
        elif pct > p_start:
            phase_pct = (pct - p_start) / span
            completed += w.get(name, 0.30) * phase_pct
    return min(completed, 1.0)


def _compute_eta(
    start_time, end_time, pct, status, job_phase_times, avg_completion_time, smoothed_etas, job_id,
    phase_weights=None, avg_llm_duration=None, avg_video_duration=None,
    job_features=None, per_job_stats=None,
):
    """Compute ETA with phase weighting, avg completion blending, and smoothing.
    
    When job_features (from _extract_job_features) and per_job_stats (historical
    records in batch_stats.json) are available, uses similarity-weighted prediction
    to produce job-specific duration estimates instead of global averages.
    
    Returns (eta_str, eta_seconds, elapsed_str, eta_llm, eta_video).
    eta_llm/eta_video: pipeline-aware breakdown (remaining seconds, 0 if phase done)
    for use in global pipeline ETA calculation.
    """
    from gui.batch import format_elapsed

    if not start_time:
        return "--", 0.0, "--", 0.0, 0.0

    now = time.time()
    duration = (end_time if end_time else now) - start_time
    elapsed_str = format_elapsed(duration)

    if status == "Done":
        return "0s", 0.0, elapsed_str + " (Done)", 0.0, 0.0

    if not (pct and pct > 0):
        return "--", 0.0, elapsed_str, 0.0, 0.0

    # Determine effective duration estimates — use job-specific prediction when available
    effective_llm_dur = avg_llm_duration
    effective_video_dur = avg_video_duration
    if job_features and job_features.get("word_count") and per_job_stats:
        pred_llm, pred_video = _predict_phase_duration(job_features, per_job_stats)
        if pred_llm is not None:
            effective_llm_dur = pred_llm
        if pred_video is not None:
            effective_video_dur = pred_video

    # Pipeline-aware breakdown
    llm_done = job_phase_times and job_phase_times.get("_phase_llm_end") is not None

    if llm_done:
        # LLM phase complete — remaining time is all video
        llm_end = job_phase_times["_phase_llm_end"]
        video_elapsed = (end_time if end_time else now) - llm_end
        video_progress = compute_video_progress(pct, weights=phase_weights)
        if effective_video_dur is not None and video_progress < 0.3:
            # Early in video phase — use learned average for stability
            eta_video = effective_video_dur * max(0, 1.0 - video_progress)
        elif video_progress > 0:
            eta_video = video_elapsed / video_progress * (1.0 - video_progress)
        else:
            eta_video = effective_video_dur if effective_video_dur else 60
        eta_llm = 0.0
    else:
        # Still in LLM phase — estimate LLM remaining, use learned avg for video
        effective_progress = compute_video_progress(pct, weights=phase_weights)
        if effective_progress > 0:
            # Job already in video pipeline but no llm_end recorded (edge case)
            eta_video = duration / effective_progress * (1.0 - effective_progress)
        else:
            eta_video = effective_video_dur if effective_video_dur else 60
        # LLM remaining from overall progress
        llm_fraction = min(1.0, (pct or 0) / 20.0) if pct else 0
        if llm_fraction > 0:
            eta_llm = duration / llm_fraction * (1.0 - llm_fraction)
        else:
            eta_llm = effective_llm_dur if effective_llm_dur else 30

    # Total job-remaining for per-job display
    eta_seconds = eta_llm + eta_video

    # Apply exponential smoothing to prevent wild jumps (on total)
    if smoothed_etas is not None and job_id is not None:
        prev = smoothed_etas.get(job_id, eta_seconds)
        smoothed = 0.3 * eta_seconds + 0.7 * prev
        smoothed_etas[job_id] = smoothed
        eta_seconds = smoothed
        # Scale breakdown proportionally
        total_raw = eta_llm + eta_video
        if total_raw > 0:
            ratio = eta_seconds / total_raw
            eta_llm *= ratio
            eta_video *= ratio

    return format_elapsed(eta_seconds), eta_seconds, elapsed_str, eta_llm, eta_video


def _sync_progress(batch_state, num_shorts):
    """Copy shared_progress (Manager dict) to progress_dict (regular dict) for API access."""
    with _batch_state_lock:
        for i in range(1, num_shorts + 1):
            batch_state["progress_dict"][i] = batch_state["shared_progress"].get(i, "Queued")
            for suffix in ["_start", "_end"] + _PHASE_TRACKING_KEYS:
                sk = f"{i}{suffix}"
                if sk in batch_state["shared_progress"]:
                    batch_state["progress_dict"][sk] = batch_state["shared_progress"][sk]


# ---------------------------------------------------------------------------
# Feature extraction / duration prediction helpers
# ---------------------------------------------------------------------------


def _extract_job_features(script_text, job_config):
    """Extract job characteristics from script text and config for ETA prediction.
    
    Returns a dict with feature keys, or empty dict if script_text is unavailable.
    """
    if not script_text:
        return {}
    
    words = script_text.split()
    word_count = len(words)
    
    # Count sentences by sentence-ending punctuation
    sentence_count = max(1, len(re.findall(r'[.!?]+', script_text)))
    
    # Count chunks (blank-line-separated blocks) — each chunk becomes a TTS call
    chunks = [c.strip() for c in re.split(r'\n\s*\n', script_text) if c.strip()]
    chunk_count = len(chunks)
    
    # Count emoji characters in the script
    try:
        import unicodedata
        emoji_count = sum(1 for c in script_text if unicodedata.category(c) == 'So')
    except Exception:
        emoji_count = 0
    
    features = {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "chunk_count": chunk_count,
        "emoji_count": emoji_count,
        "enable_emojis": bool(job_config.get("enable_emojis", False)),
        "voice_id": str(job_config.get("voice_id", "")),
    }
    return features


def _predict_phase_duration(features, per_job_stats):
    """Predict LLM and video duration for a job based on historical per-job stats.
    
    Uses similarity-weighted average from jobs with similar features
    (word_count, chunk_count) using a normalized Euclidean distance metric.
    Blends with global average when few matching jobs exist.
    
    Args:
        features: dict from _extract_job_features() — must include word_count
        per_job_stats: list of historical per-job stat dicts (or None)
    
    Returns:
        (predicted_llm_duration, predicted_video_duration) in seconds, or (None, None)
    """
    word_count = features.get("word_count", 0)
    chunk_count = features.get("chunk_count", 0)
    if not word_count or not per_job_stats:
        return None, None
    
    # Compute feature means and stds from historical data for normalization
    wc_values = [s.get("word_count", 0) for s in per_job_stats if s.get("word_count")]
    cc_values = [s.get("chunk_count", 0) for s in per_job_stats if s.get("chunk_count")]
    
    if not wc_values:
        return None, None
    
    wc_mean = sum(wc_values) / len(wc_values)
    wc_var = sum((v - wc_mean) ** 2 for v in wc_values) / len(wc_values)
    wc_std = wc_var ** 0.5 or 1.0
    
    cc_mean = sum(cc_values) / len(cc_values) if cc_values else 0
    cc_var = sum((v - cc_mean) ** 2 for v in cc_values) / len(cc_values) if cc_values else 0
    cc_std = cc_var ** 0.5 or 1.0
    
    # Normalize target features
    target_wc_norm = (word_count - wc_mean) / wc_std
    target_cc_norm = (chunk_count - cc_mean) / cc_std if cc_values else 0.0
    
    # Compute distance and weight for every historical job
    scored = []
    for s in per_job_stats:
        wc = s.get("word_count", 0)
        cc = s.get("chunk_count", 0)
        if not wc:
            continue
        
        wc_norm = (wc - wc_mean) / wc_std
        cc_norm = (cc - cc_mean) / cc_std if cc_values else 0.0
        
        # Euclidean distance in normalized feature space
        dist = ((target_wc_norm - wc_norm) ** 2 + (target_cc_norm - cc_norm) ** 2) ** 0.5
        
        # Same voice_id gets a bonus of +1 to effective distance reduction
        same_voice = s.get("voice_id", "") == features.get("voice_id", "")
        
        scored.append((s, dist, same_voice))
    
    if not scored:
        return None, None
    
    # Sort by distance (closest first), take top 10 most similar
    scored.sort(key=lambda x: x[1])
    candidates = scored[:10]
    
    # Compute similarity-weighted average phase durations
    total_weight = 0.0
    pred_llm = 0.0
    pred_voice = 0.0
    pred_transcribe = 0.0
    pred_render = 0.0
    
    for s, dist, same_voice in candidates:
        # Convert distance to weight: closer = higher weight
        # Using 1/(1+dist) — smooth decay, no math import needed
        weight = 1.0 / (1.0 + dist)
        if same_voice:
            weight *= 1.5
        
        total_weight += weight
        if s.get("llm_duration"):
            pred_llm += weight * s["llm_duration"]
        if s.get("voice_duration"):
            pred_voice += weight * s["voice_duration"]
        if s.get("transcribe_duration"):
            pred_transcribe += weight * s["transcribe_duration"]
        if s.get("render_duration"):
            pred_render += weight * s["render_duration"]
    
    if total_weight <= 0:
        return None, None
    
    pred_llm /= total_weight
    pred_voice /= total_weight
    pred_transcribe /= total_weight
    pred_render /= total_weight
    
    # Blend with global averages when few candidates
    n = len(candidates)
    if n < 3:
        # Compute global averages from all per_job_stats for blending
        all_llm = [s.get("llm_duration") for s in per_job_stats if s.get("llm_duration")]
        all_video = [
            (s.get("voice_duration", 0) + s.get("transcribe_duration", 0) + s.get("render_duration", 0))
            for s in per_job_stats if s.get("voice_duration")
        ]
        global_avg_llm = sum(all_llm) / len(all_llm) if all_llm else None
        global_avg_video = sum(all_video) / len(all_video) if all_video else None
        
        blend = n / 3.0  # 0->1 as n goes 0->3
        if global_avg_llm:
            pred_llm = blend * pred_llm + (1 - blend) * global_avg_llm
        if global_avg_video:
            pred_video = blend * (pred_voice + pred_transcribe + pred_render) + (1 - blend) * global_avg_video
        else:
            pred_video = pred_voice + pred_transcribe + pred_render
    else:
        pred_video = pred_voice + pred_transcribe + pred_render
    
    return pred_llm, pred_video


# ---------------------------------------------------------------------------
# Phase weight persistence
# ---------------------------------------------------------------------------


def _load_phase_weights():
    """Load learned phase weights, absolute duration averages, and per-job stats from disk.
    
    Returns dict with keys:
      phase_ratios: dict {phase_name: weight} (blended with defaults)
      avg_llm_duration: float seconds or None
      avg_video_duration: float seconds or None
      per_job_stats: list of per-job feature+duration dicts or []
    """
    result = {
        "phase_ratios": dict(DEFAULT_PHASE_WEIGHTS),
        "avg_llm_duration": None,
        "avg_video_duration": None,
        "per_job_stats": [],
    }
    try:
        if os.path.exists(BATCH_STATS_FILE):
            with open(BATCH_STATS_FILE, "r") as f:
                data = json.load(f)
            stored = data.get("phase_ratios", {})
            sample_count = data.get("sample_count", 0)
            if sample_count >= 3:
                blend = min(0.8, sample_count / (sample_count + 5))
                for phase in result["phase_ratios"]:
                    if phase in stored:
                        result["phase_ratios"][phase] = blend * stored[phase] + (1 - blend) * result["phase_ratios"][phase]
            result["avg_llm_duration"] = data.get("avg_llm_duration")
            result["avg_video_duration"] = data.get("avg_video_duration")
            result["per_job_stats"] = data.get("per_job_stats", [])
    except Exception as e:
        logger.warning(f"Failed to load batch stats: {e}")
    return result


_PER_JOB_STATS_MAX = 500  # keep at most this many historical job records


def _save_phase_weights(phase_ratios, sample_count, avg_llm_duration=None, avg_video_duration=None, per_job_stats=None):
    """Persist learned phase weight ratios, absolute duration averages, and per-job stats to disk."""
    try:
        os.makedirs(os.path.dirname(BATCH_STATS_FILE), exist_ok=True)
        payload = {
            "phase_ratios": phase_ratios,
            "sample_count": sample_count,
            "avg_llm_duration": avg_llm_duration,
            "avg_video_duration": avg_video_duration,
        }
        if per_job_stats is not None:
            # Cap to prevent unbounded growth — keep most recent entries
            if len(per_job_stats) > _PER_JOB_STATS_MAX:
                per_job_stats = per_job_stats[-_PER_JOB_STATS_MAX:]
            payload["per_job_stats"] = per_job_stats
        with open(BATCH_STATS_FILE, "w") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save batch stats: {e}")


# ---------------------------------------------------------------------------
# Memory warning helper (used by start_batch endpoint)
# ---------------------------------------------------------------------------


def _log_memory_warning():
    try:
        with open("/proc/meminfo") as f:
            data = f.read()
        m = {}
        for line in data.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                m[parts[0].strip()] = int(parts[1].strip().split()[0])
        avail_mb = m.get("MemAvailable", 0) // 1024
        total_mb = m.get("MemTotal", 0) // 1024
        if avail_mb < 1024:
            logger.warning(
                f"Low memory: {avail_mb}MB available / {total_mb}MB total — batch may risk OOM"
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main batch worker thread
# ---------------------------------------------------------------------------


def batch_worker_thread(
    num_shorts,
    selected_prompts=None,
    enable_emojis=None,
    enable_emoji_animation=None,
    emoji_scale_factor=None,
    emoji_hold_duration=None,
    emoji_throw_max_count=None,
    emoji_styles=None,
):
    batch_state["in_progress"] = True
    notify_clients("batch", "started", f"Batch generation started for {num_shorts} shorts.", "info", {"total": num_shorts})
    batch_state["should_cancel"] = False
    batch_state["failed_job_configs"] = []
    batch_state["batch_results"] = []
    loaded = _load_phase_weights()
    batch_state["_phase_weights"] = loaded["phase_ratios"]
    batch_state["_avg_llm_duration"] = loaded["avg_llm_duration"]
    batch_state["_avg_video_duration"] = loaded["avg_video_duration"]
    batch_state["_job_features"] = {}  # per-job feature dicts for ETA prediction
    batch_state["_per_job_stats"] = loaded.get("per_job_stats", [])
    failure_mode = shared_state.settings.get("batch_failure_mode", "stop_all")

    try:
        from generator import unload_tts_model
        from gui.batch import llm_job_worker, log_memory_usage, unload_whisper_model, video_job_worker
        from gui.config import load_prompt_templates

        log_memory_usage("After model unloading")

        templates = load_prompt_templates()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        from gui.utils import get_active_llm_profile

        active_profile = get_active_llm_profile()
        api_key = active_profile.get("api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = active_profile.get("base_url") or os.environ.get("OPENAI_BASE_URL")

        model = active_profile.get("model", "gpt-4o-mini")

        from gui.config import DEFAULT_SCRIPT_SYSTEM_PROMPT

        default_system_prompt = DEFAULT_SCRIPT_SYSTEM_PROMPT
        max_words = shared_state.settings.get("max_words", 400)
        raw_system_prompt = shared_state.settings.get("system_prompt", default_system_prompt)
        try:
            system_prompt = raw_system_prompt.format(
                max_words=max_words, max_words_seconds=int(max_words / 2.3)
            )
        except (KeyError, ValueError):
            system_prompt = raw_system_prompt

        job_configs = {}
        batch_state["job_details"] = {}

        # Check if we have retry configs from the retry-failed endpoint
        retry_configs = batch_state.get("_retry_configs")
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
                    "layout": "Split-Screen" if cfg.get("bg_video_bottom_path") else "Full Screen",
                }

        if not retry_configs:
            # Build shuffled prompt pool to avoid duplicates in a batch
            pool = templates
            if selected_prompts and templates:
                pool = {k: v for k, v in templates.items() if k in selected_prompts}
                if not pool:
                    pool = templates  # fallback if none match
            prompt_items = (
                list(pool.items()) if pool else [("Random", "A surprising fact about space.")]
            )
            random.shuffle(prompt_items)

            # Helper to resolve music safely
            def _resolve_music(path):
                if not path:
                    return None
                if os.path.exists(path):
                    return path
                if os.path.exists(os.path.join(BASE_DIR, path)):
                    return os.path.join(BASE_DIR, path)
                return path

            for i in range(1, num_shorts + 1):
                # Cycle through shuffled prompts for diversity
                template_title, prompt = prompt_items[(i - 1) % len(prompt_items)]

                voice_name, voice_id = random.choice(shared_state.VOICES)

                is_split = random.choice([True, False])
                top_video = "random"
                bottom_video = "random" if is_split else None

                os.makedirs(MUSIC_DIR, exist_ok=True)
                music_files = [
                    f
                    for f in os.listdir(MUSIC_DIR)
                    if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg", ".flac"))
                ]

                if music_files:
                    chosen_music = os.path.join(MUSIC_DIR, random.choice(music_files))
                else:
                    chosen_music = _resolve_music("music/default_music.mp3")

                sub_font = random.choice(
                    ["Arial", "Impact", "Georgia", "Courier New", "Times New Roman"]
                )
                sub_size = random.randint(64, 84)
                sub_color = "#FFFFFF"
                vibrant_colors = [
                    "#FFFF00",
                    "#00FFFF",
                    "#00FF00",
                    "#FF00FF",
                    "#FF3333",
                    "#FF9900",
                    "#0080FF",
                    "#FF55BB",
                    "#33FF33",
                ]
                sub_highlight = random.choice(vibrant_colors)
                sub_outline = "#000000"
                sub_outline_width = random.randint(4, 7)
                sub_bold = random.choice([True, False])

                enable_emojis = (
                    enable_emojis
                    if enable_emojis is not None
                    else shared_state.settings.get("enable_emojis", True)
                )
                word_pop = random.choice([True, False])
                word_pop_scale = round(random.uniform(1.10, 1.25), 2) if word_pop else 1.0
                inactive_dim = random.choice([True, False])
                inactive_alpha = random.choice(["44", "66", "88", "AA"]) if inactive_dim else "FF"
                sub_animation_style = random.choice(
                    [
                        "tiktok_pop",
                        "karaoke_sweep",
                        "bouncy_bounce",
                        "cinematic_zoom",
                        "glow_shake",
                        "neon_flicker",
                        "pulse_grow",
                        "fade_in_slide",
                        "typewriter_swipe",
                    ]
                )

                script_temp = shared_state.settings.get("llm_temp_script", 0.7)
                meta_temp = shared_state.settings.get("llm_temp_metadata", 0.7)
                output_filename = f"rendered_batch_{timestamp}_{i}.mp4"

                # Determine words per screen strategy
                global_wps = shared_state.settings.get("words_per_screen", "3")
                if global_wps == "random":
                    words_per_screen_choice = random.choice(["1", "3", "sentence"])
                else:
                    words_per_screen_choice = global_wps

                # Random setting + tone modifiers for prompt diversity
                random_setting = random.choice([
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
                ])
                random_tone = random.choice([
                    "Tell this with a melancholic, reflective tone.",
                    "Tell this with a darkly humorous edge.",
                    "Tell this with a tense, urgent feel.",
                    "Tell this with a warm, hopeful tone.",
                    "Tell this with a cynical, gritty tone.",
                    "Tell this with a nostalgic, bittersweet feel.",
                    "",
                    "",
                    "",
                ])
                prompt_modifier = " ".join(filter(None, [random_setting, random_tone])).strip()

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
                    "sub_color": sub_color,
                    "sub_highlight": sub_highlight,
                    "sub_outline": sub_outline,
                    "sub_outline_width": sub_outline_width,
                    "sub_bold": sub_bold,
                    "enable_emojis": enable_emojis,
                    "emoji_scale_factor": emoji_scale_factor
                    if emoji_scale_factor is not None
                    else shared_state.settings.get("emoji_scale_factor", 1.5),
                    "emoji_hold_duration": emoji_hold_duration
                    if emoji_hold_duration is not None
                    else shared_state.settings.get("emoji_hold_duration", 0.5),
                    "enable_emoji_animation": enable_emoji_animation
                    if enable_emoji_animation is not None
                    else shared_state.settings.get("enable_emoji_animation", True),
                    "emoji_throw_max_count": emoji_throw_max_count
                    if emoji_throw_max_count is not None
                    else shared_state.settings.get("emoji_throw_max_count", 3),
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
                    "emoji_style": random.choice(emoji_styles) if emoji_styles else shared_state.settings.get("emoji_style", "apple"),
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
                    "enable_emojis": enable_emojis,
                    "emoji_style": job_configs[i]["emoji_style"],
                }

        batch_state["job_configs"] = job_configs

        max_workers = _resolve_worker_count("max_workers", 1)
        llm_max_workers = _resolve_worker_count("llm_max_workers", 5)
        batch_state["max_workers"] = max_workers
        batch_state["llm_max_workers"] = llm_max_workers
        batch_state["_smoothed_eta"] = {}
        logger.info(
            "[Batch Thread] Starting %d shorts with %d video workers, %d LLM workers, failure_mode=%s",
            num_shorts,
            max_workers,
            llm_max_workers,
            failure_mode,
        )

        for i in range(1, num_shorts + 1):
            batch_state["shared_progress"][i] = "Queued"

        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

        ctx = multiprocessing.get_context("spawn")
        batch_state["executor"] = ProcessPoolExecutor(
            max_workers=max_workers, mp_context=ctx, max_tasks_per_child=1
        )
        batch_state["llm_executor"] = ThreadPoolExecutor(max_workers=llm_max_workers)
        log_memory_usage("Before LLM phase")

        # Two-phase pipeline: phase 1 = all LLM, phase 2 = video as LLM completes
        llm_futures = []
        for i in range(1, num_shorts + 1):
            batch_state["shared_progress"][f"{i}_start"] = time.time()
            batch_state["shared_progress"][i] = "Waiting for LLM"
            f = batch_state["llm_executor"].submit(
                llm_job_worker, job_configs[i], batch_state["shared_progress"]
            )
            llm_futures.append((i, f))

        video_futures = []
        batch_state["futures"] = []  # regenerate for API compatibility

        # Main polling loop — two-phase: LLM then Video
        _sync_progress(batch_state, num_shorts)
        while llm_futures or video_futures:
            if batch_state["should_cancel"]:
                # Cancel all remaining futures
                for _, f in llm_futures:
                    f.cancel()
                for _, f in video_futures:
                    f.cancel()
                # Mark remaining queued jobs
                for i in range(1, num_shorts + 1):
                    status = batch_state["shared_progress"].get(i)
                    if status in ("Queued", "Waiting for LLM"):
                        batch_state["shared_progress"][i] = "Failed: Batch cancelled"
                break

            # --- Check for timed-out jobs ---
            timeout = shared_state.settings.get("batch_job_timeout", 600)
            if timeout and timeout > 0:
                now = time.time()
                # Check LLM futures
                still_llm_timeout = []
                for i, f in llm_futures:
                    if f.done():
                        still_llm_timeout.append((i, f))
                        continue
                    start = batch_state["shared_progress"].get(f"{i}_start")
                    if start and (now - start) > timeout:
                        logger.warning("[Batch] Job #%d — LLM timed out after %ds (limit: %ds)", i, int(now - start), timeout)
                        f.cancel()
                        batch_state["shared_progress"][i] = f"Failed: Timed out ({int(now - start)}s)"
                        batch_state["failed_job_configs"].append(job_configs[i])
                        notify_clients("batch", "job_failed", f"Job #{i} timed out (LLM)", "error", {"job_id": i})
                        if failure_mode == "stop_all":
                            batch_state["should_cancel"] = True
                            break
                    else:
                        still_llm_timeout.append((i, f))
                llm_futures = still_llm_timeout
                if batch_state["should_cancel"]:
                    continue

                # Check video futures
                still_video_timeout = []
                for i, f in video_futures:
                    if f.done():
                        still_video_timeout.append((i, f))
                        continue
                    # Video phase start: use LLM end timestamp, or overall start as fallback
                    v_start = batch_state["shared_progress"].get(f"{i}_phase_llm_end") or batch_state["shared_progress"].get(f"{i}_start")
                    if v_start and (now - v_start) > timeout:
                        logger.warning("[Batch] Job #%d — Video timed out after %ds (limit: %ds)", i, int(now - v_start), timeout)
                        f.cancel()
                        batch_state["shared_progress"][i] = f"Failed: Timed out ({int(now - v_start)}s)"
                        batch_state["failed_job_configs"].append(job_configs[i])
                        notify_clients("batch", "job_failed", f"Job #{i} timed out (Video)", "error", {"job_id": i})
                        if failure_mode == "stop_all":
                            batch_state["should_cancel"] = True
                            break
                    else:
                        still_video_timeout.append((i, f))
                video_futures = still_video_timeout
                if batch_state["should_cancel"]:
                    continue

            # Sync progress for API (before processing futures to capture last LLM/video state)
            _sync_progress(batch_state, num_shorts)

            # --- Process completed LLM futures ---
            still_llm = []
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
                            # Extract job features for per-job ETA prediction
                            features = _extract_job_features(script_text, job_configs[i])
                            if features:
                                batch_state["_job_features"][i] = features
                            batch_state["shared_progress"][i] = "Waiting for Compilation"
                            batch_state["shared_progress"][f"{i}_phase_llm_end"] = time.time()
                            vf = batch_state["executor"].submit(
                                video_job_worker, job_configs[i], batch_state["shared_progress"]
                            )
                            video_futures.append((i, vf))
                        else:
                            logger.warning("[Batch] Job #%d — LLM failed: %s", i, err_msg)
                            batch_state["shared_progress"][i] = f"Failed: {err_msg}"
                            batch_state["failed_job_configs"].append(job_configs[i])
                            notify_clients("batch", "job_failed", f"Job #{i} failed (LLM): {err_msg}", "error", {"job_id": i})
                            if failure_mode == "stop_all":
                                batch_state["should_cancel"] = True
                                break
                    except Exception as e:
                        logger.error(f"[Batch Thread] LLM job {i} exception: {e}")
                        batch_state["shared_progress"][i] = f"Failed: {str(e)}"
                        batch_state["failed_job_configs"].append(job_configs[i])
                        notify_clients("batch", "job_failed", f"Job #{i} failed (LLM): {e}", "error", {"job_id": i})
                        if failure_mode == "stop_all":
                            batch_state["should_cancel"] = True
                            break
                else:
                    still_llm.append((i, f))
            llm_futures = still_llm

            if not llm_futures and video_futures:
                log_memory_usage("LLM phase complete")

            if batch_state["should_cancel"]:
                continue

            # --- Process completed video futures ---
            still_video = []
            for i, f in video_futures:
                if f.done():
                    try:
                        idx, success, msg = f.result()
                        if success:
                            logger.info("[Batch] Job #%d — video done: %s", idx, msg)
                        else:
                            logger.warning("[Batch] Job #%d — video failed: %s", idx, msg)
                            batch_state["failed_job_configs"].append(job_configs[i])
                            notify_clients("batch", "job_failed", f"Job #{idx} failed (Video): {msg}", "error", {"job_id": idx})
                            if failure_mode == "stop_all":
                                logger.error(
                                    f"[Batch Thread] Video job {idx} failed: {msg}. Cancelling batch."
                                )
                                batch_state["should_cancel"] = True
                                batch_state["shared_progress"][idx] = f"Failed: {msg}"
                                break
                    except Exception as e:
                        logger.error(f"[Batch Thread] Video job {i} exception: {e}")
                        batch_state["failed_job_configs"].append(job_configs[i])
                        notify_clients("batch", "job_failed", f"Job #{i} failed (Video): {e}", "error", {"job_id": i})
                        if failure_mode == "stop_all":
                            batch_state["should_cancel"] = True
                            batch_state["shared_progress"][i] = f"Failed: {str(e)}"
                            break
                else:
                    still_video.append((i, f))
            video_futures = still_video

            if batch_state["should_cancel"]:
                continue

            time.sleep(0.5)

        # Final sync
        _sync_progress(batch_state, num_shorts)
        log_memory_usage("All jobs complete (before cleanup)")

        # Populate batch_results for the report endpoint
        batch_state["batch_results"] = []
        for i in range(1, num_shorts + 1):
            detail = batch_state["job_details"].get(i, {})
            status = batch_state["shared_progress"].get(i, "Unknown")
            config = job_configs.get(i, {})
            start = batch_state["shared_progress"].get(f"{i}_start")
            end = batch_state["shared_progress"].get(f"{i}_end")
            # Extract error message from status if it's a failure
            error = ""
            if str(status).startswith("Failed:"):
                error = str(status)[len("Failed: "):] if len(status) > 7 else status
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
                    "script_text": config.get("script_text", "")[:200],
                }
            )

        # Log batch summary
        done = sum(
            1 for i in range(1, num_shorts + 1) if batch_state["shared_progress"].get(i) == "Done"
        )
        failed = sum(
            1
            for i in range(1, num_shorts + 1)
            if str(batch_state["shared_progress"].get(i, "")).startswith("Failed")
        )
        logger.info(
            "[Batch Thread] Batch complete: %d/%d done, %d failed", done, num_shorts, failed
        )
        if failed == 0:
            notify_clients("batch", "success", f"Batch completed successfully ({done}/{num_shorts})", "success")
        elif done == 0:
            notify_clients("batch", "error", f"Batch failed completely ({failed}/{num_shorts} failed)", "error")
        else:
            notify_clients("batch", "success", f"Batch partially completed ({done} done, {failed} failed)", "info")

        # Collect phase timing ratios and absolute durations from completed jobs
        phase_durations = {"LLM": [], "Voice": [], "Transcribe": [], "Render": []}
        llm_durations = []
        video_durations = []
        pd = batch_state["progress_dict"]
        for i in range(1, num_shorts + 1):
            st = pd.get(f"{i}_start")
            et = pd.get(f"{i}_end")
            vs = pd.get(f"{i}_phase_voice_start")
            ts = pd.get(f"{i}_phase_transcribe_start")
            rs = pd.get(f"{i}_phase_render_start")
            llm_end = pd.get(f"{i}_phase_llm_end")
            if st and et and pd.get(i) == "Done" and vs and ts and rs:
                total = et - st
                if total > 0:
                    phase_durations["LLM"].append((vs - st) / total)
                    phase_durations["Voice"].append((ts - vs) / total)
                    phase_durations["Transcribe"].append((rs - ts) / total)
                    phase_durations["Render"].append((et - rs) / total)
                # Absolute durations (seconds) for pipeline ETA
                if llm_end:
                    llm_durations.append(llm_end - st)
                video_durations.append(et - vs)

        # Compute average ratios from this batch
        batch_ratios = {}
        job_count = 0
        for phase in DEFAULT_PHASE_WEIGHTS:
            durs = phase_durations[phase]
            if durs:
                job_count = len(durs)
                batch_ratios[phase] = sum(durs) / len(durs)

        avg_llm_duration = sum(llm_durations) / len(llm_durations) if llm_durations else None
        avg_video_duration = sum(video_durations) / len(video_durations) if video_durations else None

        # Always load existing data for blending (needed by downstream per-job stats too)
        stored_data = _load_phase_weights()
        stored = stored_data.get("phase_ratios", {})
        sample_count = 0
        merged = stored if stored else dict(DEFAULT_PHASE_WEIGHTS)
        merged_avg_llm = None
        merged_avg_video = None

        # Build per-job feature+duration records for historical prediction
        # (runs even if no jobs completed — just appends to existing list)
        job_features = batch_state.get("_job_features", {})
        new_job_stats = []
        pd = batch_state["progress_dict"]
        for i in range(1, num_shorts + 1):
            features = job_features.get(i, {})
            if not features or not features.get("word_count"):
                continue  # no features available (e.g. failed before LLM)
            st = pd.get(f"{i}_start")
            vs = pd.get(f"{i}_phase_voice_start")
            ts = pd.get(f"{i}_phase_transcribe_start")
            rs = pd.get(f"{i}_phase_render_start")
            et = pd.get(f"{i}_end")
            llm_end = pd.get(f"{i}_phase_llm_end")
            if st and et and vs and ts and rs:
                record = dict(features)
                if llm_end:
                    record["llm_duration"] = llm_end - st
                record["voice_duration"] = ts - vs
                record["transcribe_duration"] = rs - ts
                record["render_duration"] = et - rs
                record["video_duration"] = et - vs
                new_job_stats.append(record)

        # Load existing per_job_stats and extend with new entries
        per_job_stats = list(batch_state.get("_per_job_stats", []))
        per_job_stats.extend(new_job_stats)

        # Derive sample_count from per_job_stats so the two never diverge
        sample_count = len(per_job_stats)

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

            # Blend: weight this batch by job_count, cap influence of any single run
            blend = min(0.5, job_count / (job_count + 3))
            merged = dict(stored) if stored else dict(DEFAULT_PHASE_WEIGHTS)
            for phase in merged:
                if phase in batch_ratios:
                    merged[phase] = (1 - blend) * stored.get(phase, DEFAULT_PHASE_WEIGHTS[phase]) + blend * batch_ratios[phase]

            merged_avg_llm = None
            if avg_llm_duration is not None:
                if prev_avg_llm is not None:
                    merged_avg_llm = (1 - blend) * prev_avg_llm + blend * avg_llm_duration
                else:
                    merged_avg_llm = avg_llm_duration

            merged_avg_video = None
            if avg_video_duration is not None:
                if prev_avg_video is not None:
                    merged_avg_video = (1 - blend) * prev_avg_video + blend * avg_video_duration
                else:
                    merged_avg_video = avg_video_duration

            _save_phase_weights(merged, sample_count, merged_avg_llm, merged_avg_video, per_job_stats=per_job_stats)
        elif new_job_stats:
            # No phase ratios to blend but have new per-job stats — save them alone
            stored = _load_phase_weights()
            _save_phase_weights(
                stored.get("phase_ratios", dict(DEFAULT_PHASE_WEIGHTS)),
                sample_count,
                avg_llm_duration=stored.get("avg_llm_duration"),
                avg_video_duration=stored.get("avg_video_duration"),
                per_job_stats=per_job_stats,
            )

        # Persist failed job configs to disk for retry across restarts
        try:
            failed = batch_state.get("failed_job_configs", [])
            if failed:
                os.makedirs(os.path.dirname(FAILED_CONFIGS_FILE), exist_ok=True)
                with open(FAILED_CONFIGS_FILE, "w") as f:
                    json.dump(failed, f, default=str, indent=2)
                logger.info("[Batch Thread] Persisted %d failed configs to %s", len(failed), FAILED_CONFIGS_FILE)
        except Exception as e:
            logger.warning("[Batch Thread] Failed to persist failed configs: %s", e)

    except Exception as e:
        logger.error(f"[Batch Thread] Crash: {e}")
        notify_clients("batch", "error", f"Batch generation crashed: {e}", "error")
        logger.exception("Exception occurred")
    finally:
        if batch_state.get("executor"):
            batch_state["executor"].shutdown(wait=True, cancel_futures=True)
        if batch_state.get("llm_executor"):
            batch_state["llm_executor"].shutdown(wait=True, cancel_futures=True)
        if batch_state.get("manager"):
            batch_state["manager"].shutdown()
        batch_state["in_progress"] = False

        import gc

        gc.collect()
        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
        except Exception:
            pass
        log_memory_usage("After cleanup")
