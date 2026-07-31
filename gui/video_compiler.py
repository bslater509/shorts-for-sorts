"""Video compilation logic — orchestrates TTS, transcription, subtitles, and FFmpeg rendering.

Extracted from ``batch.py`` to separate concerns.  Each compilation stage
has a dedicated helper function for testability and clarity.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import gc
import os
import random
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable
from typing import Any

import nltk
import numpy as np
import soundfile as sf
from openai import OpenAI

from generator.utils import _release_memory_to_os
from gui.assets_utils import list_video_files
from gui.config import CACHE_DIR, OUTPUT_DIR, TEMP_DIR, console, load_emoji_map, logger
from gui.progress_utils import log_memory_usage
from gui.state import settings, state
from gui.utils import get_active_llm_profile, resolve_preset_path

# --- Constants ---

TTS_CHUNK_MAX_WORDS: int = 50
"""Maximum words per grouped sentence chunk when no paragraph breaks exist."""

TTS_DEFAULT_SAMPLE_RATE: int = 24000
"""Default sample rate for TTS audio generation."""

TRANSCRIPTION_PROGRESS_STEPS: int = 20
"""Number of progress updates to emit during API transcription."""

TRANSCRIPTION_PROGRESS_PCT_CAP: int = 99
"""Maximum progress percentage before subtitles phase."""

AUDIO_DURATION_PADDING: float = 0.5
"""Seconds added to the last word end time for the output duration."""

FALLBACK_VOICE: str = "af_bella"
"""Default Kokoro voice used when the specified voice is unrecognised."""

SUBS_DIR_FALLBACK_MARGIN_V: int = 440
"""Bottom margin for split-screen subtitle alignment."""

SUBS_DEFAULT_MARGIN_V: int = 10
"""Bottom margin for full-screen subtitle alignment."""

SUBS_SPLIT_ALIGNMENT: int = 2
"""ASS text alignment for split-screen layout (2 = bottom-centre)."""

SUBS_FULL_ALIGNMENT: int = 5
"""ASS text alignment for full-screen layout (5 = centre)."""

MAX_WORKER_CORES_DIVISOR: int = 1
"""Reserved CPU cores for non-TTS work when computing max TTS workers."""

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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _process_chunk_worker(
    c_idx: int,
    chunk: str,
    total_chunks: int,
    job_id: str,
    voice: str,
    voice_speed: float,
) -> tuple[int, Any, int]:
    """Worker for parallel TTS generation — generates audio for one paragraph chunk.

    Args:
        c_idx: Chunk index (0-based).
        chunk: Text to synthesise.
        total_chunks: Total number of chunks (for logging).
        job_id: Unique job identifier for temp filenames.
        voice: Kokoro voice ID.
        voice_speed: Speech speed multiplier.

    Returns:
        Tuple of ``(chunk_index, audio_data, sample_rate)``.
    """
    console.print(
        f'[yellow]  → Generating voice for chunk {c_idx + 1}/{total_chunks}: '
        f'"{chunk[:60]}{"..." if len(chunk) > 60 else ""}"[/]'
    )
    c_temp_audio_path: str = os.path.join(
        CACHE_DIR, f"c_temp_{job_id}_{c_idx}.wav"
    )

    from generator import generate_voice

    generate_voice(chunk, voice, c_temp_audio_path, default_speed=voice_speed)

    try:
        c_audio_data, c_sr = sf.read(c_temp_audio_path)
        return c_idx, c_audio_data, c_sr
    except Exception as e:
        logger.error(
            "Failed to load generated audio array: %s", e, exc_info=True
        )
        raise e
    finally:
        if os.path.exists(c_temp_audio_path):
            with contextlib.suppress(Exception):
                os.remove(c_temp_audio_path)


def _resolve_background_videos(
    current_state: dict[str, Any],
    video_files: list[str],
) -> tuple[str | None, str | None, str | None]:
    """Resolve top/bottom/music paths, handle "random" selection, validate existence.

    Args:
        current_state: Session state dictionary with ``bg_video_path``,
            ``bg_video_bottom_path``, and ``bg_music_path``.
        video_files: List of available video file paths.

    Returns:
        Tuple of ``(resolved_top_path, resolved_bottom_path, resolved_music_path)``.

    Raises:
        RuntimeError: If no videos are available for random selection or
            a required path does not exist.
    """
    resolved_top_path: str | None = resolve_preset_path(
        current_state["bg_video_path"]
    )
    resolved_bottom_path: str | None = resolve_preset_path(
        current_state["bg_video_bottom_path"]
    )
    resolved_music_path: str | None = resolve_preset_path(
        current_state["bg_music_path"]
    )

    if resolved_top_path == "random":
        if not video_files:
            logger.error("No background videos found for random top video selection.")
            console.print(
                "[red]Error: No background videos found in videos/ folder to select from.[/]"
            )
            raise RuntimeError("No background videos available for random selection")
        resolved_top_path = random.choice(video_files)
        console.print(
            f"[yellow]Resolved Top Video: {os.path.basename(resolved_top_path)}[/]"
        )

    if resolved_bottom_path == "random":
        if not video_files:
            logger.error("No background videos found for random bottom video selection.")
            console.print(
                "[red]Error: No background videos found in videos/ folder to select from.[/]"
            )
            raise RuntimeError("No background videos available for random bottom selection")
        remaining = [v for v in video_files if v != resolved_top_path]
        resolved_bottom_path = random.choice(remaining) if remaining else random.choice(video_files)
        console.print(
            f"[yellow]Resolved Bottom Video: {os.path.basename(resolved_bottom_path)}[/]"
        )

    if not resolved_top_path or not os.path.exists(resolved_top_path):
        logger.error("Top background video file '%s' not found.", resolved_top_path)
        console.print(f"[red]Error: Top background video file '{resolved_top_path}' not found.[/]")
        raise RuntimeError(f"Top background video not found: {resolved_top_path}")

    if current_state["bg_video_bottom_path"] and (
        not resolved_bottom_path or not os.path.exists(resolved_bottom_path)
    ):
        logger.error("Bottom background video file '%s' not found.", resolved_bottom_path)
        console.print(f"[red]Error: Bottom background video file '{resolved_bottom_path}' not found.[/]")
        raise RuntimeError(f"Bottom background video not found: {resolved_bottom_path}")

    return resolved_top_path, resolved_bottom_path, resolved_music_path


def _load_subtitle_options(
    current_state: dict[str, Any]
) -> dict[str, Any]:
    """Load subtitle style settings with fallback to global settings.

    Args:
        current_state: Session state with per-job subtitle overrides.

    Returns:
        Subtitle options dict suitable for :func:`generator.generate_ass_subtitles`.
    """
    target_h: int = 1920 if (settings.get("render_resolution", "1080p") == "1080p") else 1280

    sub_opts: dict[str, Any] = {
        "font_name": (
            current_state.get("sub_font")
            if current_state.get("sub_font") is not None
            else settings.get("sub_font", "Arial")
        ),
        "font_size": int(
            current_state.get("sub_size")
            if current_state.get("sub_size") is not None
            else settings.get("sub_size", 72)
        ),
        "primary_color": (
            current_state.get("sub_color")
            if current_state.get("sub_color") is not None
            else settings.get("sub_color", "#FFFFFF")
        ),
        "highlight_color": (
            current_state.get("sub_highlight")
            if current_state.get("sub_highlight") is not None
            else settings.get("sub_highlight", "#00FFFF")
        ),
        "outline_color": (
            current_state.get("sub_outline")
            if current_state.get("sub_outline") is not None
            else settings.get("sub_outline", "#000000")
        ),
        "outline_width": int(
            current_state.get("sub_outline_width")
            if current_state.get("sub_outline_width") is not None
            else settings.get("sub_outline_width", 5)
        ),
        "bold": (
            current_state.get("sub_bold")
            if current_state.get("sub_bold") is not None
            else settings.get("sub_bold", True)
        ),
        "word_pop": (
            current_state.get("word_pop")
            if current_state.get("word_pop") is not None
            else settings.get("word_pop", True)
        ),
        "word_pop_scale": float(
            current_state.get("word_pop_scale")
            if current_state.get("word_pop_scale") is not None
            else settings.get("word_pop_scale", 1.15)
        ),
        "inactive_dim": (
            current_state.get("inactive_dim")
            if current_state.get("inactive_dim") is not None
            else settings.get("inactive_dim", True)
        ),
        "inactive_alpha": (
            current_state.get("inactive_alpha")
            if current_state.get("inactive_alpha") is not None
            else settings.get("inactive_alpha", "88")
        ),
        "enable_emojis": (
            current_state.get("enable_emojis")
            if current_state.get("enable_emojis") is not None
            else settings.get("enable_emojis", True)
        ),
        "emoji_position": (
            current_state.get("emoji_position")
            if current_state.get("emoji_position") is not None
            else settings.get("emoji_position", "above")
        ),
        "emoji_style": (
            current_state.get("emoji_style")
            if current_state.get("emoji_style") is not None
            else settings.get("emoji_style", "apple")
        ),
        "enable_emoji_animation": (
            current_state.get("enable_emoji_animation")
            if current_state.get("enable_emoji_animation") is not None
            else settings.get("enable_emoji_animation", True)
        ),
        "emoji_scale_factor": float(
            current_state.get("emoji_scale_factor")
            if current_state.get("emoji_scale_factor") is not None
            else settings.get("emoji_scale_factor", 1.5)
        ),
        "emoji_hold_duration": float(
            current_state.get("emoji_hold_duration")
            if current_state.get("emoji_hold_duration") is not None
            else settings.get("emoji_hold_duration", 0.5)
        ),
        "emoji_throw_max_count": int(
            current_state.get("emoji_throw_max_count")
            if current_state.get("emoji_throw_max_count") is not None
            else settings.get("emoji_throw_max_count", 1)
        ),
        "words_per_screen": (
            current_state.get("words_per_screen")
            if current_state.get("words_per_screen") is not None
            else settings.get("words_per_screen", "3")
        ),
    }

    if current_state.get("bg_video_bottom_path"):
        sub_opts["alignment"] = SUBS_SPLIT_ALIGNMENT
        sub_opts["margin_v"] = SUBS_DIR_FALLBACK_MARGIN_V
    else:
        sub_opts["alignment"] = SUBS_FULL_ALIGNMENT
        sub_opts["margin_v"] = SUBS_DEFAULT_MARGIN_V

    sub_opts["target_h"] = target_h
    return sub_opts


def _split_script_into_chunks(script: str) -> list[str]:
    """Split a script into TTS-friendly chunks.

    1.  Blank-line paragraphs -- each block becomes a chunk.
    2.  If only one paragraph exists, fall back to sentence-tokenisation
        with ~50-word groups.

    Args:
        script: The full script text.

    Returns:
        List of chunk strings.
    """
    raw_chunks: list[str] = [c.strip() for c in script.split("\n\n") if c.strip()]

    if not raw_chunks:
        raw_chunks = [script.strip()]
    elif len(raw_chunks) == 1:
        try:
            nltk.data.find("tokenizers/punkt_tab")
        except LookupError:
            logger.info("NLTK punkt_tab tokenizer not found. Downloading...")
            nltk.download("punkt_tab")
        all_sents: list[str] = [
            s.strip() for s in nltk.sent_tokenize(script) if s.strip()
        ]
        fallback_chunks: list[str] = []
        current_group: list[str] = []
        current_word_count: int = 0
        for sent in all_sents:
            w_count: int = len(sent.split())
            if current_word_count + w_count > TTS_CHUNK_MAX_WORDS and current_group:
                fallback_chunks.append(" ".join(current_group))
                current_group = [sent]
                current_word_count = w_count
            else:
                current_group.append(sent)
                current_word_count += w_count
        if current_group:
            fallback_chunks.append(" ".join(current_group))
        raw_chunks = fallback_chunks if fallback_chunks else [script.strip()]
        logger.info(
            "[Voice] No blank-line paragraph breaks found in script. "
            "Fell back to ~%d-word sentence grouping: %d chunk(s).",
            TTS_CHUNK_MAX_WORDS,
            len(raw_chunks),
        )

    return raw_chunks


def _run_tts_phase(
    chunks: list[str],
    voice: str,
    voice_speed: float,
    job_id: str,
) -> tuple[list[np.ndarray], int]:
    """Run parallel TTS generation for all chunks.

    Args:
        chunks: List of text chunks to synthesise.
        voice: Kokoro voice ID.
        voice_speed: Speech speed multiplier.
        job_id: Unique job identifier for temp files.

    Returns:
        Tuple of ``(audio_arrays_list, sample_rate)``.
    """
    results: list[np.ndarray | None] = [None] * len(chunks)
    total_chunks: int = len(chunks)
    sample_rate: int = TTS_DEFAULT_SAMPLE_RATE

    tts_workers_raw: str | int | None = settings.get("max_workers") or 1
    try:
        tts_workers: int = min(
            int(tts_workers_raw),
            max(1, (os.cpu_count() or 2) - MAX_WORKER_CORES_DIVISOR),
        )
    except (ValueError, TypeError):
        tts_workers = 1

    logger.info(
        "[Compiler] Phase 1 — TTS: %d chunks, %d workers",
        total_chunks,
        tts_workers,
    )
    _t_tts_start: float = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=tts_workers) as executor:
        future_to_idx = {
            executor.submit(
                _process_chunk_worker, i, c, total_chunks, job_id, voice, voice_speed
            ): i
            for i, c in enumerate(chunks)
        }
        errors: list[tuple[int, Exception]] = []
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                c_idx, c_audio_data, c_sr = future.result()
                results[c_idx] = c_audio_data
                sample_rate = c_sr
            except Exception as e:
                errors.append((idx, e))
                logger.error("Error generating voice for chunk %d: %s", idx + 1, e)
        if errors:
            raise RuntimeError(
                f"Voice generation failed for {len(errors)} chunk(s): "
                + "; ".join(f"chunk {i+1}: {e}" for i, e in errors[:3])
            )

    _t_tts_end = time.time()
    logger.info(
        "[Compiler] Phase 1 — TTS done in %.1fs", _t_tts_end - _t_tts_start
    )
    return results, sample_rate


def _concatenate_audio(
    audio_arrays: list[np.ndarray],
    sample_rate: int,
    audio_path: str,
) -> float:
    """Concatenate a list of audio arrays and write the result to disk.

    Args:
        audio_arrays: List of audio waveforms.
        sample_rate: Common sample rate for all arrays.
        audio_path: Destination WAV path.

    Returns:
        Total duration of the concatenated audio in seconds.
    """
    concatenated_audio: np.ndarray = np.concatenate(audio_arrays)
    sf.write(audio_path, concatenated_audio, sample_rate)
    total_duration: float = len(concatenated_audio) / sample_rate
    del audio_arrays, concatenated_audio
    gc.collect()
    log_memory_usage("Video: after audio concatenation")
    return total_duration


def _transcribe_audio(
    audio_path: str,
    total_duration: float,
    use_local_whisper: bool,
    w_client: OpenAI | None,
    local_model_name: str,
    script: str,
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

    Returns:
        Tuple of ``(words_list, transcribed_flag)`` where each word dict has
        ``"word"``, ``"start"``, and ``"end"`` keys.
    """
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME
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
            from faster_whisper import WhisperModel

            if _WHISPER_MODEL is None or local_model_name != _WHISPER_MODEL_NAME:
                _WHISPER_MODEL = WhisperModel(
                    local_model_name, device="auto", compute_type="default"
                )
                _WHISPER_MODEL_NAME = local_model_name
            segments, info = _WHISPER_MODEL.transcribe(
                audio_path, word_timestamps=True
            )
            for segment in segments:
                pct = min(TRANSCRIPTION_PROGRESS_PCT_CAP, int((segment.end / total_duration) * 100))
                console.print(f"Transcribing audio... {pct}%")
                if segment.words:
                    for w in segment.words:
                        words.append(
                            {"word": w.word, "start": w.start, "end": w.end}
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
            from faster_whisper import WhisperModel

            if _WHISPER_MODEL is None or local_model_name != _WHISPER_MODEL_NAME:
                _WHISPER_MODEL = WhisperModel(
                    local_model_name, device="auto", compute_type="default"
                )
                _WHISPER_MODEL_NAME = local_model_name
            segments, info = _WHISPER_MODEL.transcribe(
                audio_path, word_timestamps=True
            )
            for segment in segments:
                pct = min(TRANSCRIPTION_PROGRESS_PCT_CAP, int((segment.end / total_duration) * 100))
                console.print(f"Transcribing audio... {pct}%")
                if segment.words:
                    for w in segment.words:
                        words.append(
                            {"word": w.word, "start": w.start, "end": w.end}
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


def _generate_subtitles(
    words: list[dict[str, Any]],
    subs_path: str,
    sub_opts: dict[str, Any],
) -> None:
    """Generate an ASS subtitle file with custom styling.

    Args:
        words: List of word dicts with ``"word"``, ``"start"``, ``"end"``.
        subs_path: Destination path for the ASS file.
        sub_opts: Style options dict.
    """
    console.print(
        "[yellow][3/4] Generating ASS subtitle file with custom styling...[/]"
    )
    from generator import generate_ass_subtitles

    generate_ass_subtitles(
        words, subs_path, style_opts=sub_opts, emoji_map=load_emoji_map()
    )
    console.print("[green]ASS subtitles generated.[/]")
    del words
    log_memory_usage("Video: after subtitle generation")


def _render_ffmpeg(
    resolved_top_path: str,
    resolved_bottom_path: str | None,
    resolved_music_path: str | None,
    audio_path: str,
    subs_path: str,
    temp_output_path: str,
    audio_duration: float,
    voice_vol: float,
    music_vol: float,
    progress_callback: Callable[[float], None] | None,
) -> None:
    """Render the vertical video using FFmpeg (crop, mix, burn subtitles).

    Args:
        resolved_top_path: Path to the top background video.
        resolved_bottom_path: Optional path to the bottom background video.
        resolved_music_path: Optional path to background music.
        audio_path: Path to the mixed voiceover WAV.
        subs_path: Path to the ASS subtitle file.
        temp_output_path: Temporary output path before move.
        audio_duration: Duration of the audio track in seconds.
        voice_vol: Voiceover volume multiplier.
        music_vol: Background music volume multiplier.
        progress_callback: Optional progress callback (0–100%).
    """
    render_preset: str = settings.get("render_preset", "ultrafast")
    render_res: str = settings.get("render_resolution", "1080p")
    video_encoder: str = settings.get("video_encoder", "libx264")
    logger.info(
        "[Compiler] Phase 4 — FFmpeg render: encoder=%s preset=%s res=%s top=%s bottom=%s",
        video_encoder,
        render_preset,
        render_res,
        os.path.basename(resolved_top_path),
        os.path.basename(resolved_bottom_path) if resolved_bottom_path else "(none)",
    )
    from generator import compile_video

    compile_video(
        bg_video_path=resolved_top_path,
        audio_path=audio_path,
        subs_path=subs_path,
        output_path=temp_output_path,
        audio_duration=audio_duration,
        music_path=resolved_music_path,
        voice_volume=voice_vol,
        music_volume=music_vol,
        bg_video_bottom_path=resolved_bottom_path,
        render_preset=render_preset,
        render_resolution=render_res,
        video_encoder=video_encoder,
        progress_callback=progress_callback,
    )


def _save_metadata_and_thumbnail(
    output_path: str,
    output_filename: str,
    current_state: dict[str, Any],
    script: str,
    duration: float | None = None,
) -> None:
    """Save a metadata ``.txt`` file and generate a thumbnail for the output video.

    Non-critical: failures are logged as warnings but do not abort the pipeline.

    Args:
        output_path: The final rendered video path.
        output_filename: The base filename of the output.
        current_state: Session state with ``generated_title`` and ``generated_hashtags``.
        script: The original script text.
        duration: Optional video duration in seconds. When provided, a
            ``Duration: <seconds>`` line is written to the metadata sidecar so
            gallery loads can avoid an ffprobe round-trip.
    """
    try:
        base_name: str = os.path.splitext(output_filename)[0]
        txt_path: str = os.path.join(OUTPUT_DIR, f"{base_name}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"{current_state.get('generated_title', '')}\n")
            f.write(f"{current_state.get('generated_hashtags', '')}\n")
            if duration is not None:
                f.write(f"Duration: {duration:.2f}\n")
            f.write(f"\nScript:\n{script}\n")
    except Exception as e:
        logger.warning("Failed to write metadata .txt: %s", e)

    try:
        thumb_dir: str = os.path.join(OUTPUT_DIR, "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_filename: str = os.path.splitext(output_filename)[0] + ".jpg"
        thumb_path: str = os.path.join(thumb_dir, thumb_filename)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                output_path,
                "-ss",
                "00:00:02",
                "-vframes",
                "1",
                "-vf",
                "scale=480:-1",
                thumb_path,
            ],
            capture_output=True,
            check=True,
            timeout=15,
        )
        logger.info("Generated thumbnail: %s", thumb_filename)
    except Exception as e:
        logger.warning("Thumbnail generation skipped (non-critical): %s", e)


# ---------------------------------------------------------------------------
# Main compilation pipeline
# ---------------------------------------------------------------------------


def compile_video_flow(
    skip_confirm: bool = False,
    custom_output_filename: str | None = None,
    progress_callback: Callable[[float], None] | None = None,
    state_override: dict[str, Any] | None = None,
) -> bool:
    """Run the full video compilation pipeline.

    Stages:
        0.  Split script into TTS chunks.
        1.  Parallel TTS voice generation.
        1b. Concatenate audio.
        2.  Transcription (local faster-whisper or OpenAI API).
        3.  ASS subtitle generation.
        4.  FFmpeg rendering + metadata + thumbnail.

    Args:
        skip_confirm: Unused (kept for backward compatibility).
        custom_output_filename: Optional override for the output filename.
        progress_callback: Optional progress callback for FFmpeg rendering.
        state_override: Optional state dict override (for batch jobs).

    Returns:
        ``True`` on success.

    Raises:
        RuntimeError: If any stage fails irrecoverably.
    """
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME
    _t0: float = time.time()
    current_state: dict[str, Any] = (
        state_override if state_override is not None else state
    )

    console.print("[bold yellow]5. COMPILE TIKTOK SHORT[/]")
    script: str = current_state["script_text"].strip()
    voice: str = current_state["selected_voice"]

    from gui.state import VOICE_DISPLAY_TO_ID

    if voice not in VOICE_DISPLAY_TO_ID.values():
        resolved: str | None = VOICE_DISPLAY_TO_ID.get(voice)
        if resolved:
            logger.info(
                "[Compiler] Resolved voice display name '%s' → Kokoro ID '%s'",
                voice,
                resolved,
            )
            voice = resolved
        else:
            logger.warning(
                "[Compiler] Unknown voice '%s', falling back to %s",
                voice,
                FALLBACK_VOICE,
            )
            voice = FALLBACK_VOICE
    word_count: int = len(script.split()) if script else 0
    logger.info(
        "[Compiler] Starting compilation: voice=%s words=%d job_id=%s",
        voice,
        word_count,
        uuid.uuid4().hex[:8],
    )

    if not script:
        logger.error("Script is empty.")
        console.print(
            "[red]Error: Script is empty. Please generate or edit a script first.[/]"
        )
        raise RuntimeError("Script is empty — no text to compile")

    if not current_state.get("bg_video_path"):
        logger.error("No top/primary background video configured.")
        console.print(
            "[red]Error: No top/primary background video configured. "
            "Please configure it first.[/]"
        )
        raise RuntimeError("No background video configured")

    # List and validate background videos
    video_files: list[str] = list_video_files()
    if video_files:
        from generator import get_video_info

        valid_video_files: list[str] = []
        for vf in video_files:
            try:
                info = get_video_info(vf, suppress_errors=True)
                if info and info.get("width", 0) > 0 and info.get("height", 0) > 0:
                    valid_video_files.append(vf)
                else:
                    logger.warning(
                        "Skipping corrupt/invalid video file: %s",
                        os.path.basename(vf),
                    )
            except Exception:
                logger.warning(
                    "Skipping corrupt/invalid video file: %s",
                    os.path.basename(vf),
                )
        video_files = valid_video_files
        if not video_files:
            logger.error("All available background videos are corrupt or invalid.")

    resolved_top_path, resolved_bottom_path, resolved_music_path = (
        _resolve_background_videos(current_state, video_files)
    )

    # API / Whisper configuration
    active_profile: dict[str, Any] = get_active_llm_profile()
    api_key: str = (
        active_profile.get("api_key") or os.environ.get("OPENAI_API_KEY", "")
    )
    base_url: str = (
        active_profile.get("base_url") or os.environ.get("OPENAI_BASE_URL", "")
    )
    whisper_api_key: str = (
        settings.get("whisper_api_key") or os.environ.get("WHISPER_API_KEY", "")
    )
    whisper_base_url: str = (
        settings.get("whisper_base_url") or os.environ.get("WHISPER_BASE_URL", "")
    )
    use_local_whisper: bool = settings.get("local_whisper", True)
    local_model_name: str = settings.get("local_whisper_model", "tiny")

    if not use_local_whisper and not api_key:
        logger.error("API Key required for transcription when local Whisper is disabled.")
        console.print(
            "[red]Error: API Key is required to transcribe audio when local Whisper "
            "is disabled. Configure it in Settings.[/]"
        )
        raise RuntimeError("API key required for transcription (local Whisper disabled)")

    # Job paths
    job_id: str = str(uuid.uuid4())
    audio_path: str = os.path.join(CACHE_DIR, f"audio_{job_id}.wav")
    subs_path: str = os.path.join(CACHE_DIR, f"subs_{job_id}.ass")
    output_filename: str = (
        custom_output_filename
        if custom_output_filename
        else f"rendered_{job_id}.mp4"
    )
    output_path: str = os.path.join(OUTPUT_DIR, output_filename)
    temp_output_path: str = os.path.join(TEMP_DIR, output_filename)

    try:
        sub_opts = _load_subtitle_options(current_state)

        voice_vol: float = current_state.get("voice_volume") or settings.get(
            "voice_volume", 1.0
        )
        music_vol: float = current_state.get("music_volume") or settings.get(
            "music_volume", 0.15
        )
        voice_speed: float = current_state.get("voice_speed") or settings.get(
            "voice_speed", 1.0
        )

        # Phase 0: Split script into TTS chunks
        chunks: list[str] = _split_script_into_chunks(script)
        console.print(
            f"[yellow]→ Script split into {len(chunks)} voice chunk(s).[/]"
        )

        # Whisper API client setup
        w_client: OpenAI | None = None
        if not use_local_whisper:
            try:
                if whisper_api_key:
                    w_client = OpenAI(
                        api_key=whisper_api_key, base_url=whisper_base_url
                    )
                elif whisper_base_url:
                    w_client = OpenAI(api_key=api_key, base_url=whisper_base_url)
                elif api_key:
                    w_client = OpenAI(api_key=api_key, base_url=base_url)
            except Exception as e:
                logger.warning(
                    "Failed to initialise Whisper API client: %s", e
                )

        # Phase 1: Parallel TTS generation
        audio_arrays, sample_rate = _run_tts_phase(
            chunks, voice, voice_speed, job_id
        )

        from generator import unload_tts_model

        unload_tts_model()
        log_memory_usage("Video: after TTS generation")

        # Phase 1b: Concatenate audio
        if not audio_arrays:
            raise RuntimeError("No audio generated.")
        total_duration = _concatenate_audio(audio_arrays, sample_rate, audio_path)
        console.print(
            f"[yellow]  → Transcribing full audio file ({total_duration:.1f}s)...[/]"
        )

        # Phase 2: Transcription
        words, _transcribed = _transcribe_audio(
            audio_path,
            total_duration,
            use_local_whisper,
            w_client,
            local_model_name,
            script,
        )
        audio_duration: float = words[-1]["end"] + AUDIO_DURATION_PADDING
        logger.info(
            "[Compiler] Phase 2 — Transcription done: %d words, duration=%.2fs",
            len(words),
            audio_duration,
        )
        console.print(
            f"[green]Transcription complete: {len(words)} words. "
            f"Duration: {audio_duration:.2f}s[/]"
        )

        unload_whisper_model()
        log_memory_usage("Video: after transcription")

        # Phase 3: Subtitle generation
        _generate_subtitles(words, subs_path, sub_opts)

        # Phase 4: FFmpeg render
        console.print(
            "[yellow][4/4] Rendering vertical video using FFmpeg "
            "(cropping 9:16, mixing audio, burning subtitles)...[/]"
        )
        _render_ffmpeg(
            resolved_top_path,
            resolved_bottom_path,
            resolved_music_path,
            audio_path,
            subs_path,
            temp_output_path,
            audio_duration,
            voice_vol,
            music_vol,
            progress_callback,
        )

        shutil.move(temp_output_path, output_path)
        log_memory_usage("Video: after FFmpeg rendering")

        # Metadata + thumbnail
        _save_metadata_and_thumbnail(
            output_path, output_filename, current_state, script, duration=audio_duration
        )

        _t1 = time.time()
        logger.info(
            "[Compiler] ✅ Success in %.1fs — output/%s",
            _t1 - _t0,
            output_filename,
        )
        console.print(
            f"\n[green]🎉 RENDER SUCCESSFUL! Saved to output/{output_filename}[/]\n"
        )
        return True
    except Exception as e:
        logger.error(
            "Video compilation failed for job '%s': %s", job_id, e, exc_info=True
        )
        console.print(f"[red]Video compilation failed: {str(e)}[/]")
        console.print(
            "[yellow]Detailed error logs are available in logs/app.log[/]"
        )
        if os.path.exists(temp_output_path):
            with contextlib.suppress(Exception):
                os.remove(temp_output_path)
        if os.path.exists(output_path):
            with contextlib.suppress(Exception):
                os.remove(output_path)
        raise RuntimeError(str(e)) from e
    finally:
        from generator import unload_tts_model

        unload_tts_model()
        unload_whisper_model()
        for p in [audio_path, subs_path]:
            if os.path.exists(p):
                with contextlib.suppress(Exception):
                    os.remove(p)
