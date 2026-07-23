import concurrent.futures
import os
import re
import time
import traceback
from dataclasses import dataclass, fields

from gui import state as shared_state
from gui.config import OUTPUT_DIR, console, logger
from gui.utils import resolve_preset_path

from gui.video_compiler import compile_video_flow, _release_memory_to_os, unload_whisper_model
from gui.progress_utils import (
    get_progress_percentage,
    make_progress_bar,
    format_elapsed,
    display_progress_table,
    log_memory_usage,
)
from gui.llm_utils import retry_with_backoff, parse_title_hashtags, generate_title_hashtags


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

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=300.0)

        # Streaming LLM call with retry + buffered progress
        # Retry covers both the initial request AND the streaming read,
        # so mid-stream disconnects ("incomplete chunked read") trigger a full restart.
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
                script_text = ""
                _last_ts = time.time()
                _last_wc = 0
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
                break  # success — exit retry loop
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
                    for w in [
                        "rate", "timeout", "connection", "overloaded",
                        "api_error", "incomplete chunked read",
                    ]
                )
                if not is_retryable or attempt == 2:
                    raise
                progress_dict[idx] = f"LLM Script (retry {attempt + 1}/3)"
                time.sleep(1.0 * (2**attempt))

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
