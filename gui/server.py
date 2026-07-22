import os
import sys

# Ensure parent directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import asyncio
import datetime
import json
import multiprocessing
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
    PexelsDownloadRequest,
    PexelsSearchRequest,
    PresetModel,
    SettingsModel,
    StateModel,
    TiktokUploadRequest,
    YoutubeDownloadRequest,
    YoutubeSearchRequest,
)
from gui.utils import (
    check_system_dependencies,
    download_default_assets_if_empty,
    get_active_llm_profile,
    resolve_preset_path,
)

THUMBNAIL_DIR = os.path.join(OUTPUT_DIR, "thumbnails")
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

GUI_STATE_FILE = os.path.join(BASE_DIR, "config", "gui_state.json")
BATCH_STATS_FILE = os.path.join(BASE_DIR, "config", "batch_stats.json")

# Locks for thread-safe access to shared mutable state
_batch_lock = threading.Lock()  # Guards batch_state["in_progress"] TOCTOU

app = FastAPI(title="Shorts for Sorts Web GUI")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_main_loop = None
manager = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

def notify_clients(event_type: str, status: str, message: str, level: str = "info", metadata: dict = None):
    if _main_loop is None or _main_loop.is_closed():
        return
    payload = {
        "event_type": event_type,
        "status": status,
        "message": message,
        "level": level,
        "metadata": metadata or {}
    }
    import asyncio
    asyncio.run_coroutine_threadsafe(manager.broadcast(payload), _main_loop)

@app.on_event("startup")
async def save_event_loop():
    global _main_loop
    import asyncio
    _main_loop = asyncio.get_running_loop()

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

@app.websocket("/api/notifications")
async def websocket_notifications(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)


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

            await websocket.send_json(
                {"cpu_percent": round(cpu_usage, 1), "memory_percent": round(memory_percent, 1)}
            )
    except Exception as e:
        # Silently ignore disconnections; log unexpected errors for diagnosis
        from fastapi.websockets import WebSocketDisconnect

        if not isinstance(e, WebSocketDisconnect):
            logger.debug(f"[WebSocket system_stats] Unexpected error: {e}")


def init_app_state():
    """Initializes the backend settings, dependencies, and default state."""
    clear_cache()
    try:
        check_system_dependencies()
    except Exception as e:
        logger.warning(f"System dependencies check failed: {e}")

    load_settings()
    download_default_assets_if_empty()


init_app_state()


@app.get("/videos/{filename:path}")
def serve_video(filename: str, range: str = Header(None)):
    safe_path = os.path.realpath(os.path.join(VIDEOS_DIR, filename))
    if not safe_path.startswith(os.path.realpath(VIDEOS_DIR)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return stream_media(safe_path, range)


@app.get("/music/{filename:path}")
def serve_music(filename: str, range: str = Header(None)):
    safe_path = os.path.realpath(os.path.join(MUSIC_DIR, filename))
    if not safe_path.startswith(os.path.realpath(MUSIC_DIR)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return stream_media(safe_path, range)


@app.get("/output/{filename:path}")
def serve_output(filename: str, range: str = Header(None)):
    safe_path = os.path.realpath(os.path.join(OUTPUT_DIR, filename))
    if not safe_path.startswith(os.path.realpath(OUTPUT_DIR)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return stream_media(safe_path, range)


FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "gui/frontend/dist")
if os.path.exists(FRONTEND_DIST_DIR):
    app.mount(
        "/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST_DIR, "assets")), name="assets"
    )
    app.mount("/static", StaticFiles(directory=FRONTEND_DIST_DIR), name="static")
else:
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "gui/static")), name="static")

# REST Endpoints


@app.get("/")
def get_root():
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(BASE_DIR, "gui/static/index.html"))


@app.get("/api/settings")
def get_api_settings():
    # reload settings from disk first
    load_settings()
    return shared_state.settings


