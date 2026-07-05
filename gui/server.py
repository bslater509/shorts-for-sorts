import os
import sys

# Ensure parent directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from gui.utils import (
    check_system_dependencies, download_default_assets_if_empty,
    extract_keywords_from_script, discover_opencode_keys
)
from gui.config import (
    CONFIG_DIR, VIDEOS_DIR, MUSIC_DIR, OUTPUT_DIR, TEMP_DIR,
    load_settings, save_settings, load_presets, save_custom_preset, delete_custom_preset,
    clear_cache, logger
)
import gui.state as shared_state
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException, WebSocket
import json
import shutil
import urllib.parse
import urllib.request
import threading
import queue

# Locks for thread-safe access to shared mutable state
_compile_log_lock = threading.Lock()      # Guards compilation_logs list
_compile_thread_lock = threading.Lock()   # Guards compilation_thread spawn
_state_file_lock = threading.Lock()       # Guards GUI_STATE_FILE writes
_batch_lock = threading.Lock()            # Guards batch_state["in_progress"] TOCTOU
import traceback
import time
import random
import datetime
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Optional
import psutil
import asyncio


app = FastAPI(title="Shorts for Sorts Web GUI")

@app.on_event("startup")
async def cleanup_temp_dir():
    try:
        for f in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, f)
            if os.path.isfile(file_path):
                os.remove(file_path)
        logger.info("Cleaned up orphaned files in temp directory on startup.")
    except Exception as e:
        logger.warning(f"Failed to clean temp directory on startup: {e}")

@app.websocket("/api/system_stats")
async def websocket_system_stats(websocket: WebSocket):
    await websocket.accept()
    # Initial call to cpu_percent to set baseline
    psutil.cpu_percent(interval=None)
    try:
        while True:
            await asyncio.sleep(1)
            cpu_usage = psutil.cpu_percent(interval=None)
            
            memory_info = psutil.virtual_memory()
            memory_percent = memory_info.percent
            
            await websocket.send_json({
                "cpu_percent": round(cpu_usage, 1),
                "memory_percent": round(memory_percent, 1)
            })
    except Exception as e:
        # Silently ignore disconnections; log unexpected errors for diagnosis
        from fastapi.websockets import WebSocketDisconnect
        if not isinstance(e, WebSocketDisconnect):
            logger.debug(f"[WebSocket system_stats] Unexpected error: {e}")

# Persistence path for GUI Session State
GUI_STATE_FILE = os.path.join(CONFIG_DIR, "gui_state.json")

# Server-side compilation tracking
compilation_in_progress = False
compilation_success = False
compilation_logs = []
compilation_thread = None
compilation_queue = queue.Queue()

# Custom Stdout redirector to capture compilation logs
original_stdout = sys.stdout
original_stderr = sys.stderr


class WebStdoutRedirector:
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, text):
        self.original_stream.write(text)
        if compilation_in_progress:
            # Thread-safe append: compilation_logs is read concurrently by API thread
            with _compile_log_lock:
                compilation_logs.append(text)

    def flush(self):
        self.original_stream.flush()

    def __getattr__(self, name):
        return getattr(self.original_stream, name)


sys.stdout = WebStdoutRedirector(original_stdout)
sys.stderr = WebStdoutRedirector(original_stderr)


def init_app_state():
    """Initializes the backend settings, dependencies, and default state."""
    # Ensure default folders and settings are loaded
    clear_cache()
    try:
        check_system_dependencies()
    except Exception as e:
        logger.warning(f"System dependencies check failed: {e}")

    load_settings()
    download_default_assets_if_empty()

    # Auto-load GUI state if it exists
    if os.path.exists(GUI_STATE_FILE):
        try:
            with open(GUI_STATE_FILE, "r", encoding="utf-8") as f:
                saved_state = json.load(f)
                # Filter saved keys to match key structure in shared_state.state
                for k, v in saved_state.items():
                    if k in shared_state.state:
                        shared_state.state[k] = v
        except Exception as e:
            logger.error(f"Failed to load gui_state.json: {e}")
            


init_app_state()

# Mount static asset folders directly so they can be previewed/downloaded in browser
app.mount("/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")
app.mount("/music", StaticFiles(directory=MUSIC_DIR), name="music")
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "gui/frontend/dist")
if os.path.exists(FRONTEND_DIST_DIR):
    app.mount(
        "/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST_DIR, "assets")), name="assets")
    app.mount("/static", StaticFiles(directory=FRONTEND_DIST_DIR), name="static")
else:
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR,
              "gui/static")), name="static")

# Pydantic schemas


