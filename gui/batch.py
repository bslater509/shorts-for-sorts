import concurrent.futures
import contextlib
import gc
import os
import random
import re
import shutil
import subprocess
import time
import traceback
import uuid
from dataclasses import dataclass, fields

import nltk
import numpy as np
import psutil
import soundfile as sf
from openai import OpenAI
from rich.table import Table

from gui import state as shared_state
from gui.config import CACHE_DIR, OUTPUT_DIR, TEMP_DIR, VIDEOS_DIR, console, load_emoji_map, logger
from gui.state import settings, state
from gui.utils import get_active_llm_profile, resolve_preset_path

# Shared whisper model for batch compilation workers
_WHISPER_MODEL = None
_WHISPER_MODEL_NAME = None


def log_memory_usage(stage: str):
    proc = psutil.Process()
    rss_mb = proc.memory_info().rss / 1024 / 1024
    mem = psutil.virtual_memory()
    logger.info(
        f"[Batch Memory] {stage}: RSS={rss_mb:.0f}MB | "
        f"Avail={mem.available / 1024 / 1024:.0f}MB / "
        f"{mem.total / 1024 / 1024:.0f}MB ({mem.percent}%)"
    )


@dataclass
class BatchJobConfig:
    # Required fields (no defaults)
    index: int
    prompt: str
    voice_id: str
    bg_video_path: str
    output_filename: str
    settings: dict

    # Optional fields (with defaults)
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
    emoji_style: str = "Symbola"
    sub_animation_style: str = "tiktok_pop"
    script_temp: float = 0.7
    meta_temp: float = 0.7
    model: str = "gpt-4o-mini"
    system_prompt: str = ""
    generated_title: str | None = None
    generated_hashtags: str | None = None
    script_text: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "BatchJobConfig":
        valid_fields = {f.name for f in fields(cls)}
        kwargs = {k: data[k] for k in data if k in valid_fields}
        return cls(**kwargs)


class ProgressConsole:
    def __init__(self, idx, p_dict):
        self.idx = idx
        self.p_dict = p_dict

    def print(self, *args, **kwargs):
        msg = " ".join(str(a) for a in args)
        # Direct float/numeric progress callback (e.g., FFmpeg progress percentage)
        try:
            pct = float(msg)
            self.p_dict[self.idx] = f"FFmpeg Rendering ({pct:.1f}%)"
            return
        except (TypeError, ValueError):
            pass
        try:
            if "Generating voice for sentence" in msg or "Generating voice for chunk" in msg:
                # Record phase entry timestamp (first time only)
                phase_key = f"{self.idx}_phase_voice_start"
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
            elif "ℹ️ Found cached" in msg:
                self.p_dict[self.idx] = "Reusing Cache (Voice)"
        except Exception:
            logger.debug(
                "ProgressConsole.print exception for idx=%d", self.idx, exc_info=True
            )

    def clear(self):
        pass


def get_progress_percentage(status):
    if status == "Queued":
        return 0
    elif status == "Waiting for LLM":
        return 5
    elif status.startswith("LLM Script"):
        match = re.search(r"\((\d+)\s*words\)", status)
        if match:
            word_count = int(match.group(1))
            pct = min(14, 5 + int((word_count / 400) * 9))
            return pct
        return 10
    elif status == "LLM Metadata":
        return 15
    elif status == "Waiting for Compilation":
        return 20
    elif status.startswith("Voice Generation"):
        match = re.search(r"\((\d+)/(\d+)\)", status)
        if match:
            s_idx = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                return 20 + int((s_idx / total) * 25)
        return 30
    elif status == "Reusing Cache (Voice)":
        return 45
    elif status == "Compiling":
        return 28
    elif status.startswith("Transcription"):
        match = re.search(r"\((\d+)%\)", status)
        if match:
            pct = int(match.group(1))
            return 45 + int((pct / 100) * 10)
        return 48
    elif status == "Subtitles":
        return 55
    elif status.startswith("FFmpeg Rendering"):
        match = re.search(r"\((\d+\.?\d*)%\)", status)
        if match:
            pct = float(match.group(1))
            return 55 + int((pct / 100) * 45)
        return 75
    elif status == "Done":
        return 100
    elif status.startswith("Failed"):
        return None
    return 0


