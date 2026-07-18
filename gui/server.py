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

THUMBNAIL_DIR = os.path.join(OUTPUT_DIR, "thumbnails")
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# Locks for thread-safe access to shared mutable state
_compile_log_lock = threading.Lock()  # Guards compilation_logs list
_compile_thread_lock = threading.Lock()  # Guards compilation_thread spawn
_state_file_lock = threading.Lock()  # Guards GUI_STATE_FILE writes
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

@app.on_event("startup")
async def download_emoji_styles():
    import threading
    from gui.emoji_downloader import ensure_emoji_styles
    # Run in a background thread so we don't block server startup
    threading.Thread(target=ensure_emoji_styles, daemon=True).start()
    logger.info("Started background task to download emoji styles.")


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


@app.websocket("/api/terminal")
async def websocket_terminal(websocket: WebSocket):
    await websocket.accept()

    # Create a pseudo-terminal
    shell_cmd = os.environ.get("SHELL", "/bin/bash")
    tmux_path = shutil.which("tmux")
    
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    # Clear force_color from env to let programs decide
    env.pop("NO_COLOR", None)

    pid, fd = pty.fork()
    if pid == 0:
        # Child: launch the shell in the project root
        os.chdir(BASE_DIR)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_DFL)
            
        if tmux_path:
            # -A: attach to session if it exists, or create if it doesn't
            os.execve(tmux_path, ["tmux", "new", "-A", "-s", "web_gui"], env)
        else:
            os.execve(shell_cmd, [shell_cmd, "-i"], env)

    loop = asyncio.get_running_loop()
    should_stop = threading.Event()

    def blocking_read():
        try:
            return os.read(fd, 4096)
        except OSError:
            return b""

    async def read_from_pty():
        while not should_stop.is_set():
            data = await loop.run_in_executor(None, blocking_read)
            if not data:
                break
            try:
                await websocket.send_json({"type": "output", "data": data.decode("utf-8", errors="replace")})
            except Exception:
                break
        should_stop.set()

    async def read_from_ws():
        try:
            while not should_stop.is_set():
                msg = await websocket.receive_json()
                msg_type = msg.get("type")
                if msg_type == "input":
                    os.write(fd, msg["data"].encode())
                elif msg_type == "resize":
                    cols = max(1, int(msg.get("cols", 80)))
                    rows = max(1, int(msg.get("rows", 24)))
                    winsize = struct.pack("HHHH", rows, cols, 0, 0)
                    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
                    # Also signal SIGWINCH so programs like tmux pick it up
                    try:
                        os.kill(pid, signal.SIGWINCH)
                    except OSError:
                        pass
                elif msg_type == "close":
                    break
                elif msg_type == "get_active_command":
                    try:
                        cmd = ["tmux", "display-message", "-t", "web_gui", "-p", "-F", "#{pane_current_command}"]
                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL
                        )
                        stdout, _ = await proc.communicate()
                        if proc.returncode == 0:
                            active_cmd = stdout.decode("utf-8").strip()
                            await websocket.send_json({"type": "active_command", "data": active_cmd})
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            should_stop.set()

    pty_task = asyncio.create_task(read_from_pty())
    ws_task = asyncio.create_task(read_from_ws())

    try:
        await asyncio.wait([pty_task, ws_task], return_when=asyncio.FIRST_COMPLETED)
    finally:
        should_stop.set()
        for task in [pty_task, ws_task]:
            if not task.done():
                task.cancel()
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass


# Persistence path for GUI Session State
GUI_STATE_FILE = os.path.join(CONFIG_DIR, "gui_state.json")

# Server-side compilation tracking
compilation_in_progress = False
compilation_success = False
compilation_logs = []
compilation_thread = None
compilation_queue = queue.Queue()
_compile_status_lock = threading.RLock()

# Custom Stdout redirector to capture compilation logs
original_stdout = sys.stdout
original_stderr = sys.stderr


class WebStdoutRedirector:
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, text):
        self.original_stream.write(text)
        with _compile_log_lock:
            if compilation_in_progress:
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
            with open(GUI_STATE_FILE, encoding="utf-8") as f:
                saved_state = json.load(f)
                # Filter saved keys to match key structure in shared_state.state
                for k, v in saved_state.items():
                    if k in shared_state.state:
                        shared_state.state[k] = v
            # Resolve relative paths after loading saved state
            for path_key in ("bg_video_path", "bg_video_bottom_path", "bg_music_path"):
                val = shared_state.state.get(path_key)
                if val and val != "random":
                    shared_state.state[path_key] = resolve_preset_path(val)
        except Exception as e:
            logger.error(f"Failed to load gui_state.json: {e}")


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

    opencode_key, _ = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and (not base_url or base_url == "https://api.openai.com/v1"):
            base_url = "https://opencode.ai/zen/go/v1"

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

    # Persist gui state to disk (lock to prevent concurrent write corruption)
    try:
        with _state_file_lock, open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
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

            # Persist gui state to disk (lock to prevent concurrent write corruption)
            with _state_file_lock, open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
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


@app.post("/api/pexels/extract-keyword")
def extract_keyword_api():
    script = shared_state.state["script_text"].strip()
    if not script:
        raise HTTPException(
            status_code=400, detail="Script is empty. Please generate or edit a script first."
        )

    keyword = extract_keywords_from_script(script)
    if not keyword:
        keyword = "abstract loop"
    return {"keyword": keyword}


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


@app.post("/api/script/generate")
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


@app.post("/api/script/generate/stream")
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


# Video compilation runner thread task
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


@app.post("/api/compile")
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


@app.get("/api/compile/status")
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


@app.post("/api/compile/cancel")
def cancel_compilation():
    # Since python threads cannot be killed easily, we notify the user.
    # In a real app we'd have a cancel flag, but compile_video does ffmpeg processes.
    # We can try to kill running ffmpeg subprocesses if we want, but letting it finish or notifying is safer.
    # We will log cancellation attempt.
    logger.info(
        "[Compile Thread] Compilation cancellation requested (note: background processes will terminate on completion/next cycle)."
    )
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
    "shared_progress": None,
    "batch_results": [],
    "failed_job_configs": [],
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
                    "enable_color_emoji": shared_state.settings.get("enable_color_emoji", True),
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


@app.get("/api/batch/job/{job_id}")
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


@app.post("/api/preview_animation")
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