class SettingsModel(BaseModel):
    api_key: Optional[str] = ""
    base_url: Optional[str] = ""
    model: Optional[str] = "gpt-4o-mini"
    pexels_api_key: Optional[str] = ""
    voice_speed: Optional[float] = 1.0
    voice_volume: Optional[float] = 1.0
    music_volume: Optional[float] = 0.15
    local_whisper: Optional[bool] = True
    local_whisper_model: Optional[str] = "tiny"
    whisper_api_key: Optional[str] = ""
    whisper_base_url: Optional[str] = ""
    render_resolution: Optional[str] = "1080p"
    render_preset: Optional[str] = "veryfast"
    video_encoder: Optional[str] = "libx264"
    max_words: Optional[int] = 130
    max_workers: Optional[int] = 1
    llm_max_workers: Optional[int] = 5
    words_per_screen: Optional[str] = "3"
    sub_font: Optional[str] = "Arial"
    sub_size: Optional[int] = 72
    sub_color: Optional[str] = "#FFFFFF"
    sub_highlight: Optional[str] = "#00FFFF"
    sub_outline: Optional[str] = "#000000"
    sub_outline_width: Optional[int] = 5
    sub_bold: Optional[bool] = True
    word_pop: Optional[bool] = True
    word_pop_scale: Optional[float] = 1.15
    inactive_dim: Optional[bool] = True
    inactive_alpha: Optional[str] = "88"
    enable_emojis: Optional[bool] = True
    sub_uppercase: Optional[bool] = True
    sub_border_style: Optional[int] = 1
    sub_shadow_width: Optional[int] = 0
    sub_bg_color: Optional[str] = "#000000"
    sub_bg_alpha: Optional[str] = "80"
    single_word_mode: Optional[bool] = False
    emoji_position: Optional[str] = "above"
    emoji_font: Optional[str] = "Symbola"
    sub_animation_style: Optional[str] = "tiktok_pop"
    sentry_dsn: Optional[str] = ""


class PresetModel(BaseModel):
    name: str
    selected_voice: str
    voice_speed: float
    bg_video_path: Optional[str] = "random"
    bg_video_bottom_path: Optional[str] = None
    bg_music_path: Optional[str] = "music/default_music.mp3"
    music_volume: float
    voice_volume: float
    sub_font: str
    sub_size: int
    sub_color: str
    sub_highlight: str
    sub_outline: str
    sub_outline_width: int
    sub_bold: bool
    word_pop: bool
    word_pop_scale: float
    inactive_dim: bool
    inactive_alpha: str
    enable_emojis: bool
    sub_animation_style: str
    single_word_mode: Optional[bool] = False
    emoji_position: Optional[str] = "above"
    sub_uppercase: Optional[bool] = True
    sub_border_style: Optional[int] = 1


class StateModel(BaseModel):
    script_text: str
    bg_video_path: Optional[str] = None
    bg_video_bottom_path: Optional[str] = None
    selected_voice: str
    bg_music_path: Optional[str] = None
    music_volume: Optional[float] = None
    voice_volume: Optional[float] = None
    sub_font: Optional[str] = None
    sub_size: Optional[int] = None
    sub_color: Optional[str] = None
    sub_highlight: Optional[str] = None
    sub_outline: Optional[str] = None
    sub_outline_width: Optional[int] = None
    sub_bold: Optional[bool] = None
    word_pop: Optional[bool] = None
    word_pop_scale: Optional[float] = None
    inactive_dim: Optional[bool] = None
    words_per_screen: Optional[str] = None
    inactive_alpha: Optional[str] = None
    enable_emojis: Optional[bool] = None
    sub_uppercase: Optional[bool] = None
    sub_border_style: Optional[int] = None
    sub_shadow_width: Optional[int] = None
    sub_bg_color: Optional[str] = None
    sub_bg_alpha: Optional[str] = None
    single_word_mode: Optional[bool] = None
    emoji_position: Optional[str] = None
    emoji_font: Optional[str] = None
    sub_animation_style: Optional[str] = None
    loaded_preset_name: Optional[str] = None


class ScriptGenerateRequest(BaseModel):
    prompt: str
    selected_voice: Optional[str] = None
    model_override: Optional[str] = None


class PexelsSearchRequest(BaseModel):
    query: str


class LogMessageRequest(BaseModel):
    level: str
    message: str


class PexelsDownloadRequest(BaseModel):
    download_url: str
    video_id: int
    keyword: str
    position: str  # "top" or "bottom"

class YoutubeDownloadRequest(BaseModel):
    url: str
    downscale: bool = False

# REST Endpoints


@app.get("/")
def get_root():
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(BASE_DIR, "gui/static/index.html"))


@app.post("/api/log")
def log_from_client(log: LogMessageRequest):
    if log.level == "error":
        logger.error(f"[Frontend] {log.message}")
    elif log.level == "warn":
        logger.warning(f"[Frontend] {log.message}")
    else:
        logger.info(f"[Frontend] {log.message}")
    return {"status": "success"}


@app.get("/api/settings")
def get_api_settings():
    # reload settings from disk first
    load_settings()
    return shared_state.settings


@app.post("/api/settings")
def save_api_settings(data: SettingsModel):
    # Convert model to dict
    settings_dict = data.model_dump()
    # If key was default pattern, replace with blank
    if settings_dict.get("api_key") == "YOUR_API_KEY_HERE":
        settings_dict["api_key"] = ""

    success = save_settings(settings_dict)
    if success:
        return {"status": "success", "message": "Settings saved successfully."}
    else:
        raise HTTPException(
            status_code=500, detail="Failed to save settings to disk.")


@app.get("/api/presets")
def get_api_presets():
    # Combination of builtin and custom presets
    presets = load_presets()
    return presets


@app.post("/api/presets")
def save_api_preset(data: PresetModel):
    preset_dict = data.model_dump()
    name = preset_dict.pop("name")
    success = save_custom_preset(name, preset_dict)
    if success:
        return {"status": "success", "message": f"Preset '{name}' saved successfully."}
    else:
        raise HTTPException(status_code=500, detail="Failed to save preset.")