@app.post("/api/settings")
def save_api_settings(data: SettingsModel):
    # Convert model to dict
    settings_dict = data.model_dump()

    success = save_settings(settings_dict)
    if success:
        return {"status": "success", "message": "Settings saved successfully."}
    else:
        raise HTTPException(status_code=500, detail="Failed to save settings to disk.")


@app.post("/api/llm/models")
def fetch_llm_models(data: FetchModelsRequest):
    api_key = data.api_key.strip() if data.api_key else os.environ.get("OPENAI_API_KEY", "")
    base_url = (
        data.base_url.strip()
        if data.base_url
        else os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required to fetch models.")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        models = client.models.list()
        # Sort models alphabetically
        model_ids = sorted([m.id for m in models.data])
        return {"status": "success", "models": model_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")


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
            status_code=400,
            detail=f"Preset '{name}' could not be deleted (might be builtin or not found).",
        )


@app.get("/api/state")
def get_api_state():
    return shared_state.state


@app.post("/api/state")
def save_api_state(data: StateModel):
    # Update global shared state
    for k, v in data.model_dump().items():
        shared_state.state[k] = v

    # Persist gui state to disk
    try:
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
        if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
            fp = os.path.join(VIDEOS_DIR, f)
            size = os.path.getsize(fp)
            modified = os.path.getmtime(fp)
            videos.append(
                {"filename": f, "url": f"/videos/{f}", "size": size, "modified": modified}
            )
    # Sort by modified time (newest first)
    videos.sort(key=lambda x: x["modified"], reverse=True)
    return videos


@app.post("/api/assets/videos")
def upload_assets_video(file: UploadFile = File(...)):
    safe = "".join(c for c in file.filename if c.isalnum() or c in (".", "_", "-"))
    filename = safe.lstrip(".")[:255] or "unnamed_file"
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Save the file to videos/
    dest_path = os.path.join(VIDEOS_DIR, filename)
    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"status": "success", "filename": filename, "url": f"/videos/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {e}")


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
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {e}")


@app.get("/api/assets/music")
def list_assets_music():
    if not os.path.exists(MUSIC_DIR):
        return []
    music = []
    for f in os.listdir(MUSIC_DIR):
        if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg", ".flac")):
            fp = os.path.join(MUSIC_DIR, f)
            size = os.path.getsize(fp)
            modified = os.path.getmtime(fp)
            music.append({"filename": f, "url": f"/music/{f}", "size": size, "modified": modified})
    # Sort by modified time
    music.sort(key=lambda x: x["modified"], reverse=True)
    return music


@app.post("/api/assets/music")
def upload_assets_music(file: UploadFile = File(...)):
    safe = "".join(c for c in file.filename if c.isalnum() or c in (".", "_", "-"))
    filename = safe.lstrip(".")[:255] or "unnamed_file"
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    dest_path = os.path.join(MUSIC_DIR, filename)
    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"status": "success", "filename": filename, "url": f"/music/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload music: {e}")


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
        raise HTTPException(status_code=500, detail=f"Failed to delete music: {e}")


@app.get("/api/gallery")
def list_gallery_videos():
    if not os.path.exists(OUTPUT_DIR):
        return []
    videos = []
    for f in os.listdir(OUTPUT_DIR):
        if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
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

            title = ""
            hashtags = ""
            txt_file = os.path.splitext(fp)[0] + ".txt"
            if os.path.exists(txt_file):
                try:
                    with open(txt_file, encoding="utf-8") as tf:
                        lines = tf.readlines()
                        if lines:
                            if any(re.match(r"^hashtags?\s*:", line, re.I) for line in lines):
                                # Old format: find line starting with Hashtag(s):
                                for line in lines:
                                    m = re.match(r"^hashtags?\s*:\s*(.*)", line, re.I)
                                    if m:
                                        hashtags = m.group(1).strip()
                                        break
                            else:
                                # New format: line 0 is title, line 1 is hashtags
                                if len(lines) >= 2:
                                    title = lines[0].strip()
                                    hashtags = lines[1].strip()
                except Exception:
                    pass

            # Thumbnail
            thumb_filename = os.path.splitext(f)[0] + ".jpg"
            thumbnail = f"/api/gallery/thumbnail/{thumb_filename}"

            videos.append(
                {
                    "filename": f,
                    "url": f"/output/{f}",
                    "size": size,
                    "modified": modified,
                    "duration": duration,
                    "title": title,
                    "hashtags": hashtags,
                    "thumbnail": thumbnail,
                }
            )
    # Sort by newest first
    videos.sort(key=lambda x: x["modified"], reverse=True)
    return videos


