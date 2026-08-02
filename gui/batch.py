"""Batch job orchestration — job config, progress console, LLM worker, and video worker.

Contains the :class:`BatchJobConfig` dataclass, the :class:`ProgressConsole`
class that intercepts console output for progress tracking, the per-job
LLM script generation worker, and the video compilation worker for batch mode.
"""

from __future__ import annotations

import os
import re
import time
import traceback
from dataclasses import dataclass, fields
from typing import Any

from gui import state as shared_state
from gui.config import console, logger
from gui.llm_utils import parse_title_hashtags, retry_with_backoff
from gui.progress_utils import log_memory_usage
from gui.utils import resolve_preset_path
from gui.video_compiler import compile_video_flow
from gui.ws_manager import stream_llm_token, stream_llm_event

# --- Constants ---

DEFAULT_LLM_MODEL: str = "gpt-4o-mini"
"""Default model used for LLM script generation in batch mode."""

LLM_RETRY_ATTEMPTS: int = 3
"""Number of retry attempts for the LLM streaming call."""

STREAM_PROGRESS_WORD_INTERVAL: int = 5
"""Minimum word-count change to emit a progress update during streaming."""

STREAM_PROGRESS_TIME_INTERVAL: float = 0.25
"""Minimum time interval (seconds) between streaming progress updates."""

TITLE_FALLBACK: str = "Batch Video"
"""Fallback title used when LLM title generation fails."""

HASHTAGS_FALLBACK: str = "#shorts #video"
"""Fallback hashtags used when LLM hashtag generation fails."""

# Output filename fallback
BATCH_FILENAME_FALLBACK: str = "batch_video"

# Keywords that indicate retryable streaming errors
STREAM_RETRYABLE_KEYWORDS: tuple[str, ...] = (
    "rate",
    "timeout",
    "connection",
    "overloaded",
    "api_error",
    "incomplete chunked read",
)

# Non-retryable error keywords for streaming
STREAM_NON_RETRYABLE_KEYWORDS: tuple[str, ...] = (
    "bad request",
    "auth",
    "unauthorized",
    "401",
    "403",
)

# Prompt templates
TITLE_HASHTAGS_APPENDIX: str = (
    "\n\n9. After the script ends, include exactly one line "
    "'TITLE: <short catchy title under 5 words>' "
    "followed by one line 'HASHTAGS: <5 trending hashtags>' "
    "based on your script. "
    "Do not include these lines within the script body."
)
"""Appendix appended to system prompts to request title/hashtags in the response."""

# --- Cached LLM client ---

_cached_llm_client: Any = None
"""Module-level cached :class:`openai.OpenAI` client instance."""
_cached_llm_api_key: str = ""
"""Cached API key for client reuse verification."""
_cached_llm_base_url: str = ""
"""Cached base URL for client reuse verification."""


# --- Dataclasses ---


@dataclass
class BatchJobConfig:
    """Configuration for a single batch job.

    Required Fields:
        index: Job index (1-based).
        prompt: The script generation prompt.
        voice_id: Kokoro voice identifier.
        bg_video_path: Path to the top background video.
        output_filename: Desired output filename.
        settings: Global settings snapshot (for worker process isolation).
    """

    index: int
    prompt: str
    voice_id: str
    bg_video_path: str
    output_filename: str
    settings: dict[str, Any]

    # Optional fields with defaults
    bg_video_bottom_path: str | None = None
    bg_music_path: str | None = None
    music_volume: float = 0.15
    voice_volume: float = 1.0
    sub_font: str = "Arial"
    sub_size: int = 72
    sub_color: str = "#FFFFFF"
    sub_highlight: str = "#00FFFF"
    sub_outline: str = "#000000"
    sub_outline_width: int = 5
    sub_bold: bool = False
    enable_emojis: bool = False
    enable_emoji_animation: bool = True
    emoji_scale_factor: float = 1.5
    emoji_hold_duration: float = 0.5
    emoji_throw_max_count: int = 3
    word_pop: bool = False
    word_pop_scale: float = 1.0
    inactive_dim: bool = False
    inactive_alpha: str = "FF"
    voice_speed: float | None = None
    sub_uppercase: bool = True
    sub_border_style: int = 1
    sub_shadow_width: int = 0
    sub_bg_color: str = "#000000"
    sub_bg_alpha: str = "80"
    single_word_mode: bool = False
    emoji_position: str = "above"
    emoji_style: str = "Noto Color Emoji"
    sub_animation_style: str = "tiktok_pop"
    script_temp: float = 0.7
    meta_temp: float = 0.7
    model: str = DEFAULT_LLM_MODEL
    system_prompt: str = ""
    generated_title: str | None = None
    generated_hashtags: str | None = None
    script_text: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BatchJobConfig:
        """Construct a :class:`BatchJobConfig` from a dictionary, ignoring unknown keys.

        Args:
            data: Dictionary of field values.

        Returns:
            A new :class:`BatchJobConfig` instance.

        Raises:
            TypeError: If a required field is missing.
        """
        valid_fields: set[str] = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {k: data[k] for k in data if k in valid_fields}
        return cls(**kwargs)


