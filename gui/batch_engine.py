"""Batch generation engine — orchestrates multi-job batches with LLM and video workers.

Contains the batch state dictionary, worker-count resolution, the pipeline
polling loop (``_run_pipeline`` / ``_process_llm_futures`` /
``_process_video_futures`` / ``_handle_job_failure``), and the main
``batch_worker_thread`` orchestrator.

Helpers have been extracted into focused modules:

- ``gui.batch_config`` — ``_build_job_configs`` and randomization tables.
- ``gui.batch_eta`` — progress/ETA and duration prediction helpers.
- ``gui.batch_persistence`` — phase-weight persistence and result collection.
- ``gui.batch_tiktok`` — TikTok posting worker.
- ``gui.progress_utils`` — memory helpers.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import gui.state as shared_state
from gui.batch_config import _build_job_configs
from gui.batch_eta import _extract_job_features
from gui.batch_persistence import _collect_and_persist_results, _load_phase_weights
from gui.batch_tiktok import _tiktok_post_worker
from gui.config import logger
from gui.exceptions import BatchCancelledError
from gui.progress_utils import _wait_for_memory
from gui.ws_manager import broadcast_batch_status, notify_clients

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Phase tracking keys — set by batch_worker_thread (llm_end) or ProgressConsole (rest)
_PHASE_TRACKING_KEYS: list[str] = [
    "_phase_llm_end",
    "_phase_voice_start",
    "_phase_transcribe_start",
    "_phase_render_start",
]

# Poll interval for the pipeline loop
PIPELINE_POLL_INTERVAL: float = 0.1

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
    "llm_max_workers": 2,
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
# Pipeline loop
# ---------------------------------------------------------------------------


def _run_pipeline(
    job_configs: dict[int, dict[str, Any]],
    num_shorts: int,
    failure_mode: str,
    max_workers_override: int | None = None,
    llm_max_workers_override: int | None = None,
) -> None:
    """Main polling loop — two-phase: LLM then Video.

    Submits all LLM workers, then as each LLM finishes submits its video
    worker.  Returns when all futures complete or the batch is cancelled.

    Args:
        job_configs: Job configuration dicts keyed by index.
        num_shorts: Number of shorts in the batch.
        failure_mode: ``"stop_all"`` or ``"continue"`` on job failure.
        max_workers_override: Optional video worker count override.
        llm_max_workers_override: Optional LLM worker count override.
    """
    import hashlib
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

    from gui.batch import llm_job_worker
    from gui.progress_utils import log_memory_usage

    max_workers: int = _resolve_worker_count("max_workers", 1)
    llm_max_workers: int = _resolve_worker_count("llm_max_workers", 2)
    if max_workers_override is not None:
        max_workers = max(1, int(max_workers_override))
    if llm_max_workers_override is not None:
        llm_max_workers = max(1, int(llm_max_workers_override))
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

    # Set up TikTok post worker if posting is enabled
    if batch_state.get("post_to_tiktok"):
        import queue as _queue_mod
        import threading as _threading_mod
        post_q: _queue_mod.Queue = _queue_mod.Queue()
        batch_state["tiktok_post_queue"] = post_q
        batch_state["tiktok_post_results"] = {}
        post_thread = _threading_mod.Thread(
            target=_tiktok_post_worker, args=(post_q,), daemon=True
        )
        post_thread.start()
        batch_state["tiktok_post_thread"] = post_thread
        logger.info("[Batch] TikTok post worker started")

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

    _last_mem_log: float = 0.0
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
            _now = time.time()
            if _now - _last_mem_log >= 60.0:
                log_memory_usage("LLM phase complete")
                _last_mem_log = _now

        if batch_state["should_cancel"]:
            continue

        # Process completed video futures
        video_futures = _process_video_futures(
            video_futures, job_configs, failure_mode
        )

        if batch_state["should_cancel"]:
            continue

        time.sleep(PIPELINE_POLL_INTERVAL)

    # Drain and join the TikTok post worker if running
    post_q = batch_state.get("tiktok_post_queue")  # type: ignore
    post_thread = batch_state.get("tiktok_post_thread")
    if post_q is not None and post_thread is not None and post_thread.is_alive():
        logger.info("[Batch] Waiting for TikTok post worker to drain…")
        post_q.put(None)  # Send sentinel
        post_thread.join(timeout=300)  # Wait up to 5 min for uploads to complete
        if post_thread.is_alive():
            logger.warning("[Batch] TikTok post worker did not finish in time")
        else:
            logger.info("[Batch] TikTok post worker finished")


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
                    _wait_for_memory()
                    if batch_state["should_cancel"]:
                        break
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
            except BatchCancelledError:
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
                    # If post-to-TikTok is enabled, enqueue this job for upload
                    post_queue = batch_state.get("tiktok_post_queue")
                    if post_queue is not None and batch_state.get("post_to_tiktok"):
                        batch_state["shared_progress"][idx] = "Posting to TikTok…"
                        post_queue.put(idx)
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
            except BatchCancelledError:
                batch_state["shared_progress"][i] = "Cancelled"
                continue
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
    layout: str | None = None,
    voice_id: str | None = None,
    sub_animation_style: str | None = None,
    words_per_screen: str | None = None,
    single_word_mode: bool | None = None,
    bg_music_path: str | None = None,
    script_temp: float | None = None,
    meta_temp: float | None = None,
    max_workers: int | None = None,
    llm_max_workers: int | None = None,
    post_to_tiktok: bool = False,
    tiktok_delays: dict[int, float] | None = None,
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
        layout: Optional layout override ("Split-Screen", "Full Screen",
            or ``None`` for random).
        voice_id: Optional voice ID override; ``None`` for random.
        sub_animation_style: Optional subtitle animation override.
        words_per_screen: Optional words-per-screen override.
        single_word_mode: Optional single-word-mode override.
        bg_music_path: Optional music file override ("random" or ``None``
            falls back to the normal random selection).
        script_temp: Optional LLM script temperature override.
        meta_temp: Optional LLM metadata temperature override.
        max_workers: Optional video worker count override.
        llm_max_workers: Optional LLM worker count override.
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
    # Determine posting mode: new flag OR any stored job config carries it (retries)
    retry_cfgs: list[dict] = batch_state.get("_retry_configs") or []
    effective_post = post_to_tiktok or any(
        cfg.get("post_to_tiktok") for cfg in retry_cfgs
    )
    batch_state["post_to_tiktok"] = effective_post
    batch_state["tiktok_delays"] = tiktok_delays or {}
    batch_state["tiktok_post_queue"] = None
    batch_state["tiktok_post_thread"] = None
    batch_state["tiktok_post_results"] = {}
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
    _memory_telemetry_stop = None
    try:
        from gui.progress_utils import log_memory_usage
        from gui.progress_utils import start_memory_telemetry

        _log_mem = log_memory_usage
        log_memory_usage("After model unloading")
        _memory_telemetry_stop = start_memory_telemetry(interval_seconds=60.0)

        job_configs, _timestamp = _build_job_configs(
            num_shorts,
            selected_prompts=selected_prompts,
            enable_emojis=enable_emojis,
            enable_emoji_animation=enable_emoji_animation,
            emoji_scale_factor=emoji_scale_factor,
            emoji_hold_duration=emoji_hold_duration,
            emoji_throw_max_count=emoji_throw_max_count,
            emoji_styles=emoji_styles,
            layout=layout,
            voice_id=voice_id,
            sub_animation_style=sub_animation_style,
            words_per_screen=words_per_screen,
            single_word_mode=single_word_mode,
            bg_music_path=bg_music_path,
            script_temp=script_temp,
            meta_temp=meta_temp,
            post_to_tiktok=effective_post,
        )
        batch_state["job_configs"] = job_configs

        _run_pipeline(
            job_configs,
            num_shorts,
            failure_mode,
            max_workers_override=max_workers,
            llm_max_workers_override=llm_max_workers,
        )
        _collect_and_persist_results(job_configs, num_shorts)

    except Exception as e:
        logger.error("[Batch Thread] Crash: %s", e)
        notify_clients(
            "batch", "error", f"Batch generation crashed: {e}", "error"
        )
        logger.exception("Exception occurred")
    finally:
        if _memory_telemetry_stop is not None:
            from gui.progress_utils import stop_memory_telemetry

            stop_memory_telemetry(_memory_telemetry_stop)
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