@app.delete("/api/gallery/{filename}")
def delete_gallery_video(filename: str):
    filename = os.path.basename(filename)
    dest_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(dest_path):
        raise HTTPException(status_code=404, detail="Compiled video file not found.")

    try:
        os.remove(dest_path)
        basename = os.path.splitext(filename)[0]
        # Remove thumbnail sidecar
        thumb_path = os.path.join(THUMBNAIL_DIR, basename + ".jpg")
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        # Remove metadata sidecar
        meta_path = os.path.join(OUTPUT_DIR, basename + ".txt")
        if os.path.exists(meta_path):
            os.remove(meta_path)
        return {"status": "success", "message": "Compiled video deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {e}")


@app.delete("/api/gallery")
def delete_all_gallery_videos():
    if not os.path.exists(OUTPUT_DIR):
        return {"status": "success", "message": "No videos to delete."}

    try:
        for f in os.listdir(OUTPUT_DIR):
            fp = os.path.join(OUTPUT_DIR, f)
            if os.path.isfile(fp):
                os.remove(fp)
        return {"status": "success", "message": "All generated videos deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete all videos: {e}")


@app.get("/api/gallery/thumbnail/{filename}")
def get_gallery_thumbnail(filename: str):
    """Serve or generate a thumbnail for a gallery video."""
    # Sanitize filename to prevent path traversal
    filename = os.path.basename(filename)
    thumb_path = os.path.join(THUMBNAIL_DIR, filename)

    # If thumbnail already exists, serve it
    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")

    # Try to generate from corresponding video in output/
    base_name = os.path.splitext(filename)[0]
    for ext in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
        video_path = os.path.join(OUTPUT_DIR, base_name + ext)
        if os.path.exists(video_path):
            if generate_video_thumbnail(video_path, thumb_path) and os.path.exists(thumb_path):
                return FileResponse(thumb_path, media_type="image/jpeg")
            break

    raise HTTPException(status_code=404, detail="Thumbnail not found")