@app.delete("/api/presets/{name}")
def delete_api_preset(name: str):
    success = delete_custom_preset(name)
    if success:
        return {"status": "success", "message": f"Preset '{name}' deleted successfully."}
    else:
        raise HTTPException(
            status_code=400, detail=f"Preset '{name}' could not be deleted (might be builtin or not found).")


@app.get("/api/state")
def get_api_state():
    return shared_state.state


@app.post("/api/state")
def save_api_state(data: StateModel):
    # Update global shared state
    for k, v in data.model_dump().items():
        shared_state.state[k] = v

    # Persist gui state to disk (lock to prevent concurrent write corruption)
    try:
        with _state_file_lock:
            with open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(shared_state.state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save gui_state.json: {e}")

    return {"status": "success", "data": shared_state.state}


@app.get("/api/voices")
def get_api_voices():
    # Return mapping of friendly name and internal tag
    return [{"name": name, "value": val} for name, val in shared_state.VOICES]


@app.get("/api/assets/videos")
def list_assets_videos():
    if not os.path.exists(VIDEOS_DIR):
        return []
    videos = []
    for f in os.listdir(VIDEOS_DIR):
        if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.avi')):
            fp = os.path.join(VIDEOS_DIR, f)
            size = os.path.getsize(fp)
            modified = os.path.getmtime(fp)
            videos.append({
                "filename": f,
                "url": f"/videos/{f}",
                "size": size,
                "modified": modified
            })
    # Sort by modified time (newest first)
    videos.sort(key=lambda x: x["modified"], reverse=True)
    return videos


@app.post("/api/assets/videos")
def upload_assets_video(file: UploadFile = File(...)):
    filename = "".join(
        c for c in file.filename if c.isalnum() or c in ('.', '_', '-')
    )
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Save the file to videos/
    dest_path = os.path.join(VIDEOS_DIR, filename)
    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"status": "success", "filename": filename, "url": f"/videos/{filename}"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to upload video: {e}")


@app.delete("/api/assets/videos/{filename}")
def delete_assets_video(filename: str):
    # Safety checks
    filename = os.path.basename(filename)
    dest_path = os.path.join(VIDEOS_DIR, filename)
    if not os.path.exists(dest_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    try:
        os.remove(dest_path)
        # Clear state paths if it matches
        if shared_state.state["bg_video_path"] == dest_path:
            shared_state.state["bg_video_path"] = None
        if shared_state.state["bg_video_bottom_path"] == dest_path:
            shared_state.state["bg_video_bottom_path"] = None
        return {"status": "success", "message": "Video deleted successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete video: {e}")


@app.get("/api/assets/music")
def list_assets_music():
    if not os.path.exists(MUSIC_DIR):
        return []
    music = []
    for f in os.listdir(MUSIC_DIR):
        if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac')):
            fp = os.path.join(MUSIC_DIR, f)
            size = os.path.getsize(fp)
            modified = os.path.getmtime(fp)
            music.append({
                "filename": f,
                "url": f"/music/{f}",
                "size": size,
                "modified": modified
            })
    # Sort by modified time
    music.sort(key=lambda x: x["modified"], reverse=True)
    return music


@app.post("/api/assets/music")
def upload_assets_music(file: UploadFile = File(...)):
    filename = "".join(
        c for c in file.filename if c.isalnum() or c in ('.', '_', '-')
    )
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    dest_path = os.path.join(MUSIC_DIR, filename)
    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"status": "success", "filename": filename, "url": f"/music/{filename}"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to upload music: {e}")


@app.delete("/api/assets/music/{filename}")
def delete_assets_music(filename: str):
    filename = os.path.basename(filename)
    dest_path = os.path.join(MUSIC_DIR, filename)
    if not os.path.exists(dest_path):
        raise HTTPException(status_code=404, detail="Music file not found.")

    try:
        os.remove(dest_path)
        if shared_state.state["bg_music_path"] == dest_path:
            shared_state.state["bg_music_path"] = None
        return {"status": "success", "message": "Music deleted successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete music: {e}")


@app.get("/api/gallery")
def list_gallery_videos():
    if not os.path.exists(OUTPUT_DIR):
        return []
    videos = []
    for f in os.listdir(OUTPUT_DIR):
        if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.avi')):
            fp = os.path.join(OUTPUT_DIR, f)
            size = os.path.getsize(fp)
            modified = os.path.getmtime(fp)

            # Read duration using basic check or placeholder
            duration = None
            try:
                from generator import get_video_info
                info = get_video_info(fp, suppress_errors=True)
                duration = info.get("duration")
            except Exception:
                pass

            videos.append({
                "filename": f,
                "url": f"/output/{f}",
                "size": size,
                "modified": modified,
                "duration": duration
            })
    # Sort by newest first
    videos.sort(key=lambda x: x["modified"], reverse=True)
    return videos


@app.delete("/api/gallery/{filename}")
def delete_gallery_video(filename: str):
    filename = os.path.basename(filename)
    dest_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(dest_path):
        raise HTTPException(
            status_code=404, detail="Compiled video file not found.")

    try:
        os.remove(dest_path)
        return {"status": "success", "message": "Compiled video deleted successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete video: {e}")


@app.post("/api/pexels/search")
def search_pexels_api(data: PexelsSearchRequest):
    pexels_key = shared_state.settings.get("pexels_api_key", "").strip()
    if not pexels_key:
        raise HTTPException(
            status_code=400, detail="Pexels API Key is missing. Add it in the Settings panel.")

    query = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&orientation=portrait&per_page=12"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": pexels_key,
            "User-Agent": "Mozilla/5.0"
        }
    )

    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            videos_raw = res_data.get("videos", [])

            results = []
            for v in videos_raw:
                # Find download vertical video links
                video_files = v.get("video_files", [])
                vertical_files = [vf for vf in video_files if (
                    vf.get("width") or 0) < (vf.get("height") or 0)]
                files_to_check = vertical_files if vertical_files else video_files

                if not files_to_check:
                    continue

                best_file = sorted(files_to_check, key=lambda x: x.get(
                    "width") or 0, reverse=True)[0]

                results.append({
                    "id": v.get("id"),
                    "thumbnail": v.get("image"),
                    "duration": v.get("duration"),
                    "user": v.get("user", {}).get("name", "Unknown Artist"),
                    "width": best_file.get("width"),
                    "height": best_file.get("height"),
                    "download_url": best_file.get("link")
                })
            return {"videos": results}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search Pexels: {str(e)}")


