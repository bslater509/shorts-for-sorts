"""Whisper transcription logic (local faster-whisper + OpenAI API).

Extracted from ``gui/video_compiler.py`` to keep the compilation module focused
on orchestration.  Owns the module-level faster-whisper model cache and the
local → API → local-fallback transcription chain.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from openai import OpenAI

from generator.utils import _release_memory_to_os
from gui.config import console, logger
from gui.exceptions import BatchCancelledError

# --- Constants ---

TRANSCRIPTION_PROGRESS_STEPS: int = 20
"""Number of progress updates to emit during API transcription."""

TRANSCRIPTION_PROGRESS_PCT_CAP: int = 99
"""Maximum progress percentage before subtitles phase."""

# --- Module-level shared Whisper model ---

_WHISPER_MODEL = None
_WHISPER_MODEL_NAME: str | None = None


def unload_whisper_model() -> None:
    """Unload the cached Whisper model from memory."""
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME
    if _WHISPER_MODEL is not None:
        del _WHISPER_MODEL
        _WHISPER_MODEL = None
        _WHISPER_MODEL_NAME = None
        _release_memory_to_os()
        logger.info("Whisper model unloaded from memory.")


def _get_whisper_model(
    local_model_name: str,
    abort_check: Callable[[], bool] | None = None,
):
    """Return the cached faster-whisper model, loading it if needed.

    The model is cached module-level and only reloaded when the requested
    model name changes.  Loading waits for available memory and silences
    ctranslate2's chatty log output.
    """
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME
    if _WHISPER_MODEL is None or local_model_name != _WHISPER_MODEL_NAME:
        from gui.progress_utils import wait_for_available_memory

        wait_for_available_memory(threshold_mb=2500, abort_check=abort_check)

        import logging

        import ctranslate2

        ctranslate2.set_log_level(logging.ERROR)

        from faster_whisper import WhisperModel

        _WHISPER_MODEL = WhisperModel(
            local_model_name, device="auto", compute_type="int8"
        )
        _WHISPER_MODEL_NAME = local_model_name
    return _WHISPER_MODEL


def _transcribe_via_faster_whisper(
    audio_path: str,
    total_duration: float,
    local_model_name: str,
    abort_check: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """Transcribe ``audio_path`` with local faster-whisper word timestamps.

    Emits progress via :data:`TRANSCRIPTION_PROGRESS_PCT_CAP`-capped segment
    progress prints.  Returns word dicts with ``"word"``/``"start"``/``"end"``
    keys.

    Raises:
        BatchCancelledError: If ``abort_check`` signals a cancellation.
    """
    model = _get_whisper_model(local_model_name, abort_check)
    segments, _info = model.transcribe(audio_path, word_timestamps=True)
    words: list[dict[str, Any]] = []
    for segment in segments:
        if abort_check is not None and abort_check():
            raise BatchCancelledError("Batch cancelled: transcription interrupted")
        pct = min(
            TRANSCRIPTION_PROGRESS_PCT_CAP,
            int((segment.end / total_duration) * 100),
        )
        console.print(f"Transcribing audio... {pct}%")
        if segment.words:
            for w in segment.words:
                words.append(
                    {"word": w.word, "start": w.start, "end": w.end}
                )
    return words


def transcribe_audio(
    audio_path: str,
    total_duration: float,
    use_local_whisper: bool,
    w_client: OpenAI | None,
    local_model_name: str,
    script: str,
    abort_check: Callable[[], bool] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Transcribe audio using local faster-whisper or the OpenAI Whisper API.

    Falls back from API to local Whisper if configured.

    Args:
        audio_path: Path to the audio WAV file.
        total_duration: Audio duration in seconds (for progress estimation).
        use_local_whisper: If ``True``, prefer local faster-whisper.
        w_client: Optional OpenAI client for API-based transcription.
        local_model_name: faster-whisper model size name.
        script: Original script text (used as fallback if transcription yields no words).
        abort_check: Optional zero-argument callable returning ``True`` when the
            pipeline should be aborted.

    Returns:
        Tuple of ``(words_list, transcribed_flag)`` where each word dict has
        ``"word"``, ``"start"``, and ``"end"`` keys.
    """
    words: list[dict[str, Any]] = []
    transcribed: bool = False

    logger.info(
        "[Compiler] Phase 2 — Transcription starting (%s), audio duration=%.1fs",
        "local faster-whisper" if (use_local_whisper or w_client is None) else "OpenAI Whisper API",
        total_duration,
    )

    # Attempt 1: local faster-whisper
    if use_local_whisper or w_client is None:
        try:
            words = _transcribe_via_faster_whisper(
                audio_path, total_duration, local_model_name, abort_check
            )
            if words:
                transcribed = True
        except Exception as e:
            logger.error(
                "Local Whisper transcription failed: %s", e, exc_info=True
            )

    # Attempt 2: OpenAI Whisper API
    if not transcribed and w_client is not None:
        try:
            console.print("Transcribing audio... (API)")
            with open(audio_path, "rb") as f:
                transcription = w_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["word"],
                )
            if hasattr(transcription, "words") and transcription.words:
                total_api: int = len(transcription.words)
                for i, w in enumerate(transcription.words):
                    if abort_check is not None and abort_check():
                        raise BatchCancelledError("Batch cancelled: transcription interrupted")
                    word_data: dict[str, Any] = {
                        "word": w.get("word") if isinstance(w, dict) else w.word,
                        "start": w.get("start") if isinstance(w, dict) else w.start,
                        "end": w.get("end") if isinstance(w, dict) else w.end,
                    }
                    words.append(word_data)
                    if total_api > 1 and (i + 1) % max(1, total_api // TRANSCRIPTION_PROGRESS_STEPS) == 0:
                        pct = min(
                            TRANSCRIPTION_PROGRESS_PCT_CAP,
                            int(((i + 1) / total_api) * 100),
                        )
                        console.print(f"Transcribing audio... {pct}%")
                transcribed = True
        except Exception as e:
            logger.error(
                "Whisper API transcription failed: %s", e, exc_info=True
            )

    # Attempt 3: fallback local Whisper if API was requested but failed
    if not transcribed and not use_local_whisper:
        try:
            words = _transcribe_via_faster_whisper(
                audio_path, total_duration, local_model_name, abort_check
            )
            if words:
                transcribed = True
        except Exception as local_e:
            logger.error(
                "Local Whisper fallback failed: %s", local_e, exc_info=True
            )

    # Ultimate fallback: use the script text as a single word
    if not words:
        duration: float = total_duration
        clean_sentence: str = re.sub(r"\[[^\]]+\]", "", script).strip()
        words = [{"word": clean_sentence, "start": 0.0, "end": duration}]

    return words, transcribed