def make_progress_bar(percentage, status, width=15):
    filled = int(width * percentage / 100)
    filled = max(0, min(width, filled))
    empty = width - filled

    if status == "Done":
        bar_color = "green"
        pct_color = "green"
        desc = "[bold green]✓ Done[/]"
    elif status == "Queued":
        bar_color = "grey37"
        pct_color = "grey37"
        desc = "[dim]Queued...[/]"
    else:
        bar_color = "cyan"
        pct_color = "yellow"
        desc = f"[bold yellow]🔄 {status}...[/]"

    bar = f"[{bar_color}]" + "█" * filled + f"[/{bar_color}][grey37]" + "░" * empty + "[/grey37]"
    return f"{bar} [{pct_color}]{percentage:3d}%[/{pct_color}] {desc}"


def format_elapsed(duration):
    total_seconds = int(duration) if duration >= 0 else 0
    m = total_seconds // 60
    s = total_seconds % 60
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def display_progress_table(progress_dict, total_shorts, job_details):
    table = Table(
        title="[bold magenta]Concurrent Batch Generation Progress[/bold magenta]",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Short #", justify="center", style="dim", width=8)
    table.add_column("Category & Topic", justify="left")
    table.add_column("Voice & Layout", justify="left")
    table.add_column("Status / Progress", justify="left")
    table.add_column("Elapsed", justify="center", style="dim", width=12)

    for idx in range(1, total_shorts + 1):
        details = job_details.get(idx, {})
        topic = details.get("topic", "Unknown")
        voice_layout = f"{details.get('voice', 'Unknown')} | {details.get('layout', 'Unknown')}"
        status = progress_dict.get(idx, "Queued")

        # Calculate elapsed time
        start_time = progress_dict.get(f"{idx}_start")
        end_time = progress_dict.get(f"{idx}_end")

        elapsed_str = "--"
        if start_time:
            if end_time:
                duration = end_time - start_time
                elapsed_str = (
                    f"{format_elapsed(duration)} (Done)"
                    if status == "Done"
                    else format_elapsed(duration)
                )
            else:
                duration = time.time() - start_time
                elapsed_str = format_elapsed(duration)

        # Calculate percentage
        pct = get_progress_percentage(status)

        if pct is None:
            status_str = f"[bold red]✗ {status}[/]"
        else:
            status_str = make_progress_bar(pct, status)

        table.add_row(f"#{idx}", topic, voice_layout, status_str, elapsed_str)

    return table


def orchestrate_batch_job(job_config, progress_dict, llm_executor, video_executor):
    # Validate job config early to catch missing required keys
    BatchJobConfig.from_dict(job_config)
    idx = job_config["index"]
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
        future_video = video_executor.submit(video_job_worker, job_config, progress_dict)
        result = future_video.result()
        log_memory_usage(f"Job {idx}: video complete")
        return result

    except Exception as e:
        progress_dict[idx] = f"Failed: {str(e)}"
        progress_dict[f"{idx}_end"] = time.time()
        return (idx, False, str(e))


def retry_with_backoff(func, max_attempts=3, base_delay=1.0):
    """Retry a callable on transient errors with exponential backoff.
    Retries on ConnectionError, Timeout, and exceptions mentioning
    rate/timeout/connection/overloaded.  Does NOT retry on bad request
    or auth errors (those are configuration problems).
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            err_str = str(e).lower()
            # Never retry bad-request / auth errors
            if (
                "bad request" in err_str
                or "auth" in err_str
                or "unauthorized" in err_str
                or "401" in err_str
                or "403" in err_str
            ):
                raise
            is_retryable = isinstance(e, (ConnectionError, TimeoutError)) or any(
                w in err_str for w in ["rate", "timeout", "connection", "overloaded", "api_error"]
            )
            if not is_retryable or attempt == max_attempts - 1:
                raise
            delay = base_delay * (2**attempt)
            time.sleep(delay)


def parse_title_hashtags(script_text: str) -> tuple:
    """Extract TITLE/HASHTAGS lines from LLM output, case-insensitive.
    Returns (cleaned_script, title, hashtags).
    """
    title = ""
    hashtags = ""
    cleaned_lines = []
    for line in script_text.split("\n"):
        m_title = re.match(r"^title\s*:\s*(.*)", line, re.I)
        m_h_tags = re.match(r"^hashtags?\s*:\s*(.*)", line, re.I)
        if m_title:
            title = m_title.group(1).strip()
        elif m_h_tags:
            hashtags = m_h_tags.group(1).strip()
        else:
            cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines).strip()

    if not title:
        words = cleaned.split()
        title = " ".join(words[:8]) if words else ""

    return cleaned, title, hashtags


def generate_title_hashtags(
    script_text: str, client, model: str, temperature: float = 0.7
) -> tuple:
    """Generate title and hashtags from a finished script via a dedicated LLM call.
    Always uses a second call — never expects TITLE/HASHTAGS in the first response.
    Returns (title, hashtags).
    """
    prompt = (
        "Based on the following short-form video script, "
        "generate a catchy title (under 5 words) "
        "and 5 trending, relevant hashtags.\n\n"
        "Script:\n" + script_text + "\n\n"
        "Respond with exactly:\n"
        "TITLE: <title>\nHASHTAGS: <5 hashtags>"
    )
    try:
        response = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}], temperature=temperature
        )
        reply = (response.choices[0].message.content or "").strip()
        _, title, hashtags = parse_title_hashtags(reply)
    except Exception:
        logger.warning("Title/hashtag LLM call failed; falling back")
        title = ""
        hashtags = ""

    if not title:
        words = script_text.split()
        title = " ".join(words[:8]) if words else ""

    return title, hashtags


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
    """Worker for parallel TTS generation. Generates audio for a single paragraph chunk."""
    console.print(
        f'[yellow]  → Generating voice for chunk {c_idx + 1}/{total_chunks}: "{chunk[:60]}{"..." if len(chunk) > 60 else ""}"[/]'
    )
    c_temp_audio_path = os.path.join(CACHE_DIR, f"c_temp_{job_id}_{c_idx}.wav")

    from generator import generate_voice

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

    console.print("[bold yellow]5. COMPILE TIKTOK SHORT[/]")
    script = current_state["script_text"].strip()
    voice = current_state["selected_voice"]

    from gui.state import VOICE_DISPLAY_TO_ID
    if voice not in VOICE_DISPLAY_TO_ID.values():
        resolved = VOICE_DISPLAY_TO_ID.get(voice)
        if resolved:
            logger.info("[Compiler] Resolved voice display name '%s' → Kokoro ID '%s'", voice, resolved)
            voice = resolved
        else:
            logger.warning("[Compiler] Unknown voice '%s', falling back to af_bella", voice)
            voice = "af_bella"
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

    video_files = []
    if os.path.exists(VIDEOS_DIR):
        video_files = [
            os.path.join(VIDEOS_DIR, f)
            for f in os.listdir(VIDEOS_DIR)
            if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi"))
            and "sound effect" not in f.lower()
            and "sfx" not in f.lower()
        ]

    from generator import get_video_info

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
        remaining = [v for v in video_files if v != resolved_top_path]
        if remaining:
            resolved_bottom_path = random.choice(remaining)
        else:
            resolved_bottom_path = random.choice(video_files)
        console.print(f"[yellow]Resolved Bottom Video: {os.path.basename(resolved_bottom_path)}[/]")

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

    active_profile = get_active_llm_profile()
    api_key = active_profile.get("api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = active_profile.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    whisper_api_key = settings.get("whisper_api_key") or os.environ.get("WHISPER_API_KEY")
    whisper_base_url = settings.get("whisper_base_url") or os.environ.get("WHISPER_BASE_URL")
    use_local_whisper = settings.get("local_whisper", True)
    local_model_name = settings.get("local_whisper_model", "tiny")

    if not use_local_whisper and not api_key:
        console.print(
            "[red]Error: API Key is required to transcribe audio when local Whisper is disabled. Configure it in Settings.[/]"
        )
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
            "font_name": current_state.get("sub_font") if current_state.get("sub_font") is not None else settings.get("sub_font", "Arial"),
            "font_size": int(current_state.get("sub_size") if current_state.get("sub_size") is not None else settings.get("sub_size", 72)),
            "primary_color": current_state.get("sub_color") if current_state.get("sub_color") is not None else settings.get("sub_color", "#FFFFFF"),
            "highlight_color": current_state.get("sub_highlight") if current_state.get("sub_highlight") is not None else settings.get("sub_highlight", "#00FFFF"),
            "outline_color": current_state.get("sub_outline") if current_state.get("sub_outline") is not None else settings.get("sub_outline", "#000000"),
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
            "emoji_position": current_state.get("emoji_position") if current_state.get("emoji_position") is not None else settings.get("emoji_position", "above"),
            "emoji_style": current_state.get("emoji_style") if current_state.get("emoji_style") is not None else settings.get("emoji_style", "apple"),
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
            "words_per_screen": current_state.get("words_per_screen") if current_state.get("words_per_screen") is not None else settings.get("words_per_screen", "3"),
        }

        if current_state["bg_video_bottom_path"]:
            sub_opts["alignment"] = 2
            sub_opts["margin_v"] = 440
        else:
            sub_opts["alignment"] = 5
            sub_opts["margin_v"] = 10

        target_h = 1920 if (settings.get("render_resolution", "1080p") == "1080p") else 1280
        sub_opts["target_h"] = target_h

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

        raw_chunks = [c.strip() for c in script.split("\n\n") if c.strip()]

        if not raw_chunks:
            raw_chunks = [script.strip()]
        elif len(raw_chunks) == 1:
            try:
                nltk.data.find("tokenizers/punkt_tab")
            except LookupError:
                logger.error(
                    "NLTK punkt_tab tokenizer not found. "
                    "Run: python -m nltk.downloader punkt_tab"
                )
                raise RuntimeError(
                    "NLTK punkt_tab tokenizer not installed. "
                    "Run: python -m nltk.downloader punkt_tab"
                ) from None
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
        sample_rate = 24000

        w_client = None
        if not use_local_whisper:
            try:
                if whisper_api_key:
                    w_client = OpenAI(api_key=whisper_api_key, base_url=whisper_base_url)
                elif whisper_base_url:
                    w_client = OpenAI(api_key=api_key, base_url=whisper_base_url)
                elif api_key:
                    w_client = OpenAI(api_key=api_key, base_url=base_url)
            except Exception as e:
                logger.warning(f"Failed to initialize Whisper API client: {e}")

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

        from generator import unload_tts_model

        unload_tts_model()
        log_memory_usage("Video: after TTS generation")

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

        console.print("[yellow][3/4] Generating ASS subtitle file with custom styling...[/]")
        from generator import generate_ass_subtitles

        generate_ass_subtitles(words, subs_path, style_opts=sub_opts, emoji_map=load_emoji_map())
        console.print("[green]ASS subtitles generated.[/]")

        del words
        log_memory_usage("Video: after subtitle generation")

        console.print(
            "[yellow][4/4] Rendering vertical video using FFmpeg (cropping 9:16, mixing audio, burning subtitles)...[/]"
        )
        render_preset = settings.get("render_preset", "fast")
        render_res = settings.get("render_resolution", "1080p")
        video_encoder = settings.get("video_encoder", "libx264")
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

        shutil.move(temp_output_path, output_path)
        log_memory_usage("Video: after FFmpeg rendering")

        try:
            base_name = os.path.splitext(output_filename)[0]
            txt_path = os.path.join(OUTPUT_DIR, f"{base_name}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"{current_state.get('generated_title', '')}\n")
                f.write(f"{current_state.get('generated_hashtags', '')}\n\n")
                f.write(f"Script:\n{script}\n")
        except Exception as e:
            logger.warning(f"Failed to write metadata .txt: {e}")

        try:
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
        for p in [audio_path, subs_path]:
            if os.path.exists(p):
                with contextlib.suppress(Exception):
                    os.remove(p)


def llm_job_worker(job_config, progress_dict):
    idx = job_config["index"]
    progress_dict[idx] = "LLM Script"
    logger.info(
        "[Batch LLM #%d] Starting script generation (model=%s, temp=%.2f)",
        idx,
        job_config.get("model", "?"),
        job_config.get("script_temp", 0.7),
    )
    try:
        from openai import OpenAI

        profiles = job_config["settings"].get("llm_profiles", [])
        active_id = job_config["settings"].get("active_llm_profile_id")
        active_profile = {}
        for p in profiles:
            if p.get("id") == active_id:
                active_profile = p
                break
        if not active_profile and profiles:
            active_profile = profiles[0]

        api_key = active_profile.get("api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = active_profile.get("base_url") or os.environ.get("OPENAI_BASE_URL")

        client = OpenAI(api_key=api_key, base_url=base_url)

        # Streaming LLM call with retry + buffered progress
        script_text = ""
        _last_ts = time.time()
        _last_wc = 0

        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=job_config["model"],
                    messages=[
                        {"role": "system", "content": job_config["system_prompt"]},
                        {"role": "user", "content": job_config["prompt"]},
                    ],
                    temperature=job_config["script_temp"],
                    stream=True,
                )
                break
            except Exception as e:
                err_str = str(e).lower()
                if (
                    "bad request" in err_str
                    or "auth" in err_str
                    or "unauthorized" in err_str
                    or "401" in err_str
                    or "403" in err_str
                ):
                    raise
                is_retryable = isinstance(e, (ConnectionError, TimeoutError)) or any(
                    w in err_str
                    for w in ["rate", "timeout", "connection", "overloaded", "api_error"]
                )
                if not is_retryable or attempt == 2:
                    raise
                progress_dict[idx] = f"LLM Script (retry {attempt + 1}/3)"
                time.sleep(1.0 * (2**attempt))

        for chunk in response:
            if (
                chunk.choices
                and chunk.choices[0].delta
                and chunk.choices[0].delta.content is not None
            ):
                script_text += chunk.choices[0].delta.content
                word_count = len(script_text.split())
                now = time.time()
                if word_count - _last_wc >= 5 or now - _last_ts >= 0.25:
                    progress_dict[idx] = f"LLM Script ({word_count} words)"
                    _last_ts = now
                    _last_wc = word_count

        script_text = script_text.strip()
        # Defensively strip any TITLE/HASHTAGS lines that might be in the response
        script_text, _, _ = parse_title_hashtags(script_text)

        # Always use a dedicated second LLM call for title and hashtags
        try:
            title, hashtags = generate_title_hashtags(
                script_text,
                client,
                job_config["model"],
                job_config.get("meta_temp", job_config.get("script_temp", 0.7)),
            )

            safe_title = re.sub(r"[\s\-]+", "_", title.lower())
            safe_title = re.sub(r"[^\w_]", "", safe_title).strip("_")
            if not safe_title:
                safe_title = "batch_video"

            orig_filename = job_config["output_filename"]
            timestamp_match = re.search(r"rendered_batch_(\d+)_", orig_filename)
            timestamp = timestamp_match.group(1) if timestamp_match else str(int(time.time()))

            new_filename = f"{safe_title}_{timestamp}_{idx}.mp4"
            job_config["output_filename"] = new_filename
            job_config["generated_title"] = title or "Batch Video"
            job_config["generated_hashtags"] = hashtags or "#shorts #video"
        except Exception:
            # Fallback if title/hashtag generation fails
            job_config["generated_title"] = "Batch Video"
            job_config["generated_hashtags"] = "#shorts #video"

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


def video_job_worker(job_config, progress_dict):

    idx = job_config["index"]
    output_filename = job_config["output_filename"]
    logger.info("[Batch Video #%d] Starting compilation -> %s", idx, output_filename)

    # Resolve relative asset paths before loading into state
    from gui.utils import resolve_preset_path

    resolved_bg_video = resolve_preset_path(job_config["bg_video_path"])
    resolved_bg_video_bottom = resolve_preset_path(job_config["bg_video_bottom_path"])
    resolved_bg_music = resolve_preset_path(job_config["bg_music_path"])

    # Update process-local state and settings dictionaries
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
            "generated_title": job_config.get("generated_title", "Batch Video"),
            "generated_hashtags": job_config.get("generated_hashtags", "#shorts #video"),
        }
    )

    shared_state.settings.clear()
    shared_state.settings.update(job_config["settings"])

    # Monkeypatch the config console for progress redirection in this worker process
    progress_console = ProgressConsole(idx, progress_dict)
    console.print = progress_console.print
    console.clear = progress_console.clear

    log_memory_usage(f"Job {idx}: starting compilation")

    try:
        try:
            progress_dict[idx] = "Compiling"
        except (KeyError, BrokenPipeError, ConnectionRefusedError, OSError):
            logger.warning(
                f"Batch job {idx}: failed to update progress (manager may have shut down)",
                exc_info=True,
            )

        success = retry_with_backoff(
            lambda: compile_video_flow(
                skip_confirm=True,
                custom_output_filename=output_filename,
                progress_callback=progress_console.print,
            )
        )
        if success:
            try:
                from gui.config import OUTPUT_DIR

                base_name = os.path.splitext(output_filename)[0]
                txt_path = os.path.join(OUTPUT_DIR, f"{base_name}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(f"{job_config.get('generated_title', 'Batch Video')}\n")
                    f.write(f"{job_config.get('generated_hashtags', '#shorts')}\n\n")
                    f.write(f"Script:\n{job_config.get('script_text', '')}\n")
            except Exception:
                logger.warning(
                    f"Batch job {idx}: failed to write metadata .txt (manager may have shut down)",
                    exc_info=True,
                )

        if success:
            try:
                progress_dict[idx] = "Done"
                progress_dict[f"{idx}_end"] = time.time()
            except (KeyError, BrokenPipeError, ConnectionRefusedError, OSError):
                logger.warning(
                    f"Batch job {idx}: failed to update progress (manager may have shut down)",
                    exc_info=True,
                )
            return (idx, True, output_filename)
        else:
            try:
                progress_dict[idx] = "Failed"
                progress_dict[f"{idx}_end"] = time.time()
            except (KeyError, BrokenPipeError, ConnectionRefusedError, OSError):
                logger.warning(
                    f"Batch job {idx}: failed to update progress (manager may have shut down)",
                    exc_info=True,
                )
            return (idx, False, "Compilation failed (check logs/app.log)")
    except Exception as e:
        logger.error(f"Batch job {idx} exception: {e}\n{traceback.format_exc()}")
        try:
            progress_dict[idx] = f"Failed: {str(e)}"
            progress_dict[f"{idx}_end"] = time.time()
        except (KeyError, BrokenPipeError, ConnectionRefusedError, OSError):
            logger.warning(
                f"Batch job {idx}: failed to update progress (manager may have shut down)",
                exc_info=True,
            )
        return (idx, False, str(e))