@app.post("/api/pexels/download")
def download_pexels_video(data: PexelsDownloadRequest, background_tasks: BackgroundTasks):
    pexels_key = shared_state.settings.get("pexels_api_key", "").strip()
    if not pexels_key:
        raise HTTPException(
            status_code=400, detail="Pexels API Key is missing.")

    clean_keyword = "".join(c for c in data.keyword.lower(
    ) if c.isalnum() or c == " ").replace(" ", "_")
    filename = f"pexels_{clean_keyword}_{data.video_id}.mp4"
    dest_path = os.path.join(VIDEOS_DIR, filename)

    def download_job(url, dest, pos):
        try:
            from generator import download_file
            download_file(url, dest, f"Pexels Video: {filename}")
            state_key = "bg_video_path" if pos == "top" else "bg_video_bottom_path"
            shared_state.state[state_key] = dest

            # Persist gui state to disk (lock to prevent concurrent write corruption)
            with _state_file_lock:
                with open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(shared_state.state, f, indent=2)

            logger.info(f"[Pexels Download] Successfully downloaded to {dest_path} and set as {pos} video.")
        except Exception as e:
            logger.error(f"[Pexels Download] Error downloading video: {e}")

    background_tasks.add_task(
        download_job, data.download_url, dest_path, data.position)
    return {"status": "pending", "message": "Download started in background.", "filename": filename}

@app.post("/api/youtube/download")
def download_youtube_video(data: YoutubeDownloadRequest, background_tasks: BackgroundTasks):
    url = data.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL is missing.")
    # Validate URL scheme to prevent SSRF attacks
    import urllib.parse as _urlparse
    _parsed = _urlparse.urlparse(url)
    if _parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid URL scheme. Only http/https URLs are allowed.")

    def download_job(yt_url, downscale):
        try:
            logger.info(f"[YouTube] Starting download for {yt_url} (downscale: {downscale})")
            import subprocess
            import time
            timestamp = int(time.time())
            filename_template = f"youtube_{timestamp}_%(title)s.%(ext)s"
            dest_path = os.path.join(VIDEOS_DIR, filename_template)
            
            cmd = ["yt-dlp", "--merge-output-format", "mp4", "--restrict-filenames"]
            if downscale:
                cmd.extend(["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best"])
            else:
                cmd.extend(["-f", "bestvideo+bestaudio/best"])
            
            cmd.extend(["-o", dest_path, yt_url])
            
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if process.returncode != 0:
                logger.error(f"[YouTube] Error downloading: {process.stderr}")
            else:
                logger.info(f"[YouTube] Successfully downloaded {yt_url}")
        except Exception as e:
            logger.error(f"[YouTube] Error downloading video: {e}")

    background_tasks.add_task(download_job, url, data.downscale)
    return {"status": "pending", "message": "YouTube download started in background."}

@app.post("/api/pexels/extract-keyword")
def extract_keyword_api():
    script = shared_state.state["script_text"].strip()
    if not script:
        raise HTTPException(
            status_code=400, detail="Script is empty. Please generate or edit a script first.")

    keyword = extract_keywords_from_script(script)
    if not keyword:
        keyword = "abstract loop"
    return {"keyword": keyword}


