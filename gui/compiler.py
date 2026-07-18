import concurrent.futures
import contextlib
import gc
import json
import os
import random
import re
import shutil
import time
import uuid

import nltk
import numpy as np
import questionary
import soundfile as sf
from openai import OpenAI

from generator import compile_video, generate_ass_subtitles, generate_voice, get_video_info
from gui.config import CACHE_DIR, OUTPUT_DIR, TEMP_DIR, VIDEOS_DIR, console, load_emoji_map, logger
from gui.state import settings, state
from gui.utils import discover_opencode_keys, get_active_llm_profile, resolve_preset_path

_WHISPER_MODEL = None
_WHISPER_MODEL_NAME = None


def _release_memory_to_os():
    gc.collect()
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
    except Exception:
        pass


def unload_whisper_model():
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME
    if _WHISPER_MODEL is not None:
        del _WHISPER_MODEL
        _WHISPER_MODEL = None
        _WHISPER_MODEL_NAME = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        _release_memory_to_os()
        logger.info("Whisper model unloaded from memory.")


def _process_chunk_worker(c_idx, chunk, total_chunks, job_id, voice, voice_speed):
    """
    Worker for parallel TTS generation. Generates audio for a single paragraph chunk.
    Using paragraph-level chunks (vs individual sentences) gives the TTS engine more context,
    resulting in more natural prosody and fewer unnatural pauses at boundaries.
    """
    console.print(
        f'[yellow]  → Generating voice for chunk {c_idx + 1}/{total_chunks}: "{chunk[:60]}{"..." if len(chunk) > 60 else ""}"[/]'
    )
    c_temp_audio_path = os.path.join(CACHE_DIR, f"c_temp_{job_id}_{c_idx}.wav")

    # 1. Voice Generation
    generate_voice(chunk, voice, c_temp_audio_path, default_speed=voice_speed)

    try:
        c_audio_data, c_sr = sf.read(c_temp_audio_path)
        return c_idx, c_audio_data, c_sr
    except Exception as e:
        logger.error(f"Failed to load generated audio array: {e}", exc_info=True)
        raise e
    finally:
        if os.path.exists(c_temp_audio_path):
            with contextlib.suppress(Exception):
                os.remove(c_temp_audio_path)


