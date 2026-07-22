import os
import sys
import asyncio
import datetime
import json
import multiprocessing
import queue
import fcntl
import pty
import select
import signal
import struct
import termios
import random
import re
import shutil
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import psutil
from fastapi import (
    APIRouter,
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import gui.state as shared_state
from gui.batch import generate_title_hashtags, parse_title_hashtags
from gui.config import (
    CONFIG_DIR,
    MUSIC_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
    VIDEOS_DIR,
    clear_cache,
    delete_custom_preset,
    load_presets,
    load_settings,
    logger,
    save_custom_preset,
    save_settings,
)
from gui.media import generate_video_thumbnail, stream_media
from gui.models import (
    BatchStartRequest,
    FetchModelsRequest,
    LogMessageRequest,
    PexelsDownloadRequest,
    PexelsSearchRequest,
    PresetModel,
    PreviewAnimationRequest,
    ScriptGenerateRequest,
    SettingsModel,
    StateModel,
    TiktokUploadRequest,
    YoutubeDownloadRequest,
    YoutubeSearchRequest,
)
from gui.utils import (
    check_system_dependencies,
    discover_opencode_keys,
    download_default_assets_if_empty,
    extract_keywords_from_script,
    get_active_llm_profile,
    resolve_preset_path,
)

from gui.globals import *
from gui.globals import _batch_state_lock, batch_state

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "gui/frontend/dist")
THUMBNAIL_DIR = os.path.join(OUTPUT_DIR, "thumbnails")

def _resolve_llm_and_client(data):
    """Resolve LLM config and return (api_key, base_url, model, client, system_prompt)."""
    active_profile = get_active_llm_profile()
    api_key = active_profile.get("api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = active_profile.get("base_url") or os.environ.get("OPENAI_BASE_URL")

    opencode_key, _ = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and not base_url:
            base_url = "https://opencode.ai/zen/go/v1"

    if not api_key:
        raise HTTPException(
            status_code=400, detail="OpenAI/OpenCode API key is missing. Set it in Settings."
        )

    default_model = active_profile.get("model", "gpt-4o-mini")
    model = (
        data.model_override.strip()
        if (data.model_override and data.model_override.strip())
        else default_model
    )

    if not model:
        if base_url and "opencode.ai" in base_url:
            model = "deepseek-v4-flash"
        else:
            model = "gpt-4o-mini"

    if data.selected_voice:
        shared_state.state["selected_voice"] = data.selected_voice
        shared_state.state["loaded_preset_name"] = None

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)

    max_words = shared_state.settings.get("max_words", 400)
    from gui.config import DEFAULT_SCRIPT_SYSTEM_PROMPT

    default_system_prompt = DEFAULT_SCRIPT_SYSTEM_PROMPT
    raw_system_prompt = shared_state.settings.get("system_prompt", default_system_prompt)
    try:
        system_prompt = raw_system_prompt.format(
            max_words=max_words, max_words_seconds=int(max_words / 2.3)
        )
    except (KeyError, ValueError):
        system_prompt = raw_system_prompt

    return api_key, base_url, model, client, system_prompt



