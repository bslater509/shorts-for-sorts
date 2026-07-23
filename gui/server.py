import os
import sys

# Ensure parent directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import asyncio
import threading

import psutil
from fastapi import FastAPI, Header, HTTPException, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocketDisconnect

from gui.config import (
    FRONTEND_DIST_DIR,
    MUSIC_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
    VIDEOS_DIR,
    clear_cache,
    logger,
    load_settings,
)
from gui.media import stream_media
from gui.utils import check_system_dependencies, download_default_assets_if_empty
from gui.ws_manager import manager, notify_clients, set_main_loop

# Import all routers
from gui.routers.settings import router as settings_router
from gui.routers.assets import router as assets_router
from gui.routers.integrations import router as integrations_router
from gui.routers.batch import router as batch_router
from gui.routers.admin import router as admin_router

app = FastAPI(title="Shorts for Sorts Web GUI")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup events
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def save_event_loop():
    set_main_loop(asyncio.get_running_loop())


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


# ---------------------------------------------------------------------------
# WebSocket endpoints
# ---------------------------------------------------------------------------


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
        if not isinstance(e, WebSocketDisconnect):
            logger.debug(f"[WebSocket system_stats] Unexpected error: {e}")


# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------


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

# ---------------------------------------------------------------------------
# Media serving
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Static file serving + SPA catch-all
# ---------------------------------------------------------------------------

if os.path.exists(FRONTEND_DIST_DIR):
    app.mount(
        "/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST_DIR, "assets")), name="assets"
    )
    app.mount("/static", StaticFiles(directory=FRONTEND_DIST_DIR), name="static")
else:
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "gui/static")), name="static")


@app.get("/")
def get_root():
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(BASE_DIR, "gui/static/index.html"))


# ---------------------------------------------------------------------------
# Register route modules
# ---------------------------------------------------------------------------

app.include_router(settings_router)
app.include_router(assets_router)
app.include_router(integrations_router)
app.include_router(batch_router)
app.include_router(admin_router)


@app.get("/{full_path:path}")
def catch_all(full_path: str):
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(BASE_DIR, "gui/static/index.html"))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

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