# --- Progress Console ---


class ProgressConsole:
    """Intercepts ``console.print`` calls to extract progress information.

    Maps log-style messages to status strings stored in a shared progress
    dictionary (typically a ``multiprocessing.Manager.dict``).
    """

    def __init__(self, idx: int, p_dict: dict[Any, Any]) -> None:
        """Initialise the console proxy.

        Args:
            idx: Job index (1-based) for status key prefix.
            p_dict: Shared progress dictionary to write status updates into.
        """
        self.idx: int = idx
        self.p_dict: dict[Any, Any] = p_dict

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Intercept a print call and parse it for progress information.

        Args:
            *args: Positional arguments (first is typically the message).
            **kwargs: Keyword arguments (ignored).
        """
        msg: str = " ".join(str(a) for a in args)

        # Direct float/numeric progress callback (e.g., FFmpeg progress percentage)
        try:
            pct: float = float(msg)
            self.p_dict[self.idx] = f"FFmpeg Rendering ({pct:.1f}%)"
            return
        except (TypeError, ValueError):
            pass

        try:
            if "Generating voice for sentence" in msg or "Generating voice for chunk" in msg:
                phase_key: str = f"{self.idx}_phase_voice_start"
                if phase_key not in self.p_dict:
                    self.p_dict[phase_key] = time.time()
                match = re.search(r"(?:sentence|chunk) (\d+/\d+)", msg)
                if match:
                    self.p_dict[self.idx] = f"Voice Generation ({match.group(1)})"
                else:
                    self.p_dict[self.idx] = "Voice Generation"
            elif "Transcribing audio..." in msg or "Transcribing full audio file" in msg:
                phase_key = f"{self.idx}_phase_transcribe_start"
                if phase_key not in self.p_dict:
                    self.p_dict[phase_key] = time.time()
                match = re.search(r"(\d+)%", msg)
                if match:
                    self.p_dict[self.idx] = f"Transcription ({match.group(1)}%)"
                else:
                    self.p_dict[self.idx] = "Transcription"
            elif "[3/4]" in msg:
                self.p_dict[self.idx] = "Subtitles"
            elif "FFmpeg Rendering" in msg:
                phase_key = f"{self.idx}_phase_render_start"
                if phase_key not in self.p_dict:
                    self.p_dict[phase_key] = time.time()
                match = re.search(r"(\d+\.?\d*)%", msg)
                if match:
                    self.p_dict[self.idx] = f"FFmpeg Rendering ({match.group(1)}%)"
                else:
                    self.p_dict[self.idx] = "FFmpeg Rendering"
            elif "[4/4]" in msg:
                phase_key = f"{self.idx}_phase_render_start"
                if phase_key not in self.p_dict:
                    self.p_dict[phase_key] = time.time()
                self.p_dict[self.idx] = "FFmpeg Rendering"
            elif "\u2139\ufe0f Found cached" in msg:
                self.p_dict[self.idx] = "Reusing Cache (Voice)"
        except Exception:
            logger.debug(
                "ProgressConsole.print exception for idx=%d", self.idx, exc_info=True
            )

    def clear(self) -> None:
        """No-op for console.clear compatibility."""
        pass


# --- Orchestration ---


def orchestrate_batch_job(
    job_config: dict[str, Any],
    progress_dict: dict[Any, Any],
    llm_executor: Any,
    video_executor: Any,
) -> tuple[int, bool, str | None]:
    """Orchestrate a single batch job: LLM → video compilation.

    Args:
        job_config: Job configuration dictionary.
        progress_dict: Shared progress dictionary.
        llm_executor: ``ThreadPoolExecutor`` for LLM calls.
        video_executor: ``ProcessPoolExecutor`` for video compilation.

    Returns:
        Tuple of ``(idx, success, message_or_error)``.
    """
    BatchJobConfig.from_dict(job_config)
    idx: int = job_config["index"]
    progress_dict[f"{idx}_start"] = time.time()
    try:
        progress_dict[idx] = "Waiting for LLM"

        # 1. Run LLM in ThreadPool
        log_memory_usage(f"Job {idx}: before LLM")
        future_llm = llm_executor.submit(llm_job_worker, job_config, progress_dict)
        success, script_text, err_msg = future_llm.result()

        if not success:
            progress_dict[idx] = f"Failed: {err_msg}"
            progress_dict[f"{idx}_end"] = time.time()
            return (idx, False, err_msg)

        job_config["script_text"] = script_text
        progress_dict[idx] = "Waiting for Compilation"
        log_memory_usage(f"Job {idx}: after LLM, before video")

        # 2. Run Video Generation in ProcessPool
        future_video = video_executor.submit(
            video_job_worker, job_config, progress_dict
        )
        result: Any = future_video.result()
        log_memory_usage(f"Job {idx}: video complete")
        return result

    except Exception as e:
        progress_dict[idx] = f"Failed: {str(e)}"
        progress_dict[f"{idx}_end"] = time.time()
        return (idx, False, str(e))


# --- Workers ---


def llm_job_worker(
    job_config: dict[str, Any], progress_dict: dict[Any, Any]
) -> tuple[bool, str | None, str | None]:
    """Generate a script for a batch job via the LLM API.

    Args:
        job_config: Job configuration dictionary.
        progress_dict: Shared progress dictionary for status updates.

    Returns:
        Tuple of ``(success, script_text, error_message)``.
    """
    idx: int = job_config["index"]
    progress_dict[f"{idx}_llm_worker_start"] = time.time()

    # If this is a retry and we already have a generated script, skip generation
    if job_config.get("script_text"):
        logger.info(
            "[Batch LLM #%d] Found existing script_text, skipping generation.", idx
        )
        progress_dict[idx] = "Reusing Script"
        return True, job_config["script_text"], None

    progress_dict[idx] = "LLM Script"
    logger.info(
        "[Batch LLM #%d] Starting script generation (model=%s, temp=%.2f)",
        idx,
        job_config.get("model", "?"),
        job_config.get("script_temp", 0.7),
    )
    try:
        from openai import OpenAI

        profiles: list[dict[str, Any]] = job_config["settings"].get("llm_profiles", [])
        active_id: str | None = job_config["settings"].get("active_llm_profile_id")
        active_profile: dict[str, Any] = {}
        for p in profiles:
            if p.get("id") == active_id:
                active_profile = p
                break
        if not active_profile and profiles:
            active_profile = profiles[0]

        api_key: str = active_profile.get("api_key") or os.environ.get(
            "OPENAI_API_KEY", ""
        )
        base_url: str = active_profile.get("base_url") or os.environ.get(
            "OPENAI_BASE_URL", ""
        )

        global _cached_llm_client, _cached_llm_api_key, _cached_llm_base_url

        client_key: str = f"{api_key}|{base_url}"
        if _cached_llm_client is None or client_key != f"{_cached_llm_api_key}|{_cached_llm_base_url}":
            _cached_llm_client = OpenAI(api_key=api_key, base_url=base_url, timeout=300.0)
            _cached_llm_api_key = api_key
            _cached_llm_base_url = base_url

        client: OpenAI = _cached_llm_client

        script_text: str = ""
        _last_ts: float = time.time()
        _last_wc: int = 0

        for attempt in range(LLM_RETRY_ATTEMPTS):
            try:
                # Send started event at the top of each attempt so the
                # frontend resets the stream on retry.
                stream_llm_event(idx, "llm_started")
                script_text = ""
                response = client.chat.completions.create(
                    model=job_config["model"],
                    messages=[
                        {
                            "role": "system",
                            "content": job_config["system_prompt"],
                        },
                        {"role": "user", "content": job_config["prompt"]},
                    ],
                    temperature=job_config["script_temp"],
                    stream=True,
                )
                script_text = ""
                _last_ts = time.time()
                _last_wc = 0
                _token_buf: str = ""          # accumulate deltas for batched send
                _token_buf_ts: float = time.time()
                for chunk in response:
                    if (
                        chunk.choices
                        and chunk.choices[0].delta
                        and chunk.choices[0].delta.content is not None
                    ):
                        delta: str = chunk.choices[0].delta.content
                        script_text += delta
                        _token_buf += delta
                        word_count: int = len(script_text.split())
                        now: float = time.time()
                        # Flush accumulated tokens every ~100ms to avoid
                        # flooding the asyncio event-loop pipe from this thread.
                        if (
                            len(_token_buf) >= 40
                            or now - _token_buf_ts >= 0.1
                        ):
                            stream_llm_token(idx, _token_buf, word_count)
                            _token_buf = ""
                            _token_buf_ts = now
                        if (
                            word_count - _last_wc >= STREAM_PROGRESS_WORD_INTERVAL
                            or now - _last_ts >= STREAM_PROGRESS_TIME_INTERVAL
                        ):
                            progress_dict[idx] = f"LLM Script ({word_count} words)"
                            _last_ts = now
                            _last_wc = word_count
                # Flush any remaining buffered tokens
                if _token_buf:
                    stream_llm_token(idx, _token_buf, len(script_text.split()))
                stream_llm_event(idx, "llm_completed", len(script_text.split()))
                break  # success — exit retry loop
            except Exception as e:
                err_str: str = str(e).lower()
                if any(k in err_str for k in STREAM_NON_RETRYABLE_KEYWORDS):
                    raise
                is_retryable: bool = isinstance(
                    e, (ConnectionError, TimeoutError)
                ) or any(w in err_str for w in STREAM_RETRYABLE_KEYWORDS)
                if not is_retryable or attempt == LLM_RETRY_ATTEMPTS - 1:
                    raise
                progress_dict[idx] = f"LLM Script (retry {attempt + 1}/{LLM_RETRY_ATTEMPTS})"
                time.sleep(1.0 * (2**attempt))

        script_text = script_text.strip()
        script_text, title, hashtags = parse_title_hashtags(script_text)

        # Generate safe output filename from title
        try:
            safe_title: str = (
                re.sub(r"[\s\-]+", "_", title.lower()) if title else BATCH_FILENAME_FALLBACK
            )
            safe_title = re.sub(r"[^\w_]", "", safe_title).strip("_")
            if not safe_title:
                safe_title = BATCH_FILENAME_FALLBACK

            orig_filename: str = job_config["output_filename"]
            timestamp_match = re.search(r"rendered_batch_(\d+)_", orig_filename)
            timestamp: str = (
                timestamp_match.group(1) if timestamp_match else str(int(time.time()))
            )

            new_filename: str = f"{safe_title}_{timestamp}_{idx}.mp4"
            job_config["output_filename"] = new_filename
            job_config["generated_title"] = title or TITLE_FALLBACK
            job_config["generated_hashtags"] = hashtags or HASHTAGS_FALLBACK
        except Exception:
            job_config["generated_title"] = TITLE_FALLBACK
            job_config["generated_hashtags"] = HASHTAGS_FALLBACK

        logger.info(
            "[Batch LLM #%d] Script done: %d words, title=%s",
            idx,
            len(script_text.split()),
            job_config.get("generated_title", "(none)"),
        )
        return True, script_text, None

    except Exception as e:
        logger.warning("[Batch LLM #%d] Failed: %s", idx, str(e))
        return False, None, str(e)


def video_job_worker(
    job_config: dict[str, Any],
    progress_dict: dict[Any, Any],
) -> tuple[int, bool, str]:
    """Run video compilation for a batch job.

    Args:
        job_config: Job configuration dictionary.
        progress_dict: Shared progress dictionary for status updates.

    Returns:
        Tuple of ``(idx, success, message_or_filename)``.
    """
    idx: int = job_config["index"]
    output_filename: str = job_config["output_filename"]
    logger.info("[Batch Video #%d] Starting compilation -> %s", idx, output_filename)

    # Resolve relative asset paths before loading into state
    resolved_bg_video: str | None = resolve_preset_path(job_config["bg_video_path"])
    resolved_bg_video_bottom: str | None = resolve_preset_path(
        job_config["bg_video_bottom_path"]
    )
    resolved_bg_music: str | None = resolve_preset_path(job_config["bg_music_path"])

    # Update process-local state and settings
    shared_state.state.clear()
    shared_state.state.update(
        {
            "script_text": job_config["script_text"],
            "selected_voice": job_config["voice_id"],
            "bg_video_path": resolved_bg_video,
            "bg_video_bottom_path": resolved_bg_video_bottom,
            "bg_music_path": resolved_bg_music,
            "music_volume": job_config["music_volume"],
            "voice_volume": job_config["voice_volume"],
            "sub_font": job_config["sub_font"],
            "sub_size": job_config["sub_size"],
            "sub_color": job_config["sub_color"],
            "sub_highlight": job_config["sub_highlight"],
            "sub_outline": job_config["sub_outline"],
            "sub_outline_width": job_config["sub_outline_width"],
            "sub_bold": job_config["sub_bold"],
            "enable_emojis": job_config["enable_emojis"],
            "enable_emoji_animation": job_config.get("enable_emoji_animation", True),
            "emoji_scale_factor": job_config.get("emoji_scale_factor", 1.5),
            "emoji_hold_duration": job_config.get("emoji_hold_duration", 0.5),
            "emoji_throw_max_count": job_config.get("emoji_throw_max_count", 3),
            "word_pop": job_config["word_pop"],
            "word_pop_scale": job_config["word_pop_scale"],
            "inactive_dim": job_config["inactive_dim"],
            "inactive_alpha": job_config["inactive_alpha"],
            "voice_speed": job_config.get("voice_speed", 1.0),
            "loaded_preset_name": "Randomized Batch Job",
            "generated_title": job_config.get("generated_title", TITLE_FALLBACK),
            "generated_hashtags": job_config.get("generated_hashtags", HASHTAGS_FALLBACK),
        }
    )

    shared_state.settings.clear()
    shared_state.settings.update(job_config["settings"])

    # Monkeypatch the config console for progress redirection
    progress_console: ProgressConsole = ProgressConsole(idx, progress_dict)
    console.print = progress_console.print  # type: ignore[assignment]
    console.clear = progress_console.clear  # type: ignore[assignment]

    log_memory_usage(f"Job {idx}: starting compilation")

    try:
        try:
            progress_dict[idx] = "Compiling"
        except (KeyError, BrokenPipeError, ConnectionRefusedError, OSError):
            logger.warning(
                "Batch job %d: failed to update progress (manager may have shut down)",
                idx,
                exc_info=True,
            )

        success: bool = retry_with_backoff(
            lambda: compile_video_flow(
                skip_confirm=True,
                custom_output_filename=output_filename,
                progress_callback=progress_console.print,
            )
        )
        if success:
            try:
                from gui.config import OUTPUT_DIR

                base_name: str = os.path.splitext(output_filename)[0]
                txt_path: str = os.path.join(OUTPUT_DIR, f"{base_name}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(f"{job_config.get('generated_title', TITLE_FALLBACK)}\n")
                    f.write(f"{job_config.get('generated_hashtags', HASHTAGS_FALLBACK)}\n\n")
                    f.write(f"Script:\n{job_config.get('script_text', '')}\n")
            except Exception:
                logger.warning(
                    "Batch job %d: failed to write metadata .txt "
                    "(manager may have shut down)",
                    idx,
                    exc_info=True,
                )

        if success:
            try:
                progress_dict[idx] = "Done"
                progress_dict[f"{idx}_end"] = time.time()
            except (KeyError, BrokenPipeError, ConnectionRefusedError, OSError):
                logger.warning(
                    "Batch job %d: failed to update progress "
                    "(manager may have shut down)",
                    idx,
                    exc_info=True,
                )
            return (idx, True, output_filename)
        else:
            try:
                progress_dict[idx] = "Failed"
                progress_dict[f"{idx}_end"] = time.time()
            except (KeyError, BrokenPipeError, ConnectionRefusedError, OSError):
                logger.warning(
                    "Batch job %d: failed to update progress "
                    "(manager may have shut down)",
                    idx,
                    exc_info=True,
                )
            return (idx, False, "Compilation failed (check logs/app.log)")
    except Exception as e:
        logger.error(
            "Batch job %d exception: %s\n%s",
            idx,
            e,
            traceback.format_exc(),
        )
        try:
            progress_dict[idx] = f"Failed: {str(e)}"
            progress_dict[f"{idx}_end"] = time.time()
        except (KeyError, BrokenPipeError, ConnectionRefusedError, OSError):
            logger.warning(
                "Batch job %d: failed to update progress "
                "(manager may have shut down)",
                idx,
                exc_info=True,
            )
        return (idx, False, str(e))