@app.post("/api/script/generate")
def generate_viral_script(data: ScriptGenerateRequest):
    # Set/override settings key
    api_key = shared_state.settings.get(
        "api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = shared_state.settings.get(
        "base_url") or os.environ.get("OPENAI_BASE_URL")

    opencode_key, _ = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and not base_url:
            base_url = "https://opencode.ai/zen/go/v1"

    if not api_key:
        raise HTTPException(
            status_code=400, detail="OpenAI/OpenCode API key is missing. Set it in Settings.")

    default_model = shared_state.settings.get("model", "gpt-4o-mini")
    model = data.model_override.strip() if (
        data.model_override and data.model_override.strip()) else default_model

    if not model:
        if base_url and "opencode.ai" in base_url:
            model = "deepseek-v4-flash"
        else:
            model = "gpt-4o-mini"

    if data.selected_voice:
        shared_state.state["selected_voice"] = data.selected_voice
        shared_state.state["loaded_preset_name"] = None

    logger.info(f"[AI Script] Generating script with model '{model}' for prompt: '{data.prompt}'")

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    max_words = shared_state.settings.get("max_words", 130)
    default_system_prompt = (
        "You are an elite TikTok and YouTube Shorts scriptwriter known for creating viral, high-retention content. "
        "Write a highly engaging vertical video script based on the user's topic.\n\n"
        "Strict Guidelines:\n"
        "1. The Hook (First 3s): Start immediately with a scroll-stopping statement, provocative question, or mind-blowing fact. No introductions.\n"
        "2. Format & Pacing: Keep it conversational, punchy, and fast-paced. Use short sentences. Eliminate all fluff.\n"
        "3. Length: Strictly under {max_words} words (approx. {max_words_seconds} seconds when spoken).\n"
        "4. Content: Structure with 3 key points or a rapid-fire narrative. Deliver value immediately. End with a strong, natural Call to Action (CTA).\n"
        "5. Tone: Sound authentic and human. Avoid robotic, academic, or overly dramatic AI clichés.\n"
        "6. Formatting: Output ONLY the exact spoken words. Do NOT include stage directions, timestamps, speaker tags, or brackets (e.g., no [Music], [Host], or [Visuals]).\n"
        "7. Chunks: Group every 2-4 sentences into a natural spoken chunk and separate each chunk with a blank line (\\n\\n). This improves voice audio quality significantly — do not skip this."
    )
    raw_system_prompt = shared_state.settings.get("system_prompt", default_system_prompt)
    try:
        system_prompt = raw_system_prompt.format(max_words=max_words, max_words_seconds=int(max_words / 2.3))
    except (KeyError, ValueError):
        # User's custom prompt contains literal {braces} — fall back to the raw string
        system_prompt = raw_system_prompt

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": data.prompt}
            ],
            temperature=0.7
        )
        script_text = response.choices[0].message.content.strip()
        shared_state.state["script_text"] = script_text

        # Save state to disk
        with open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(shared_state.state, f, indent=2)

        return {"status": "success", "script": script_text}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Script generation failed: {str(e)}")

# Video compilation runner thread task
def compile_worker():
    global compilation_in_progress, compilation_success

    while True:
        job = compilation_queue.get(block=True)
        if job is None:
            break

        custom_filename = job.get("custom_filename")
        state_snapshot = job.get("state_snapshot")

        compilation_in_progress = True
        compilation_success = False
        
        # Clear logs from the previous job and add a separator
        with _compile_log_lock:
            compilation_logs.clear()
            compilation_logs.append("=" * 50 + "\n")

        logger.info(f"[Compile Thread] Starting video compilation process (Queue size: {compilation_queue.qsize()})...")
        try:
            from gui.compiler import compile_video_flow
            # run compilation flow with skip_confirm=True
            success = compile_video_flow(
                skip_confirm=True, custom_output_filename=custom_filename, state_override=state_snapshot)
            compilation_success = success
            if success:
                logger.info("[Compile Thread] Compilation finished successfully!")
            else:
                logger.error("[Compile Thread] Compilation failed (returned False). Check logs above.")
        except Exception as e:
            logger.error(f"[Compile Thread] Crash during compilation: {e}")
            import traceback
            logger.exception("Exception occurred")
            compilation_success = False
        finally:
            compilation_in_progress = False
            compilation_queue.task_done()


@app.post("/api/compile")
def start_compilation(custom_filename: Optional[str] = Form(None)):
    global compilation_thread

    # Validate script and background video
    if not shared_state.state["script_text"].strip():
        raise HTTPException(
            status_code=400, detail="Script is empty. Please generate or write a script first.")
    if not shared_state.state["bg_video_path"]:
        raise HTTPException(
            status_code=400, detail="Top background video is not selected.")

    import copy
    state_snapshot = copy.deepcopy(shared_state.state)

    compilation_queue.put({
        "custom_filename": custom_filename.strip() if custom_filename else None,
        "state_snapshot": state_snapshot
    })

    # Guard with a lock to prevent double-spawning on concurrent requests
    with _compile_thread_lock:
        if compilation_thread is None or not compilation_thread.is_alive():
            compilation_thread = threading.Thread(
                target=compile_worker,
                daemon=True
            )
            compilation_thread.start()

    return {"status": "started", "message": f"Video compilation queued. (Queue size: {compilation_queue.qsize()})"}


@app.get("/api/compile/status")
def get_compilation_status():
    with _compile_log_lock:
        log_snapshot = "".join(compilation_logs)
    return {
        "in_progress": compilation_in_progress or not compilation_queue.empty(),
        "success": compilation_success,
        "logs": log_snapshot,
        "queue_size": compilation_queue.qsize()
    }


@app.post("/api/compile/cancel")
def cancel_compilation():
    # Since python threads cannot be killed easily, we notify the user.
    # In a real app we'd have a cancel flag, but compile_video does ffmpeg processes.
    # We can try to kill running ffmpeg subprocesses if we want, but letting it finish or notifying is safer.
    # We will log cancellation attempt.
    logger.info("[Compile Thread] Compilation cancellation requested (note: background processes will terminate on completion/next cycle).")
    return {"status": "success", "message": "Cancellation request received."}