@router.post("/api/script/generate")
def generate_viral_script(data: ScriptGenerateRequest):
    _api_key, _base_url, model, client, system_prompt = _resolve_llm_and_client(data)

    logger.info(f"[AI Script] Generating script with model '{model}' for prompt: '{data.prompt}'")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": data.prompt},
            ],
            temperature=shared_state.settings.get("llm_temp_script", 0.7),
        )
        script_text = (response.choices[0].message.content or "").strip()
        # Defensively strip any TITLE/HASHTAGS lines (guideline #9 is no longer in prompt)
        script_text, _, _ = parse_title_hashtags(script_text)

        # Always use a dedicated second LLM call for title and hashtags
        try:
            title, hashtags = generate_title_hashtags(
                script_text, client, model, shared_state.settings.get("llm_temp_title", 0.7)
            )
        except Exception as e:
            logger.warning(f"Title/hashtag generation failed: {e}")
            words = script_text.split()
            title = " ".join(words[:8]) if words else ""
            hashtags = ""

        shared_state.state["script_text"] = script_text
        shared_state.state["generated_title"] = title
        shared_state.state["generated_hashtags"] = hashtags

        # Save state to disk (lock to prevent concurrent write corruption)
        with _state_file_lock, open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(shared_state.state, f, indent=2)

        return {"status": "success", "script": script_text, "title": title, "hashtags": hashtags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Script generation failed: {str(e)}")



@router.post("/api/script/generate/stream")
def generate_script_stream(data: ScriptGenerateRequest):
    _api_key, _base_url, model, client, system_prompt = _resolve_llm_and_client(data)

    logger.info(
        f"[AI Script/Stream] Generating script with model '{model}' for prompt: '{data.prompt}'"
    )

    def event_stream():
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": data.prompt},
                ],
                temperature=shared_state.settings.get("llm_temp_script", 0.7),
                stream=True,
            )
            script_text = ""
            word_count = 0
            for chunk in response:
                if (
                    chunk.choices
                    and chunk.choices[0].delta
                    and chunk.choices[0].delta.content is not None
                ):
                    content = chunk.choices[0].delta.content
                    script_text += content
                    word_count = len(script_text.split())
                    yield f"data: {json.dumps({'chunk': content, 'word_count': word_count})}\n\n"

            script_text = script_text.strip()
            # Defensively strip any TITLE/HASHTAGS lines (guideline #9 is no longer in prompt)
            script_text, _, _ = parse_title_hashtags(script_text)

            # Always use a dedicated second LLM call for title and hashtags
            try:
                title, hashtags = generate_title_hashtags(
                    script_text, client, model, shared_state.settings.get("llm_temp_title", 0.7)
                )
            except Exception as e:
                logger.warning(f"Title/hashtag generation failed: {e}")
                words = script_text.split()
                title = " ".join(words[:8]) if words else ""
                hashtags = ""

            shared_state.state["script_text"] = script_text
            shared_state.state["generated_title"] = title
            shared_state.state["generated_hashtags"] = hashtags
            with _state_file_lock, open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(shared_state.state, f, indent=2)

            yield f"data: {json.dumps({'done': True, 'word_count': word_count, 'title': title, 'hashtags': hashtags})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            raise

    return StreamingResponse(event_stream(), media_type="text/event-stream")



def compile_worker():
    global compilation_in_progress, compilation_success

    while True:
        job = compilation_queue.get(block=True)
        if job is None:
            break

        custom_filename = job.get("custom_filename")
        state_snapshot = job.get("state_snapshot")

        with _compile_status_lock:
            compilation_in_progress = True
            compilation_success = False

        # Clear logs from the previous job and add a separator
        with _compile_log_lock:
            compilation_logs.clear()
            compilation_logs.append("=" * 50 + "\n")

        logger.info(
            f"[Compile Thread] Starting video compilation process (Queue size: {compilation_queue.qsize()})..."
        )
        notify_clients("compilation", "started", "Video compilation started.", "info", {"filename": custom_filename})
        try:
            from gui.compiler import compile_video_flow

            # run compilation flow with skip_confirm=True
            success = compile_video_flow(
                skip_confirm=True,
                custom_output_filename=custom_filename,
                state_override=state_snapshot,
            )
            with _compile_status_lock:
                compilation_success = success
            if success:
                logger.info("[Compile Thread] Compilation finished successfully!")
                notify_clients("compilation", "success", f"Video compilation finished successfully!", "success", {"filename": custom_filename})
            else:
                logger.error(
                    "[Compile Thread] Compilation failed (returned False). Check logs above."
                )
                notify_clients("compilation", "error", "Compilation failed. Check logs.", "error", {"filename": custom_filename})
        except Exception as e:
            logger.error(f"[Compile Thread] Crash during compilation: {e}")
            notify_clients("compilation", "error", f"Crash during compilation: {e}", "error", {"filename": custom_filename})

            logger.exception("Exception occurred")
            with _compile_status_lock:
                compilation_success = False
        finally:
            with _compile_status_lock:
                compilation_in_progress = False
            compilation_queue.task_done()



