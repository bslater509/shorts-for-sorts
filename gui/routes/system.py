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

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "gui/frontend/dist")
THUMBNAIL_DIR = os.path.join(OUTPUT_DIR, "thumbnails")

@router.websocket("/api/notifications")
async def websocket_notifications(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)



@router.websocket("/api/system_stats")
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



@router.websocket("/api/terminal")
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



@router.get("/")
def get_root():
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(BASE_DIR, "gui/static/index.html"))



@router.post("/api/log")
def log_from_client(log: LogMessageRequest):
    if log.level == "error":
        logger.error(f"[Frontend] {log.message}")
    elif log.level == "warn":
        logger.warning(f"[Frontend] {log.message}")
    else:
        logger.info(f"[Frontend] {log.message}")
    return {"status": "success"}



@router.post("/api/restart")
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
        executable = sys.executable or "python3"
        args = [executable] + sys.argv
        try:
            os.execv(executable, args)
        except FileNotFoundError:
            os.execvp(executable, args)

    background_tasks.add_task(restart)
    return {"status": "restarting"}



@router.get("/api/health")
def health_check():
    return {"status": "ok"}



@router.get("/{full_path:path}")
def catch_all(full_path: str):
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(BASE_DIR, "gui/static/index.html"))



@router.on_event("startup")
async def save_event_loop():
    global _main_loop
    import asyncio
    _main_loop = asyncio.get_running_loop()


@router.on_event("startup")
async def cleanup_temp_dir():
    try:
        for f in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, f)
            if os.path.isfile(file_path):
                os.remove(file_path)
        logger.info("Cleaned up orphaned files in temp directory on startup.")
    except Exception as e:
        logger.warning(f"Failed to clean temp directory on startup: {e}")


@router.on_event("startup")
async def download_emoji_styles():
    import threading
    from gui.emoji_downloader import ensure_emoji_styles
    # Run in a background thread so we don't block server startup
    threading.Thread(target=ensure_emoji_styles, daemon=True).start()
    logger.info("Started background task to download emoji styles.")