@app.post("/api/pexels/search")
def search_pexels_api(data: PexelsSearchRequest):
    pexels_key = shared_state.settings.get("pexels_api_key", "").strip()
    if not pexels_key:
        raise HTTPException(
            status_code=400, detail="Pexels API Key is missing. Add it in the Settings panel."
        )

    query = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&orientation=portrait&per_page=12"
    req = urllib.request.Request(
        url, headers={"Authorization": pexels_key, "User-Agent": "Mozilla/5.0"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            videos_raw = res_data.get("videos", [])

            results = []
            for v in videos_raw:
                # Find download vertical video links
                video_files = v.get("video_files", [])
                vertical_files = [
                    vf for vf in video_files if (vf.get("width") or 0) < (vf.get("height") or 0)
                ]
                files_to_check = vertical_files if vertical_files else video_files

                if not files_to_check:
                    continue

                best_file = sorted(files_to_check, key=lambda x: x.get("width") or 0, reverse=True)[
                    0
                ]

                results.append(
                    {
                        "id": v.get("id"),
                        "thumbnail": v.get("image"),
                        "duration": v.get("duration"),
                        "user": v.get("user", {}).get("name", "Unknown Artist"),
                        "width": best_file.get("width"),
                        "height": best_file.get("height"),
                        "download_url": best_file.get("link"),
                    }
                )
            return {"videos": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search Pexels: {str(e)}")


@app.post("/api/pexels/download")
def download_pexels_video(data: PexelsDownloadRequest, background_tasks: BackgroundTasks):
    pexels_key = shared_state.settings.get("pexels_api_key", "").strip()
    if not pexels_key:
        raise HTTPException(status_code=400, detail="Pexels API Key is missing.")

    clean_keyword = "".join(c for c in data.keyword.lower() if c.isalnum() or c == " ").replace(
        " ", "_"
    )
    filename = f"pexels_{clean_keyword}_{data.video_id}.mp4"
    dest_path = os.path.join(VIDEOS_DIR, filename)

    def download_job(url, dest, pos):
        try:
            from generator import download_file

            logger.info(f"[Pexels Download] Starting download for {url} as {pos} video.")
            notify_clients("pexels_download", "info", f"Pexels download started for {pos} video...", level="info")

            download_file(url, dest, f"Pexels Video: {filename}")
            state_key = "bg_video_path" if pos == "top" else "bg_video_bottom_path"
            shared_state.state[state_key] = dest

            # Persist gui state to disk
            with open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(shared_state.state, f, indent=2)

            logger.info(
                f"[Pexels Download] Successfully downloaded to {dest_path} and set as {pos} video."
            )
            notify_clients("pexels_download", "success", f"Pexels video downloaded and set as {pos} video!", level="success")
        except Exception as e:
            logger.error(f"[Pexels Download] Error downloading video: {e}")
            notify_clients("pexels_download", "error", f"Pexels download failed: {e}", level="error")

    background_tasks.add_task(download_job, data.download_url, dest_path, data.position)
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
        raise HTTPException(
            status_code=400, detail="Invalid URL scheme. Only http/https URLs are allowed."
        )

    def download_job(yt_url, downscale):
        try:
            logger.info(f"[YouTube] Starting download for {yt_url} (downscale: {downscale})")
            notify_clients("youtube_download", "info", "YouTube download started...", level="info")
            import subprocess
            import time

            timestamp = int(time.time())
            filename_template = f"youtube_{timestamp}_%(title)s.%(ext)s"
            dest_path = os.path.join(VIDEOS_DIR, filename_template)

            cmd = ["yt-dlp", "--merge-output-format", "mp4", "--restrict-filenames", "--newline"]
            if downscale:
                cmd.extend(["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best"])
            else:
                cmd.extend(["-f", "bestvideo+bestaudio/best"])

            cmd.extend(["-o", dest_path, yt_url])

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            
            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info(f"[YouTube] {line}")
                    
            process.wait()
            
            if process.returncode != 0:
                logger.error(f"[YouTube] Error downloading: yt-dlp exited with code {process.returncode}")
                notify_clients("youtube_download", "error", "YouTube download failed.", level="error")
            else:
                logger.info(f"[YouTube] Successfully downloaded {yt_url}")
                notify_clients("youtube_download", "success", "YouTube download completed!", level="success")
        except Exception as e:
            logger.error(f"[YouTube] Error downloading video: {e}")
            notify_clients("youtube_download", "error", f"YouTube download error: {e}", level="error")

    background_tasks.add_task(download_job, url, data.downscale)
    return {"status": "pending", "message": "YouTube download started in background."}


@app.post("/api/youtube/search")
def search_youtube_api(data: YoutubeSearchRequest):
    query = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    try:
        import subprocess
        import json
        cmd = ["yt-dlp", f"ytsearch{data.limit}:{query}", "--dump-json", "--no-playlist", "--default-search", "ytsearch", "--ignore-errors"]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        results = []
        for line in process.stdout.splitlines():
            if not line.strip(): continue
            try:
                info = json.loads(line)
                
                # Format duration string
                duration_sec = info.get("duration", 0)
                if duration_sec:
                    mins, secs = divmod(duration_sec, 60)
                    duration_str = f"{int(mins)}:{int(secs):02d}"
                else:
                    duration_str = "Unknown"
                    
                results.append({
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "duration": duration_sec,
                    "duration_str": duration_str,
                    "url": info.get("webpage_url") or f"https://www.youtube.com/watch?v={info.get('id')}",
                    "uploader": info.get("uploader", "Unknown Channel"),
                    "thumbnail": info.get("thumbnail") or (info.get("thumbnails", [{}])[-1].get("url") if info.get("thumbnails") else None)
                })
            except Exception as e:
                logger.warning(f"Error parsing yt-dlp line: {e}")
                pass
                
        return {"videos": results}
    except Exception as e:
        logger.error(f"[YouTube Search] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search YouTube: {str(e)}")


@app.post("/api/tiktok/upload")
def upload_tiktok_video(data: TiktokUploadRequest, background_tasks: BackgroundTasks):
    sessionid = shared_state.settings.get("tiktok_sessionid", "").strip()
    if not sessionid:
        raise HTTPException(
            status_code=400, detail="TikTok session ID is missing. Add it in Settings."
        )

    video_path = os.path.join(OUTPUT_DIR, data.filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    def upload_job():
        try:
            logger.info(f"[TikTok] Starting background upload for {data.filename}")
            import asyncio

            from gui.tiktok_uploader import upload_video

            asyncio.run(upload_video(sessionid, video_path, data.description, data.visibility))
            logger.info(f"[TikTok] Successfully uploaded {data.filename}")
        except Exception as e:
            logger.error(f"[TikTok] Upload failed: {e}")

    background_tasks.add_task(upload_job)
    return {"status": "pending", "message": "TikTok upload started in background."}


@app.post("/api/tiktok/login")
def login_tiktok_browser():
    try:
        logger.info("[TikTok] Launching browser for login...")
        import asyncio

        from gui.tiktok_uploader import login_to_tiktok

        # Run in a separate thread so we don't block the async event loop of fastapi
        def run_login():
            try:
                sid = asyncio.run(login_to_tiktok())
                if sid:
                    shared_state.settings["tiktok_sessionid"] = sid
                    save_settings(shared_state.settings)
                    logger.info("[TikTok] Login successful, saved sessionid.")
                    logger.warning(
                        "[TikTok] Session ID stored in plaintext in config/settings.json. "
                        "Keep this file secure and do not commit it."
                    )
                else:
                    logger.warning("[TikTok] Login finished but no sessionid was found.")
            except Exception as e:
                logger.error(f"[TikTok] Error during login: {e}")

        threading.Thread(target=run_login, daemon=True).start()
        return {
            "status": "pending",
            "message": "Browser opened for TikTok login. Please complete login in the new window.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open login browser: {e}")


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
    "shared_progress": None,
    "batch_results": [],
    "failed_job_configs": [],
    "max_workers": 1,
    "llm_max_workers": 5,
    "_smoothed_eta": {},
    "_phase_weights": None,
}
_batch_state_lock = threading.RLock()


def _resolve_worker_count(key, default, min_val=1):
    """Resolve a worker count from settings with a fallback default."""
    val = shared_state.settings.get(key)
    if val:
        try:
            return max(min_val, int(val))
        except (ValueError, TypeError):
            return default
    return default


# Video pipeline phases (sequential, after LLM) — used for time-weighted progress
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
    import time
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

        if batch_ratios and job_count >= 1:
            sample_count = job_count
            prev_avg_llm = stored_data.get("avg_llm_duration")
            prev_avg_video = stored_data.get("avg_video_duration")
            try:
                if os.path.exists(BATCH_STATS_FILE):
                    with open(BATCH_STATS_FILE) as f:
                        raw = json.load(f)
                    sample_count = raw.get("sample_count", 0) + job_count
                    if "avg_llm_duration" in raw:
                        prev_avg_llm = raw["avg_llm_duration"]
                    if "avg_video_duration" in raw:
                        prev_avg_video = raw["avg_video_duration"]
            except Exception:
                sample_count = job_count

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

            _save_phase_weights(merged, sample_count, merged_avg_llm, merged_avg_video)

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
        if new_job_stats:
            per_job_stats = list(batch_state.get("_per_job_stats", []))
            per_job_stats.extend(new_job_stats)
            _save_phase_weights(
                merged, sample_count,
                avg_llm_duration=merged_avg_llm, avg_video_duration=merged_avg_video,
                per_job_stats=per_job_stats,
            )

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


@app.get("/api/prompts")
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


@app.post("/api/batch/start")
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


@app.get("/api/batch/status")
def get_batch_status():
    from gui.batch import get_progress_percentage

    with _batch_state_lock:
        # Compute stats from completed jobs
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

        smoothed_etas = batch_state.get("_smoothed_eta", {})
        phase_weights = batch_state.get("_phase_weights")

        jobs = []
        for i in range(1, batch_state["num_shorts"] + 1):
            status = batch_state["progress_dict"].get(i, "Queued")
            pct = get_progress_percentage(status)

            start_time = batch_state["progress_dict"].get(f"{i}_start")
            end_time = batch_state["progress_dict"].get(f"{i}_end")

            # Gather phase entry timestamps for this job
            job_phase_times = {}
            for suffix in _PHASE_TRACKING_KEYS:
                val = batch_state["progress_dict"].get(f"{i}{suffix}")
                if val:
                    job_phase_times[suffix] = val

            eta_str, eta_seconds, elapsed_str, eta_llm, eta_video = _compute_eta(
                start_time, end_time, pct, status,
                job_phase_times, avg_completion_time, smoothed_etas, i,
                phase_weights=phase_weights,
                avg_llm_duration=batch_state.get("_avg_llm_duration"),
                avg_video_duration=batch_state.get("_avg_video_duration"),
                job_features=batch_state.get("_job_features", {}).get(i),
                per_job_stats=batch_state.get("_per_job_stats"),
            )

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
                    "eta_llm": round(eta_llm, 1) if eta_llm > 0 else 0,
                    "eta_video": round(eta_video, 1) if eta_video > 0 else 0,
                }
            )

        in_progress = batch_state["in_progress"]
        num_shorts = batch_state["num_shorts"]
        max_workers = batch_state.get("max_workers", 1)
        llm_max_workers = batch_state.get("llm_max_workers", 5)

        # Pipeline-aware global ETA
        # LLM runs in parallel (llm_max_workers), video runs sequentially (max_workers).
        # Total remaining ≈ sum(LLM remaining) / llm_max_workers + sum(video remaining) / max_workers
        avg_llm_dur = batch_state.get("_avg_llm_duration", 30) or 30
        avg_video_dur = batch_state.get("_avg_video_duration", 60) or 60
        total_llm = 0.0
        total_video = 0.0
        for j in jobs:
            s = j["status"]
            if s == "Done" or s.startswith("Failed"):
                continue
            if s != "Queued" and j.get("eta_llm") is not None:
                total_llm += j["eta_llm"]
                total_video += j["eta_video"]
            else:
                total_llm += avg_llm_dur
                total_video += avg_video_dur
        global_eta_seconds = (total_llm / max(1, llm_max_workers)) + (total_video / max(1, max_workers))

    return {
        "in_progress": in_progress,
        "num_shorts": num_shorts,
        "jobs": jobs,
        "max_workers": max_workers,
        "global_eta_seconds": round(global_eta_seconds, 1),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "progress_segments": [
            {"name": "LLM", "start": 0, "end": 20},
            {"name": "Voice", "start": 20, "end": 45},
            {"name": "Transcribe", "start": 45, "end": 55},
            {"name": "Render", "start": 55, "end": 100},
        ],
    }


@app.get("/api/batch/job/{job_id}")
def get_batch_job_detail(job_id: int):
    from gui.batch import get_progress_percentage

    with _batch_state_lock:
        # Check if the job exists
        if job_id < 1 or job_id > batch_state["num_shorts"]:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get progress info
        status = batch_state["progress_dict"].get(job_id, "Unknown")
        pct = get_progress_percentage(status)

        start_time = batch_state["progress_dict"].get(f"{job_id}_start")
        end_time = batch_state["progress_dict"].get(f"{job_id}_end")

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

        # Gather phase entry timestamps for this job
        job_phase_times = {}
        for suffix in _PHASE_TRACKING_KEYS:
            val = batch_state["progress_dict"].get(f"{job_id}{suffix}")
            if val:
                job_phase_times[suffix] = val

        smoothed_etas = batch_state.get("_smoothed_eta", {})
        phase_weights = batch_state.get("_phase_weights")
        eta_str, eta_seconds, elapsed_str, eta_llm, eta_video = _compute_eta(
            start_time, end_time, pct, status,
            job_phase_times, avg_completion_time, smoothed_etas, job_id,
            phase_weights=phase_weights,
            avg_llm_duration=batch_state.get("_avg_llm_duration"),
            avg_video_duration=batch_state.get("_avg_video_duration"),
            job_features=batch_state.get("_job_features", {}).get(job_id),
            per_job_stats=batch_state.get("_per_job_stats"),
        )

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


@app.post("/api/batch/cancel")
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


@app.post("/api/batch/retry-failed")
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


@app.get("/api/batch/report")
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


@app.post("/api/restart")
def restart_server(request: Request, background_tasks: BackgroundTasks):
    admin_token = shared_state.settings.get("admin_token")
    if admin_token:
        req_token = request.headers.get("X-Admin-Token", "")
        if req_token != admin_token:
            raise HTTPException(status_code=403, detail="Invalid admin token")
    import os
    import subprocess
    import sys
    import time

    def restart():
        frontend_dir = os.path.join(BASE_DIR, "gui/frontend")
        package_json = os.path.join(frontend_dir, "package.json")
        if os.path.exists(package_json):
            logger.info("Rebuilding frontend...")
            npm = "npm.cmd" if sys.platform == "win32" else "npm"
            result = subprocess.run(
                [npm, "run", "build"], cwd=frontend_dir, capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                logger.error(f"Frontend rebuild failed: {result.stderr.strip()}")
                return
            logger.info("Frontend rebuilt successfully.")
        else:
            logger.info("No frontend source found — skipping rebuild.")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    background_tasks.add_task(restart)
    return {"status": "restarting"}


@app.get("/api/batch/stats")
def get_batch_stats():
    try:
        if os.path.exists(BATCH_STATS_FILE):
            with open(BATCH_STATS_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "phase_ratios": dict(DEFAULT_PHASE_WEIGHTS),
        "sample_count": 0,
        "avg_llm_duration": None,
        "avg_video_duration": None,
        "per_job_stats": [],
    }


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/{full_path:path}")
def catch_all(full_path: str):
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(BASE_DIR, "gui/static/index.html"))


if __name__ == "__main__":
    import logging

    import uvicorn

    class EndpointFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            return not ("GET /api/batch/status" in msg or "GET /api/compile/status" in msg or "/api/system_stats" in msg)

    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

    # Suppress asyncio SSL connection closed warnings
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    # Kill only *known server processes* on port 5000 to avoid killing unrelated services
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                for conn in proc.net_connections(kind="inet"):
                    if conn.laddr.port == 5000:
                        proc_name = proc.name().lower()
                        # Only kill Python/server processes to avoid killing unrelated services
                        if any(
                            n in proc_name for n in ("python", "uvicorn", "gunicorn", "hypercorn")
                        ):
                            logger.info(
                                f"Killing process {proc.pid} ({proc.name()}) using port 5000"
                            )
                            proc.kill()
                        else:
                            logger.warning(
                                f"Port 5000 in use by non-server process {proc.pid} ({proc.name()}) — skipping."
                            )
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