@router.post("/api/compile")
def start_compilation(custom_filename: str | None = Form(None)):
    global compilation_thread

    # Validate script and background video
    if not shared_state.state["script_text"].strip():
        raise HTTPException(
            status_code=400, detail="Script is empty. Please generate or write a script first."
        )
    if not shared_state.state["bg_video_path"]:
        raise HTTPException(status_code=400, detail="Top background video is not selected.")

    import copy

    state_snapshot = copy.deepcopy(shared_state.state)

    # Put job inside the lock to prevent orphaned jobs if thread dies
    with _compile_thread_lock:
        compilation_queue.put(
            {
                "custom_filename": custom_filename.strip() if custom_filename else None,
                "state_snapshot": state_snapshot,
            }
        )

        if compilation_thread is None or not compilation_thread.is_alive():
            compilation_thread = threading.Thread(target=compile_worker, daemon=True)
            compilation_thread.start()

    return {
        "status": "started",
        "message": f"Video compilation queued. (Queue size: {compilation_queue.qsize()})",
    }



@router.get("/api/compile/status")
def get_compilation_status():
    with _compile_log_lock:
        log_snapshot = "".join(compilation_logs)
    with _compile_status_lock:
        in_progress = compilation_in_progress or not compilation_queue.empty()
        success = compilation_success
    return {
        "in_progress": in_progress,
        "success": success,
        "logs": log_snapshot,
        "queue_size": compilation_queue.qsize(),
    }



@router.post("/api/compile/cancel")
def cancel_compilation():
    # Since python threads cannot be killed easily, we notify the user.
    # In a real app we'd have a cancel flag, but compile_video does ffmpeg processes.
    # We can try to kill running ffmpeg subprocesses if we want, but letting it finish or notifying is safer.
    # We will log cancellation attempt.
    logger.info(
        "[Compile Thread] Compilation cancellation requested (note: background processes will terminate on completion/next cycle)."
    )
    return {"status": "success", "message": "Cancellation request received."}



def _resolve_worker_count(key, default, min_val=1):
    """Resolve a worker count from settings with a fallback default."""
    val = shared_state.settings.get(key)
    if val:
        try:
            return max(min_val, int(val))
        except (ValueError, TypeError):
            return default
    return default