# =========================================================
# BATCH GENERATION ENDPOINTS
# =========================================================


batch_state = {
    "in_progress": False,
    "num_shorts": 0,
    "progress_dict": {},
    "job_details": {},
    "should_cancel": False,
    "futures": [],
    "executor": None,
    "manager": None,
    "shared_progress": None
}


def batch_worker_thread(num_shorts):
    batch_state["in_progress"] = True
    batch_state["should_cancel"] = False

    try:
        from generator import unload_tts_model
        from gui.compiler import unload_whisper_model
        
        # Free up GPU memory from the main process before spawning workers
        unload_tts_model()
        unload_whisper_model()
        
        from gui.config import load_prompt_templates
        from gui.batch import orchestrate_batch_job

        templates = load_prompt_templates()
        presets = load_presets()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        api_key = shared_state.settings.get(
            "api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = shared_state.settings.get(
            "base_url") or os.environ.get("OPENAI_BASE_URL")
        opencode_key, _ = discover_opencode_keys()
        if not api_key:
            api_key = opencode_key
            if api_key and not base_url:
                base_url = "https://opencode.ai/zen/go/v1"

        model = "gpt-4o-mini"
        if base_url and "opencode.ai" in base_url:
            model = "deepseek-v4-flash"

        max_words = shared_state.settings.get("max_words", 130)
        default_system_prompt = (
            "You are an elite TikTok and YouTube Shorts scriptwriter known for creating viral, high-retention content. "
            "Write a highly engaging vertical video script based on the user's topic.\n\n"
            "Strict Guidelines:\n"
            "1. The Hook (First 3s): Start immediately with a scroll-stopping statement, provocative question, or mind-blowing fact. No introductions.\n"
            "2. Format & Pacing: Keep it conversational, punchy, and fast-paced. Use short sentences. Eliminate all fluff.\n"
            "3. Length: Strictly under {max_words} words (approx. {max_words_seconds} seconds when spoken).\n"
            "4. Content: Structure with 3 key points or a rapid-fire narrative. Deliver value immediately. End with a strong, natural Call to Action (CTA).\n"
            "5. Tone: Sound authentic and human. Avoid robotic, academic, or overly dramatic AI clichés.\n"
            "6. Formatting: Output ONLY the exact spoken words. Do NOT include stage directions, timestamps, speaker tags, or brackets (e.g., no [Music], [Host], or [Visuals]).\n"
            "7. Chunks: Group every 2-4 sentences into a natural spoken chunk and separate each chunk with a blank line (\\n\\n). This improves voice audio quality significantly — do not skip this."
        )
        raw_system_prompt = shared_state.settings.get("system_prompt", default_system_prompt)
        try:
            system_prompt = raw_system_prompt.format(max_words=max_words, max_words_seconds=int(max_words / 2.3))
        except (KeyError, ValueError):
            # User's custom prompt contains literal {braces} — fall back to raw string
            system_prompt = raw_system_prompt

        job_configs = {}
        batch_state["job_details"] = {}

        for i in range(1, num_shorts + 1):
            # Fallback values if templates/presets are empty
            template_title, prompt = (
                "Random", "A surprising fact about space.")
            if templates:
                template_title, prompt = random.choice(list(templates.items()))

            voice_name, voice_id = random.choice(shared_state.VOICES)

            preset_name = "default"
            preset = {}
            if presets:
                preset_name, preset = random.choice(list(presets.items()))

            is_split = random.choice([True, False])
            top_video = "random"
            bottom_video = "random" if is_split else None

            os.makedirs(MUSIC_DIR, exist_ok=True)
            music_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(
                ('.mp3', '.wav', '.m4a', '.ogg', '.flac'))]

            bg_music_preset = preset.get(
                "bg_music_path", "music/default_music.mp3")

            # Helper to resolve music safely
            def _resolve_music(path):
                if not path:
                    return None
                if os.path.exists(path):
                    return path
                if os.path.exists(os.path.join(BASE_DIR, path)):
                    return os.path.join(BASE_DIR, path)
                return path

            if music_files:
                chosen_music = os.path.join(
                    MUSIC_DIR, random.choice(music_files))
            else:
                chosen_music = _resolve_music(bg_music_preset)

            sub_font = random.choice(
                ["Arial", "Impact", "Georgia", "Courier New", "Times New Roman"])
            sub_size = random.randint(64, 84)
            sub_color = "#FFFFFF"
            vibrant_colors = ["#FFFF00", "#00FFFF", "#00FF00", "#FF00FF",
                              "#FF3333", "#FF9900", "#0080FF", "#FF55BB", "#33FF33"]
            sub_highlight = random.choice(vibrant_colors)
            sub_outline = "#000000"
            sub_outline_width = random.randint(4, 7)
            sub_bold = random.choice([True, False])

            enable_emojis = random.choice([True, False])
            word_pop = random.choice([True, False])
            word_pop_scale = round(random.uniform(
                1.10, 1.25), 2) if word_pop else 1.0
            inactive_dim = random.choice([True, False])
            inactive_alpha = random.choice(
                ["44", "66", "88", "AA"]) if inactive_dim else "FF"
            sub_animation_style = random.choice(["tiktok_pop", "karaoke_sweep", "bouncy_bounce", "cinematic_zoom",
                                                "glow_shake", "neon_flicker", "pulse_grow", "fade_in_slide", "typewriter_swipe"])

            script_temp = round(random.uniform(0.5, 0.9), 2)
            output_filename = f"rendered_batch_{timestamp}_{i}.mp4"

            # Determine words per screen strategy
            global_wps = shared_state.settings.get("words_per_screen", "3")
            if global_wps == "random":
                words_per_screen_choice = random.choice(["1", "3", "sentence"])
            else:
                words_per_screen_choice = global_wps

            job_configs[i] = {
                "index": i, "prompt": prompt, "voice_id": voice_id,
                "bg_video_path": top_video, "bg_video_bottom_path": bottom_video,
                "bg_music_path": chosen_music, "music_volume": preset.get("music_volume", 0.15),
                "voice_volume": preset.get("voice_volume", 1.0),
                "sub_font": sub_font, "sub_size": sub_size, "sub_color": sub_color,
                "sub_highlight": sub_highlight, "sub_outline": sub_outline,
                "sub_outline_width": sub_outline_width, "sub_bold": sub_bold,
                "enable_emojis": enable_emojis, "word_pop": word_pop,
                "word_pop_scale": word_pop_scale, "inactive_dim": inactive_dim,
                "inactive_alpha": inactive_alpha, "sub_uppercase": preset.get("sub_uppercase", True),
                "voice_speed": preset.get("voice_speed"),
                "sub_border_style": preset.get("sub_border_style", 1),
                "sub_shadow_width": preset.get("sub_shadow_width", 0),
                "sub_bg_color": preset.get("sub_bg_color", "#000000"),
                "sub_bg_alpha": preset.get("sub_bg_alpha", "80"),
                "single_word_mode": preset.get("single_word_mode", False),
                "words_per_screen": words_per_screen_choice,
                "emoji_position": preset.get("emoji_position", "above"),
                "emoji_font": preset.get("emoji_font", "Symbola"),
                "sub_animation_style": sub_animation_style, "script_temp": script_temp,
                "output_filename": output_filename, "model": model, "system_prompt": system_prompt,
                "settings": shared_state.settings.copy()
            }

            batch_state["job_details"][i] = {
                "topic": f"[{template_title}] {prompt[:35]}...",
                "voice": voice_name,
                "layout": "Split-Screen" if is_split else "Full Screen",
            }

        max_workers = shared_state.settings.get("max_workers")
        if max_workers:
            max_workers = int(max_workers)
        else:
            max_workers = max(1, min(2, (os.cpu_count() or 2) - 1))

        batch_state["manager"] = multiprocessing.Manager()
        batch_state["shared_progress"] = batch_state["manager"].dict()
        
        llm_max_workers = shared_state.settings.get("llm_max_workers")
        if llm_max_workers:
            try:
                llm_max_workers = int(llm_max_workers)
            except ValueError:
                llm_max_workers = 5
        else:
            llm_max_workers = 5

        for i in range(1, num_shorts + 1):
            batch_state["shared_progress"][i] = "Queued"

        ctx = multiprocessing.get_context('spawn')
        batch_state["executor"] = ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx, max_tasks_per_child=1)
        batch_state["llm_executor"] = ThreadPoolExecutor(max_workers=llm_max_workers)
        batch_state["orchestrator_executor"] = ThreadPoolExecutor(max_workers=num_shorts)
        
        batch_state["futures"] = []

        for i in range(1, num_shorts + 1):
            f = batch_state["orchestrator_executor"].submit(
                orchestrate_batch_job, 
                job_configs[i], 
                batch_state["shared_progress"],
                batch_state["llm_executor"],
                batch_state["executor"]
            )
            batch_state["futures"].append(f)

        # Polling loop
        while not all(f.done() for f in batch_state["futures"]):
            if batch_state["should_cancel"]:
                for f in batch_state["futures"]:
                    f.cancel()
                break
                
            # Check for any failed jobs to cancel the entire batch
            has_failures = False
            for f in batch_state["futures"]:
                if f.done():
                    try:
                        result = f.result()
                        if result and not result[1]: # result is (idx, success, msg)
                            has_failures = True
                            logger.error(f"[Batch Thread] Job failed with error: {result[2]}. Cancelling entire batch.")
                            break
                    except Exception as e:
                        has_failures = True
                        logger.error(f"[Batch Thread] Job failed with exception: {e}. Cancelling entire batch.")
                        break
            
            if has_failures:
                batch_state["should_cancel"] = True
                # Mark queued jobs as cancelled so the UI shows why they didn't run
                for i in range(1, num_shorts + 1):
                    if batch_state["shared_progress"].get(i) == "Queued":
                        batch_state["shared_progress"][i] = "Failed: Batch cancelled due to previous error"
                continue

            # Copy shared progress to regular dict for API access
            for i in range(1, num_shorts + 1):
                batch_state["progress_dict"][i] = batch_state["shared_progress"].get(
                    i, "Queued")
                if f"{i}_start" in batch_state["shared_progress"]:
                    batch_state["progress_dict"][f"{i}_start"] = batch_state["shared_progress"][f"{i}_start"]
                if f"{i}_end" in batch_state["shared_progress"]:
                    batch_state["progress_dict"][f"{i}_end"] = batch_state["shared_progress"][f"{i}_end"]

            time.sleep(0.5)

        # Final sync
        for i in range(1, num_shorts + 1):
            batch_state["progress_dict"][i] = batch_state["shared_progress"].get(
                i, "Queued")
            if f"{i}_start" in batch_state["shared_progress"]:
                batch_state["progress_dict"][f"{i}_start"] = batch_state["shared_progress"][f"{i}_start"]
            if f"{i}_end" in batch_state["shared_progress"]:
                batch_state["progress_dict"][f"{i}_end"] = batch_state["shared_progress"][f"{i}_end"]

    except Exception as e:
        logger.error(f"[Batch Thread] Crash: {e}")
        logger.exception("Exception occurred")
    finally:
        if batch_state.get("executor"):
            batch_state["executor"].shutdown(wait=True, cancel_futures=True)
        if batch_state.get("llm_executor"):
            batch_state["llm_executor"].shutdown(wait=True, cancel_futures=True)
        if batch_state.get("orchestrator_executor"):
            batch_state["orchestrator_executor"].shutdown(wait=True, cancel_futures=True)
        if batch_state.get("manager"):
            batch_state["manager"].shutdown()
        batch_state["in_progress"] = False