def compile_video_flow(
    skip_confirm=False, custom_output_filename=None, progress_callback=None, state_override=None
):
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME
    _t0 = time.time()
    current_state = state_override if state_override is not None else state
    from gui.batch import log_memory_usage  # noqa: E402  # inline to avoid circular import

    console.print("[bold yellow]5. COMPILE TIKTOK SHORT[/]")
    script = current_state["script_text"].strip()
    voice = current_state["selected_voice"]
    word_count = len(script.split()) if script else 0
    logger.info(
        "[Compiler] Starting compilation: voice=%s words=%d job_id=%s",
        voice,
        word_count,
        uuid.uuid4().hex[:8],
    )

    if not script:
        console.print("[red]Error: Script is empty. Please generate or edit a script first.[/]")
        return False

    if not current_state["bg_video_path"]:
        console.print(
            "[red]Error: No top/primary background video configured. Please configure it first.[/]"
        )
        return False

    # Resolve random selections
    video_files = []
    if os.path.exists(VIDEOS_DIR):
        video_files = [
            os.path.join(VIDEOS_DIR, f)
            for f in os.listdir(VIDEOS_DIR)
            if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi"))
            and "sound effect" not in f.lower()
            and "sfx" not in f.lower()
        ]

    # Filter out corrupt/invalid video files to avoid ffprobe cascading failures
    if video_files:
        valid_video_files = []
        for vf in video_files:
            try:
                info = get_video_info(vf, suppress_errors=True)
                if info and info.get("width", 0) > 0 and info.get("height", 0) > 0:
                    valid_video_files.append(vf)
                else:
                    logger.warning(f"Skipping corrupt/invalid video file: {os.path.basename(vf)}")
            except Exception:
                logger.warning(f"Skipping corrupt/invalid video file: {os.path.basename(vf)}")
        video_files = valid_video_files
        if not video_files:
            logger.error("All available background videos are corrupt or invalid.")

    resolved_top_path = resolve_preset_path(current_state["bg_video_path"])
    resolved_bottom_path = resolve_preset_path(current_state["bg_video_bottom_path"])
    resolved_music_path = resolve_preset_path(current_state["bg_music_path"])

    if resolved_top_path == "random":
        if not video_files:
            console.print(
                "[red]Error: No background videos found in videos/ folder to select from.[/]"
            )
            return False
        resolved_top_path = random.choice(video_files)
        console.print(f"[yellow]Resolved Top Video: {os.path.basename(resolved_top_path)}[/]")

    if resolved_bottom_path == "random":
        if not video_files:
            console.print(
                "[red]Error: No background videos found in videos/ folder to select from.[/]"
            )
            return False
        # Try to select a different video than the top video if possible
        remaining = [v for v in video_files if v != resolved_top_path]
        if remaining:
            resolved_bottom_path = random.choice(remaining)
        else:
            resolved_bottom_path = random.choice(video_files)
        console.print(f"[yellow]Resolved Bottom Video: {os.path.basename(resolved_bottom_path)}[/]")

    # Validate final paths
    if not resolved_top_path or not os.path.exists(resolved_top_path):
        console.print(f"[red]Error: Top background video file '{resolved_top_path}' not found.[/]")
        return False

    if current_state["bg_video_bottom_path"] and (
        not resolved_bottom_path or not os.path.exists(resolved_bottom_path)
    ):
        console.print(
            f"[red]Error: Bottom background video file '{resolved_bottom_path}' not found.[/]"
        )
        return False

    # Get settings values
    active_profile = get_active_llm_profile()
    api_key = active_profile.get("api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = active_profile.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    whisper_api_key = settings.get("whisper_api_key") or os.environ.get("WHISPER_API_KEY")
    whisper_base_url = settings.get("whisper_base_url") or os.environ.get("WHISPER_BASE_URL")
    use_local_whisper = settings.get("local_whisper", True)
    local_model_name = settings.get("local_whisper_model", "tiny")

    opencode_key, opencode_openai_token = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and not base_url:
            base_url = "https://opencode.ai/zen/go/v1"

    if not use_local_whisper and not api_key:
        console.print(
            "[red]Error: API Key is required to transcribe audio when local Whisper is disabled. Configure it in Settings.[/]"
        )
        return False

    if not skip_confirm:
        confirm = questionary.confirm(
            "Are you sure you want to compile the TikTok Short now?"
        ).ask()
        if not confirm:
            return False

    job_id = str(uuid.uuid4())
    audio_path = os.path.join(CACHE_DIR, f"audio_{job_id}.wav")
    subs_path = os.path.join(CACHE_DIR, f"subs_{job_id}.ass")
    if custom_output_filename:
        output_filename = custom_output_filename
    else:
        output_filename = f"rendered_{job_id}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    temp_output_path = os.path.join(TEMP_DIR, output_filename)

    try:
        # Load subtitle style settings
        sub_opts = {
            "font_name": current_state.get("sub_font") or settings.get("sub_font", "Arial"),
            "font_size": int(current_state.get("sub_size") or settings.get("sub_size", 72)),
            "primary_color": current_state.get("sub_color") or settings.get("sub_color", "#FFFFFF"),
            "highlight_color": current_state.get("sub_highlight")
            or settings.get("sub_highlight", "#00FFFF"),
            "outline_color": current_state.get("sub_outline")
            or settings.get("sub_outline", "#000000"),
            "outline_width": int(
                current_state.get("sub_outline_width")
                if current_state.get("sub_outline_width") is not None
                else settings.get("sub_outline_width", 5)
            ),
            "bold": current_state.get("sub_bold")
            if current_state.get("sub_bold") is not None
            else settings.get("sub_bold", True),
            "word_pop": current_state.get("word_pop")
            if current_state.get("word_pop") is not None
            else settings.get("word_pop", True),
            "word_pop_scale": float(
                current_state.get("word_pop_scale")
                if current_state.get("word_pop_scale") is not None
                else settings.get("word_pop_scale", 1.15)
            ),
            "inactive_dim": current_state.get("inactive_dim")
            if current_state.get("inactive_dim") is not None
            else settings.get("inactive_dim", True),
            "inactive_alpha": current_state.get("inactive_alpha")
            if current_state.get("inactive_alpha") is not None
            else settings.get("inactive_alpha", "88"),
            "enable_emojis": current_state.get("enable_emojis")
            if current_state.get("enable_emojis") is not None
            else settings.get("enable_emojis", True),
            "enable_color_emoji": current_state.get("enable_color_emoji")
            if current_state.get("enable_color_emoji") is not None
            else settings.get("enable_color_emoji", True),
            "emoji_position": current_state.get("emoji_position")
            or settings.get("emoji_position", "above"),
            "emoji_style": current_state.get("emoji_style") or settings.get("emoji_style", "apple"),
            "enable_emoji_animation": current_state.get("enable_emoji_animation")
            if current_state.get("enable_emoji_animation") is not None
            else settings.get("enable_emoji_animation", True),
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
            "words_per_screen": current_state.get("words_per_screen")
            or settings.get("words_per_screen", "3"),
        }

        if current_state["bg_video_bottom_path"]:
            # Stacked split screen: position subtitle centered in the bottom video
            sub_opts["alignment"] = 2
            sub_opts["margin_v"] = 440
        else:
            # Full screen: standard Alignment 5 (Middle center)
            sub_opts["alignment"] = 5
            sub_opts["margin_v"] = 10

        target_h = 1920 if (settings.get("render_resolution", "1080p") == "1080p") else 1280
        sub_opts["target_h"] = target_h

        # Load volume settings
        voice_vol = current_state["voice_volume"]
        if voice_vol is None:
            voice_vol = settings.get("voice_volume", 1.0)
        music_vol = current_state["music_volume"]
        if music_vol is None:
            music_vol = settings.get("music_volume", 0.15)

        voice_speed = current_state.get("voice_speed")
        if voice_speed is None:
            voice_speed = settings.get("voice_speed", 1.0)

        words = []

        # --- Phase 1: Split script into paragraph chunks for TTS ---
        # Paragraph-level splitting gives the TTS engine much more context per call, producing
        # more natural prosody with fewer audible seams between chunks.
        raw_chunks = [c.strip() for c in script.split("\n\n") if c.strip()]

        if not raw_chunks:
            # Fallback: single chunk
            raw_chunks = [script.strip()]
        elif len(raw_chunks) == 1:
            # No blank lines found — fall back to splitting by ~50-word groups at sentence boundaries
            # This handles legacy scripts or scripts where the AI didn't insert blank lines.
            try:
                nltk.data.find("tokenizers/punkt_tab")
            except LookupError:
                try:
                    nltk.download("punkt_tab", quiet=True)
                except Exception as e:
                    logger.error("Failed to download NLTK punkt_tab tokenizer: %s. Check your internet connection.", e)
                    raise RuntimeError(f"NLTK punkt_tab download failed: {e}") from e
            all_sents = [s.strip() for s in nltk.sent_tokenize(script) if s.strip()]
            fallback_chunks = []
            current_group = []
            current_word_count = 0
            for sent in all_sents:
                w_count = len(sent.split())
                if current_word_count + w_count > 50 and current_group:
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
                f"Fell back to ~50-word sentence grouping: {len(raw_chunks)} chunk(s)."
            )

        chunks = raw_chunks
        console.print(f"[yellow]→ Script split into {len(chunks)} voice chunk(s).[/]")

        audio_arrays = []
        sample_rate = 24000  # Kokoro TTS output sample rate

        # Setup Whisper client if using API
        w_client = None
        if not use_local_whisper:
            try:
                if whisper_api_key:
                    w_client = OpenAI(api_key=whisper_api_key, base_url=whisper_base_url)
                elif whisper_base_url:
                    w_client = OpenAI(api_key=api_key, base_url=whisper_base_url)
                elif base_url and "opencode.ai" in base_url:
                    w_key = opencode_openai_token or os.environ.get("OPENAI_API_KEY")
                    if w_key:
                        w_client = OpenAI(api_key=w_key, base_url="https://api.openai.com/v1")
                    else:
                        w_client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")
                elif api_key:
                    w_client = OpenAI(api_key=api_key, base_url=base_url)
            except Exception as e:
                logger.warning(f"Failed to initialize Whisper API client: {e}")

        # Phase 2: Generate voice for all chunks in parallel
        results = [None] * len(chunks)
        total_chunks = len(chunks)
        tts_workers = settings.get("max_workers") or 1
        try:
            tts_workers = min(int(tts_workers), max(1, (os.cpu_count() or 2) - 1))
        except (ValueError, TypeError):
            tts_workers = 1
        logger.info("[Compiler] Phase 1 — TTS: %d chunks, %d workers", total_chunks, tts_workers)
        _t_tts_start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=tts_workers) as executor:
            future_to_idx = {
                executor.submit(
                    _process_chunk_worker, i, c, total_chunks, job_id, voice, voice_speed
                ): i
                for i, c in enumerate(chunks)
            }
            errors = []
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    c_idx, c_audio_data, c_sr = future.result()
                    results[c_idx] = c_audio_data
                    sample_rate = c_sr
                except Exception as e:
                    errors.append((idx, e))
                    logger.error(f"Error generating voice for chunk {idx + 1}: {e}")
            if errors:
                raise RuntimeError(
                    f"Voice generation failed for {len(errors)} chunk(s): "
                    + "; ".join(f"chunk {i+1}: {e}" for i, e in errors[:3])
                )

        audio_arrays = results
        _t_tts_end = time.time()
        logger.info("[Compiler] Phase 1 — TTS done in %.1fs", _t_tts_end - _t_tts_start)

        # Unload TTS model now that generation is finished to save RAM
        from generator import unload_tts_model

        unload_tts_model()
        log_memory_usage("Video: after TTS generation")

        # Phase 3: Concatenate and Transcribe once
        if audio_arrays:
            try:
                concatenated_audio = np.concatenate(audio_arrays)
                sf.write(audio_path, concatenated_audio, sample_rate)
            except Exception as e:
                logger.error(f"Failed to concatenate and save audios: {e}", exc_info=True)
                raise e
        else:
            raise RuntimeError("No audio generated.")

        total_duration = len(concatenated_audio) / sample_rate
        console.print(f"[yellow]  → Transcribing full audio file ({total_duration:.1f}s)...[/]")

        del audio_arrays, concatenated_audio
        gc.collect()
        log_memory_usage("Video: after audio concatenation")

        transcribed = False

        logger.info(
            "[Compiler] Phase 2 — Transcription starting (%s), audio duration=%.1fs",
            "local faster-whisper"
            if (use_local_whisper or w_client is None)
            else "OpenAI Whisper API",
            total_duration,
        )
        if use_local_whisper or w_client is None:
            try:
                from faster_whisper import WhisperModel

                if _WHISPER_MODEL is None or local_model_name != _WHISPER_MODEL_NAME:
                    _WHISPER_MODEL = WhisperModel(
                        local_model_name, device="cpu", compute_type="int8"
                    )
                    _WHISPER_MODEL_NAME = local_model_name
                segments, info = _WHISPER_MODEL.transcribe(audio_path, word_timestamps=True)
                for segment in segments:
                    pct = min(99, int((segment.end / total_duration) * 100))
                    console.print(f"Transcribing audio... {pct}%")
                    if segment.words:
                        for w in segment.words:
                            words.append({"word": w.word, "start": w.start, "end": w.end})
                if words:
                    transcribed = True
            except Exception as e:
                logger.error(f"Local Whisper transcription failed: {e}", exc_info=True)

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
                    total_api = len(transcription.words)
                    for i, w in enumerate(transcription.words):
                        words.append(
                            {
                                "word": w.get("word")
                                if isinstance(w, dict)
                                else w.word,
                                "start": w.get("start")
                                if isinstance(w, dict)
                                else w.start,
                                "end": w.get("end") if isinstance(w, dict) else w.end,
                            }
                        )
                        if total_api > 1 and (i + 1) % max(1, total_api // 20) == 0:
                            pct = min(99, int(((i + 1) / total_api) * 100))
                            console.print(f"Transcribing audio... {pct}%")
                    transcribed = True
            except Exception as e:
                logger.error(f"Whisper API transcription failed: {e}", exc_info=True)

        if not transcribed and not use_local_whisper:
            try:
                from faster_whisper import WhisperModel

                if _WHISPER_MODEL is None or local_model_name != _WHISPER_MODEL_NAME:
                    _WHISPER_MODEL = WhisperModel(
                        local_model_name, device="cpu", compute_type="int8"
                    )
                    _WHISPER_MODEL_NAME = local_model_name
                segments, info = _WHISPER_MODEL.transcribe(audio_path, word_timestamps=True)
                for segment in segments:
                    pct = min(99, int((segment.end / total_duration) * 100))
                    console.print(f"Transcribing audio... {pct}%")
                    if segment.words:
                        for w in segment.words:
                            words.append({"word": w.word, "start": w.start, "end": w.end})
                if words:
                    transcribed = True
            except Exception as local_e:
                logger.error(f"Local Whisper fallback failed: {local_e}", exc_info=True)

        if not words:
            # Fallback to dummy timing
            duration = total_duration
            clean_sentence = re.sub(r"\[[^\]]+\]", "", script).strip()
            words = [{"word": clean_sentence, "start": 0.0, "end": duration}]

        audio_duration = words[-1]["end"] + 0.5
        logger.info(
            "[Compiler] Phase 2 — Transcription done: %d words, duration=%.2fs",
            len(words),
            audio_duration,
        )
        console.print(
            f"[green]Transcription complete: {len(words)} words. Duration: {audio_duration:.2f}s[/]"
        )

        unload_whisper_model()
        log_memory_usage("Video: after transcription")

        # 3. Create Styled Subtitles File
        console.print("[yellow][3/4] Generating ASS subtitle file with custom styling...[/]")
        # Pre-check Playwright/Chromium availability for color emoji rendering
        # Uses Python-level import check instead of shutil.which() to work reliably
        # in subprocess workers (e.g. ProcessPoolExecutor for batch jobs) where PATH
        # may not include the playwright CLI binary.
        if sub_opts.get("enable_color_emoji"):
            try:
                import importlib.util

                _chromium_ok = importlib.util.find_spec("playwright") is not None
            except Exception:
                _chromium_ok = False
            if not _chromium_ok:
                sub_opts["enable_color_emoji"] = False
                logger.warning(
                    "Playwright package found but Chromium browser may not be installed. Install with: python -m playwright install chromium"
                )
        generate_ass_subtitles(words, subs_path, style_opts=sub_opts, emoji_map=load_emoji_map())
        console.print("[green]ASS subtitles generated.[/]")

        del words
        log_memory_usage("Video: after subtitle generation")

        # Check for color emoji overlay manifest
        emoji_overlay_path = None
        if sub_opts.get("enable_color_emoji"):
            manifest_path = subs_path + ".emoji.json"
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path) as mf:
                        overlay_count = len(json.load(mf))
                    logger.info(
                        "Emoji overlay manifest found: %d overlays in %s",
                        overlay_count,
                        manifest_path,
                    )
                    emoji_overlay_path = manifest_path
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(
                        "Emoji manifest exists but unreadable at %s: %s", manifest_path, e
                    )
            else:
                logger.debug("No emoji overlay manifest — no word-to-emoji matches in script")

        # 4. Render video using FFmpeg
        console.print(
            "[yellow][4/4] Rendering vertical video using FFmpeg (cropping 9:16, mixing audio, burning subtitles)...[/]"
        )
        render_preset = settings.get("render_preset", "fast")
        render_res = settings.get("render_resolution", "1080p")
        video_encoder = settings.get("video_encoder", "libx265")
        logger.info(
            "[Compiler] Phase 4 — FFmpeg render: encoder=%s preset=%s res=%s top=%s bottom=%s emoji=%s",
            video_encoder,
            render_preset,
            render_res,
            os.path.basename(resolved_top_path),
            os.path.basename(resolved_bottom_path) if resolved_bottom_path else "(none)",
            os.path.basename(emoji_overlay_path) if emoji_overlay_path else "(none)",
        )
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
            emoji_overlay_path=emoji_overlay_path,
            emoji_style=sub_opts.get("emoji_style", "apple"),
        )

        shutil.move(temp_output_path, output_path)
        log_memory_usage("Video: after FFmpeg rendering")

        # Write .txt sidecar with title, hashtags and script
        try:
            base_name = os.path.splitext(output_filename)[0]
            txt_path = os.path.join(OUTPUT_DIR, f"{base_name}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"{current_state.get('generated_title', '')}\n")
                f.write(f"{current_state.get('generated_hashtags', '')}\n\n")
                f.write(f"Script:\n{script}\n")
        except Exception as e:
            logger.warning(f"Failed to write metadata .txt: {e}")

        # Generate thumbnail for gallery preview
        try:
            import subprocess

            thumb_dir = os.path.join(OUTPUT_DIR, "thumbnails")
            os.makedirs(thumb_dir, exist_ok=True)
            thumb_filename = os.path.splitext(output_filename)[0] + ".jpg"
            thumb_path = os.path.join(thumb_dir, thumb_filename)
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
            logger.info(f"Generated thumbnail: {thumb_filename}")
        except Exception as e:
            logger.warning(f"Thumbnail generation skipped (non-critical): {e}")

        _t1 = time.time()
        logger.info("[Compiler] ✅ Success in %.1fs — output/%s", _t1 - _t0, output_filename)
        console.print(f"\n[green]🎉 RENDER SUCCESSFUL! Saved to output/{output_filename}[/]\n")
        return True
    except Exception as e:
        logger.error(f"Video compilation failed for job '{job_id}': {e}", exc_info=True)
        console.print(f"[red]Video compilation failed: {str(e)}[/]")
        console.print("[yellow]Detailed error logs are available in logs/app.log[/]")
        if os.path.exists(temp_output_path):
            with contextlib.suppress(Exception):
                os.remove(temp_output_path)
        if os.path.exists(output_path):
            with contextlib.suppress(Exception):
                os.remove(output_path)
        return False
    finally:
        from generator import unload_tts_model

        unload_tts_model()
        unload_whisper_model()
        manifest_to_clean = subs_path + ".emoji.json"
        for p in [audio_path, subs_path, manifest_to_clean]:
            if os.path.exists(p):
                with contextlib.suppress(Exception):
                    os.remove(p)