def _sync_progress(batch_state, num_shorts):
    """Copy shared_progress (Manager dict) to progress_dict (regular dict) for API access."""
    with _batch_state_lock:
        for i in range(1, num_shorts + 1):
            batch_state["progress_dict"][i] = batch_state["shared_progress"].get(i, "Queued")
            start_key = f"{i}_start"
            end_key = f"{i}_end"
            if start_key in batch_state["shared_progress"]:
                batch_state["progress_dict"][start_key] = batch_state["shared_progress"][start_key]
            if end_key in batch_state["shared_progress"]:
                batch_state["progress_dict"][end_key] = batch_state["shared_progress"][end_key]



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
    failure_mode = shared_state.settings.get("batch_failure_mode", "stop_all")

    try:
        from generator import unload_tts_model
        from gui.compiler import unload_whisper_model

        # Free up GPU memory from the main process before spawning workers
        unload_tts_model()
        unload_whisper_model()

        from gui.batch import llm_job_worker, log_memory_usage, video_job_worker
        from gui.config import load_prompt_templates

        log_memory_usage("After model unloading")

        templates = load_prompt_templates()
        presets = load_presets()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        from gui.utils import get_active_llm_profile

        active_profile = get_active_llm_profile()
        api_key = active_profile.get("api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = active_profile.get("base_url") or os.environ.get("OPENAI_BASE_URL")
        opencode_key, _ = discover_opencode_keys()
        if not api_key:
            api_key = opencode_key
            if api_key and not base_url:
                base_url = "https://opencode.ai/zen/go/v1"

        model = active_profile.get("model", "gpt-4o-mini")
        if not active_profile.get("model") and base_url and "opencode.ai" in base_url:
            model = "deepseek-v4-flash"

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
                template_title, prompt = prompt_items[i % len(prompt_items)]

                voice_name, voice_id = random.choice(shared_state.VOICES)

                preset_name = "default"
                preset = {}
                if presets:
                    preset_name, preset = random.choice(list(presets.items()))

                is_split = random.choice([True, False])
                top_video = "random"
                bottom_video = "random" if is_split else None

                os.makedirs(MUSIC_DIR, exist_ok=True)
                music_files = [
                    f
                    for f in os.listdir(MUSIC_DIR)
                    if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg", ".flac"))
                ]

                bg_music_preset = preset.get("bg_music_path", "music/default_music.mp3")

                if music_files:
                    chosen_music = os.path.join(MUSIC_DIR, random.choice(music_files))
                else:
                    chosen_music = _resolve_music(bg_music_preset)

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

                job_configs[i] = {
                    "index": i,
                    "prompt": prompt,
                    "voice_id": voice_id,
                    "bg_video_path": top_video,
                    "bg_video_bottom_path": bottom_video,
                    "bg_music_path": chosen_music,
                    "music_volume": preset.get("music_volume", 0.15),
                    "voice_volume": preset.get("voice_volume", 1.0),
                    "sub_font": sub_font,
                    "sub_size": sub_size,
                    "sub_color": sub_color,
                    "sub_highlight": sub_highlight,
                    "sub_outline": sub_outline,
                    "sub_outline_width": sub_outline_width,
                    "sub_bold": sub_bold,
                    "enable_emojis": enable_emojis,
                    "enable_color_emoji": shared_state.settings.get("enable_color_emoji") if shared_state.settings.get("enable_color_emoji") is not None else True,
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
                    "sub_uppercase": preset.get("sub_uppercase", True),
                    "voice_speed": preset.get("voice_speed"),
                    "sub_border_style": preset.get("sub_border_style", 1),
                    "sub_shadow_width": preset.get("sub_shadow_width", 0),
                    "sub_bg_color": preset.get("sub_bg_color", "#000000"),
                    "sub_bg_alpha": preset.get("sub_bg_alpha", "80"),
                    "single_word_mode": preset.get("single_word_mode", False),
                    "words_per_screen": words_per_screen_choice,
                    "emoji_position": preset.get("emoji_position", "above"),
                    "emoji_style": random.choice(emoji_styles) if emoji_styles else preset.get("emoji_style", "apple"),
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
        logger.info(
            "[Batch Thread] Starting %d shorts with %d video workers, %d LLM workers, failure_mode=%s",
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

        # Two-phase pipeline: phase 1 = all LLM, phase 2 = video as LLM completes
        llm_futures = []
        for i in range(1, num_shorts + 1):
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
                            batch_state["shared_progress"][i] = "Waiting for Compilation"
                            vf = batch_state["executor"].submit(
                                video_job_worker, job_configs[i], batch_state["shared_progress"]
                            )
                            video_futures.append((i, vf))
                        else:
                            logger.warning("[Batch] Job #%d — LLM failed: %s", i, err_msg)
                            batch_state["shared_progress"][i] = f"Failed: {err_msg}"
                            batch_state["failed_job_configs"].append(job_configs[i])
                            if failure_mode == "stop_all":
                                batch_state["should_cancel"] = True
                                break
                    except Exception as e:
                        logger.error(f"[Batch Thread] LLM job {i} exception: {e}")
                        batch_state["shared_progress"][i] = f"Failed: {str(e)}"
                        batch_state["failed_job_configs"].append(job_configs[i])
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
            batch_state["batch_results"].append(
                {
                    "id": i,
                    "topic": detail.get("topic", ""),
                    "voice": detail.get("voice", ""),
                    "layout": detail.get("layout", ""),
                    "status": status,
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



@router.get("/api/prompts")
def get_prompts():
    from gui.config import load_prompt_templates

    return load_prompt_templates()



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



@router.post("/api/batch/start")
def start_batch(data: BatchStartRequest):
    _log_memory_warning()
    num_shorts = data.num_shorts
    if num_shorts < 1 or num_shorts > 100:
        raise HTTPException(status_code=400, detail="Number of shorts must be between 1 and 100.")

    # Create expensive manager outside lock so we don't block for too long
    new_manager = multiprocessing.Manager()
    new_shared = new_manager.dict()

    with _batch_lock:
        if batch_state["in_progress"]:
            new_manager.shutdown()  # clean up the manager we just created
            raise HTTPException(status_code=400, detail="A batch job is already running.")
        batch_state["in_progress"] = True
        batch_state["num_shorts"] = num_shorts
        batch_state["progress_dict"].clear()
        batch_state["job_configs"] = {}
        batch_state["manager"] = new_manager
        batch_state["shared_progress"] = new_shared

    t = threading.Thread(
        target=batch_worker_thread,
        args=(
            num_shorts,
            data.prompts,
            data.enable_emojis,
            data.enable_emoji_animation,
            data.emoji_scale_factor,
            data.emoji_hold_duration,
            data.emoji_throw_max_count,
            data.emoji_styles,
        ),
        daemon=True,
    )
    t.start()
    return {"status": "started", "message": f"Batch generation of {num_shorts} shorts started."}



@router.get("/api/batch/status")
def get_batch_status():
    from gui.batch import format_elapsed, get_progress_percentage

    with _batch_state_lock:
        # Compute average completion time from finished jobs
        completed_durations = []
        for i in range(1, batch_state["num_shorts"] + 1):
            st = batch_state["progress_dict"].get(f"{i}_start")
            et = batch_state["progress_dict"].get(f"{i}_end")
            status_i = batch_state["progress_dict"].get(i, "Queued")
            if st and et and status_i == "Done":
                completed_durations.append(et - st)
        avg_completion_time = (
            sum(completed_durations) / len(completed_durations) if completed_durations else None
        )

        jobs = []
        for i in range(1, batch_state["num_shorts"] + 1):
            status = batch_state["progress_dict"].get(i, "Queued")
            pct = get_progress_percentage(status)

            start_time = batch_state["progress_dict"].get(f"{i}_start")
            end_time = batch_state["progress_dict"].get(f"{i}_end")
            elapsed_str = "--"
            eta_str = "--"
            eta_seconds = 0.0
            if start_time:
                duration = (end_time if end_time else time.time()) - start_time
                elapsed_str = format_elapsed(duration)
                if status == "Done":
                    elapsed_str += " (Done)"
                    eta_str = "0s"
                elif pct and pct > 0:
                    if avg_completion_time is not None and avg_completion_time > duration:
                        eta_seconds = avg_completion_time - duration
                    elif pct < 100:
                        eta_seconds = duration / pct * (100 - pct)
                    else:
                        eta_seconds = 0
                    eta_str = format_elapsed(eta_seconds)

            detail = batch_state["job_details"].get(i, {})
            jobs.append(
                {
                    "id": i,
                    "topic": detail.get("topic", "Unknown"),
                    "voice": detail.get("voice", "Unknown"),
                    "layout": detail.get("layout", "Unknown"),
                    "enable_emojis": detail.get("enable_emojis", False),
                    "status": status,
                    "progress": pct if pct is not None else 0,
                    "failed": pct is None,
                    "elapsed": elapsed_str,
                    "eta": eta_str,
                    "eta_seconds": eta_seconds,
                }
            )

        in_progress = batch_state["in_progress"]
        num_shorts = batch_state["num_shorts"]

    return {
        "in_progress": in_progress,
        "num_shorts": num_shorts,
        "jobs": jobs,
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "progress_segments": [
            {"name": "LLM", "start": 0, "end": 20},
            {"name": "Voice", "start": 20, "end": 45},
            {"name": "Transcribe", "start": 45, "end": 55},
            {"name": "Render", "start": 55, "end": 100},
        ],
    }



@router.get("/api/batch/job/{job_id}")
def get_batch_job_detail(job_id: int):
    from gui.batch import format_elapsed, get_progress_percentage

    with _batch_state_lock:
        # Check if the job exists
        if job_id < 1 or job_id > batch_state["num_shorts"]:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get progress info
        status = batch_state["progress_dict"].get(job_id, "Unknown")
        pct = get_progress_percentage(status)

        start_time = batch_state["progress_dict"].get(f"{job_id}_start")
        end_time = batch_state["progress_dict"].get(f"{job_id}_end")
        elapsed_str = "--"
        eta_str = "--"
        eta_seconds = 0.0
        # Compute average completion time from finished jobs
        completed_durations = []
        for i in range(1, batch_state["num_shorts"] + 1):
            st = batch_state["progress_dict"].get(f"{i}_start")
            et = batch_state["progress_dict"].get(f"{i}_end")
            status_i = batch_state["progress_dict"].get(i, "Queued")
            if st and et and status_i == "Done":
                completed_durations.append(et - st)
        avg_completion_time = (
            sum(completed_durations) / len(completed_durations) if completed_durations else None
        )

        if start_time:
            import time

            duration = (end_time if end_time else time.time()) - start_time
            elapsed_str = format_elapsed(duration)
            if status == "Done":
                elapsed_str += " (Done)"
                eta_str = "0s"
            elif pct and pct > 0:
                if avg_completion_time is not None and avg_completion_time > duration:
                    eta_seconds = avg_completion_time - duration
                elif pct < 100:
                    eta_seconds = duration / pct * (100 - pct)
                else:
                    eta_seconds = 0
                eta_str = format_elapsed(eta_seconds)

        # Get detail and config
        detail = batch_state["job_details"].get(job_id, {})
        config = batch_state.get("job_configs", {}).get(job_id, {})

    # Build response with ALL job settings
    return {
        "id": job_id,
        "topic": detail.get("topic", ""),
        "voice_name": detail.get("voice", "Unknown"),
        "layout": detail.get("layout", "Unknown"),
        "enable_emojis": detail.get("enable_emojis", False),
        "status": status,
        "progress": pct if pct is not None else 0,
        "failed": pct is None,
        "elapsed": elapsed_str,
        "eta": eta_str,
        "eta_seconds": eta_seconds,
        # Full config fields (all optional - use empty string/0/False defaults)
        "prompt": config.get("prompt", ""),
        "voice_id": config.get("voice_id", ""),
        "bg_video_path": config.get("bg_video_path", ""),
        "bg_video_bottom_path": config.get("bg_video_bottom_path"),
        "bg_music_path": config.get("bg_music_path"),
        "music_volume": config.get("music_volume", 0),
        "voice_volume": config.get("voice_volume", 0),
        "sub_font": config.get("sub_font", ""),
        "sub_size": config.get("sub_size", 0),
        "sub_color": config.get("sub_color", ""),
        "sub_highlight": config.get("sub_highlight", ""),
        "sub_outline": config.get("sub_outline", ""),
        "sub_outline_width": config.get("sub_outline_width", 0),
        "sub_bold": config.get("sub_bold", False),
        "word_pop": config.get("word_pop", False),
        "word_pop_scale": config.get("word_pop_scale", 0),
        "inactive_dim": config.get("inactive_dim", False),
        "inactive_alpha": config.get("inactive_alpha", ""),
        "sub_uppercase": config.get("sub_uppercase", False),
        "voice_speed": config.get("voice_speed"),
        "sub_border_style": config.get("sub_border_style", 0),
        "sub_shadow_width": config.get("sub_shadow_width", 0),
        "sub_bg_color": config.get("sub_bg_color", ""),
        "sub_bg_alpha": config.get("sub_bg_alpha", ""),
        "single_word_mode": config.get("single_word_mode", False),
        "words_per_screen": config.get("words_per_screen", ""),
        "emoji_position": config.get("emoji_position", ""),
        "emoji_style": config.get("emoji_style", ""),
        "sub_animation_style": config.get("sub_animation_style", ""),
        "enable_emoji_animation": config.get("enable_emoji_animation", False),
        "enable_color_emoji": config.get("enable_color_emoji", False),
        "emoji_scale_factor": config.get("emoji_scale_factor", 0),
        "emoji_hold_duration": config.get("emoji_hold_duration", 0),
        "emoji_throw_max_count": config.get("emoji_throw_max_count", 0),
        "script_temp": config.get("script_temp", 0),
        "meta_temp": config.get("meta_temp", 0),
        "model": config.get("model", ""),
        "system_prompt": config.get("system_prompt", ""),
        "output_filename": config.get("output_filename", ""),
        "generated_title": config.get("generated_title", ""),
        "generated_hashtags": config.get("generated_hashtags", ""),
        "script_text": config.get("script_text", ""),
    }



@router.post("/api/batch/cancel")
def cancel_batch():
    with _batch_state_lock:
        in_progress = batch_state["in_progress"]
        if in_progress:
            batch_state["should_cancel"] = True
    if in_progress:
        return {
            "status": "success",
            "message": "Cancellation requested. Waiting for active workers to terminate.",
        }
    return {"status": "ignored", "message": "No active batch to cancel."}



@router.post("/api/batch/retry-failed")
def retry_failed_batch():
    if batch_state["in_progress"]:
        raise HTTPException(status_code=400, detail="A batch is currently running.")

    failed_configs = batch_state.get("failed_job_configs", [])
    if not failed_configs:
        raise HTTPException(status_code=400, detail="No failed jobs to retry.")

    num_failed = len(failed_configs)

    new_manager = multiprocessing.Manager()
    new_shared = new_manager.dict()

    with _batch_lock:
        batch_state["in_progress"] = True
        batch_state["num_shorts"] = num_failed
        batch_state["progress_dict"].clear()
        batch_state["manager"] = new_manager
        batch_state["shared_progress"] = new_shared
        batch_state["failed_job_configs"] = []
        batch_state["_retry_configs"] = failed_configs

    t = threading.Thread(target=batch_worker_thread, args=(num_failed, None), daemon=True)
    t.start()
    return {"status": "started", "message": f"Retrying {num_failed} failed jobs."}



@router.get("/api/batch/report")
def get_batch_report():
    with _batch_state_lock:
        results = batch_state.get("batch_results", [])
    if not results:
        raise HTTPException(status_code=404, detail="No batch results available.")

    total = len(results)
    succeeded = sum(1 for r in results if r["status"] == "Done")
    failed = sum(1 for r in results if r["status"].startswith("Failed"))

    return {
        "summary": {
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
        },
        "jobs": results,
    }

@router.post("/api/preview_animation")
async def preview_animation(request: PreviewAnimationRequest):
    from gui.preview import create_animation_preview
    
    settings_dict = request.settings.model_dump()
    try:
        webm_path = await create_animation_preview(
            settings_dict, 
            request.test_word or "Awesome", 
            request.emoji_char or "🚀"
        )
        return FileResponse(webm_path, media_type="video/webm")
    except Exception as e:
        logger.exception("Failed to generate animation preview")
        raise HTTPException(status_code=500, detail=str(e))