class BatchStartRequest(BaseModel):
    num_shorts: int = 5


@app.post("/api/batch/start")
def start_batch(data: BatchStartRequest):
    # Guard with a lock to prevent two concurrent requests both passing the in_progress check
    with _batch_lock:
        if batch_state["in_progress"]:
            raise HTTPException(
                status_code=400, detail="A batch job is already running.")
        # Claim the slot immediately so any concurrent request sees it as taken
        batch_state["in_progress"] = True

    num_shorts = data.num_shorts
    if num_shorts < 1 or num_shorts > 100:
        batch_state["in_progress"] = False  # Release on validation failure
        raise HTTPException(
            status_code=400, detail="Number of shorts must be between 1 and 100.")

    batch_state["num_shorts"] = num_shorts
    batch_state["progress_dict"].clear()

    t = threading.Thread(target=batch_worker_thread,
                         args=(num_shorts,), daemon=True)
    t.start()
    return {"status": "started", "message": f"Batch generation of {num_shorts} shorts started."}


@app.get("/api/batch/status")
def get_batch_status():
    from gui.batch import get_progress_percentage, format_elapsed

    jobs = []
    for i in range(1, batch_state["num_shorts"] + 1):
        status = batch_state["progress_dict"].get(i, "Queued")
        pct = get_progress_percentage(status)

        start_time = batch_state["progress_dict"].get(f"{i}_start")
        end_time = batch_state["progress_dict"].get(f"{i}_end")
        elapsed_str = "--"
        if start_time:
            duration = (end_time if end_time else time.time()) - start_time
            elapsed_str = format_elapsed(duration)
            if status == "Done":
                elapsed_str += " (Done)"

        detail = batch_state["job_details"].get(i, {})
        jobs.append({
            "id": i,
            "topic": detail.get("topic", "Unknown"),
            "voice": detail.get("voice", "Unknown"),
            "layout": detail.get("layout", "Unknown"),
            "status": status,
            "progress": pct if pct is not None else 0,
            "failed": pct is None,
            "elapsed": elapsed_str
        })

    return {
        "in_progress": batch_state["in_progress"],
        "num_shorts": batch_state["num_shorts"],
        "jobs": jobs,
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent
    }


@app.post("/api/batch/cancel")
def cancel_batch():
    if batch_state["in_progress"]:
        batch_state["should_cancel"] = True
        return {"status": "success", "message": "Cancellation requested. Waiting for active workers to terminate."}
    return {"status": "ignored", "message": "No active batch to cancel."}


@app.get("/{full_path:path}")
def catch_all(full_path: str):
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(BASE_DIR, "gui/static/index.html"))


if __name__ == "__main__":
    import uvicorn
    import psutil
    import logging
    
    class EndpointFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            if "GET /api/batch/status" in msg or "GET /api/compile/status" in msg or "/api/system_stats" in msg:
                return False
            return True

    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
    
    # Suppress asyncio SSL connection closed warnings
    logging.getLogger("asyncio").setLevel(logging.ERROR)
    
    # Kill only *known server processes* on port 5000 to avoid killing unrelated services
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                for conn in proc.net_connections(kind='inet'):
                    if conn.laddr.port == 5000:
                        proc_name = proc.name().lower()
                        # Only kill Python/server processes to avoid killing unrelated services
                        if any(n in proc_name for n in ('python', 'uvicorn', 'gunicorn', 'hypercorn')):
                            logger.info(f"Killing process {proc.pid} ({proc.name()}) using port 5000")
                            proc.kill()
                        else:
                            logger.warning(f"Port 5000 in use by non-server process {proc.pid} ({proc.name()}) — skipping.")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.info(f"Error while trying to free port 5000: {e}")

    # Load config port or default to 5000
    ssl_kwargs = {}
    if "--https" in sys.argv:
        if os.path.exists("cert.pem") and os.path.exists("key.pem"):
            ssl_kwargs["ssl_certfile"] = "cert.pem"
            ssl_kwargs["ssl_keyfile"] = "key.pem"
        else:
            logger.info("HTTPS requested but cert.pem or key.pem not found. Running in HTTP mode.")

    uvicorn.run(app, host="0.0.0.0", port=5000, **ssl_kwargs)
