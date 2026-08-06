"""FastAPI web server for the Shorts for Sorts GUI.

Handles startup initialisation, WebSocket connections for notifications
and system stats, media file serving, SPA routing, and module registration.
"""

from __future__ import annotations

import os
import sys
from typing import Any

# Ensure parent directory is in sys.path
BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import asyncio
import logging

import psutil
import uvicorn
from fastapi import FastAPI, Header, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocketDisconnect

import gui.thumbnail_cache as thumbnail_cache
from gui.config import (
    FRONTEND_DIST_DIR,
    MUSIC_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
    VIDEOS_DIR,
    clear_cache,
    load_settings,
    logger,
)
from gui.media import stream_media
from gui.routers.admin import router as admin_router
from gui.routers.assets import router as assets_router
from gui.routers.batch import router as batch_router
from gui.routers.integrations import router as integrations_router
from gui.routers.settings import router as settings_router
from gui.routers.schedule import router as schedule_router
from gui.routers.tiktok import router as tiktok_router
from gui.utils import check_system_dependencies, download_default_assets_if_empty
from gui.ws_manager import manager, set_main_loop

# --- Application ---

app: FastAPI = FastAPI(title="Shorts for Sorts Web GUI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Constants ---

POLL_INTERVAL_SECONDS: float = 1.0
"""Interval (seconds) for system-stats WebSocket updates."""

SYSTEM_STATS_PORT: int = 5000
"""Default port for the server."""

# Process name substrings used when freeing the port
SERVER_PROCESS_NAMES: tuple[str, ...] = (
    "python",
    "uvicorn",
    "gunicorn",
    "hypercorn",
)

# uvicorn access log paths to filter from noise
NOISY_LOG_PATHS: tuple[str, ...] = (
    "/api/batch/status",
    "/api/compile/status",
    "/api/system_stats",
)


# ---------------------------------------------------------------------------
# Startup events
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def save_event_loop() -> None:
    """Store the running event loop reference for WebSocket notification scheduling."""
    set_main_loop(asyncio.get_running_loop())


@app.on_event("startup")
async def cleanup_temp_dir() -> None:
    """Remove orphaned temp files on startup."""
    try:
        for f in os.listdir(TEMP_DIR):
            file_path: str = os.path.join(TEMP_DIR, f)
            if os.path.isfile(file_path):
                os.remove(file_path)
        logger.info("Cleaned up orphaned files in temp directory on startup.")
    except Exception as e:
        logger.warning("Failed to clean temp directory on startup: %s", e)


@app.on_event("startup")
async def start_thumbnail_worker() -> None:
    """Start the background thumbnail worker and enqueue a precache scan."""
    import threading

    thumbnail_cache.start_thumbnail_worker()
    threading.Thread(target=thumbnail_cache.precache_all, daemon=True).start()


@app.on_event("startup")
async def start_scheduler() -> None:
    """Start the background schedule-based batch runner."""
    from gui.scheduler import start_scheduler_thread

    start_scheduler_thread()


@app.on_event("shutdown")
async def stop_thumbnail_worker() -> None:
    """Gracefully stop the background thumbnail worker pool."""
    thumbnail_cache.stop_thumbnail_worker()


@app.on_event("shutdown")
async def stop_scheduler() -> None:
    """Gracefully stop the scheduler daemon thread."""
    from gui.scheduler import stop_scheduler_thread

    stop_scheduler_thread()


# ---------------------------------------------------------------------------
# WebSocket endpoints
# ---------------------------------------------------------------------------


@app.websocket("/api/notifications")
async def websocket_notifications(websocket: WebSocket) -> None:
    """WebSocket endpoint for receiving real-time event notifications."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)


@app.websocket("/api/system_stats")
async def websocket_system_stats(websocket: WebSocket) -> None:
    """WebSocket endpoint that streams CPU and memory usage every second."""
    await websocket.accept()
    # Initial call to cpu_percent to set baseline
    psutil.cpu_percent(interval=None)
    try:
        while True:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            cpu_usage: float = psutil.cpu_percent(interval=None)
            memory_info = psutil.virtual_memory()

            await websocket.send_json(
                {
                    "cpu_percent": round(cpu_usage, 1),
                    "memory_percent": round(memory_info.percent, 1),
                }
            )
    except Exception as e:
        # Silently ignore disconnections; log unexpected errors for diagnosis
        if not isinstance(e, WebSocketDisconnect):
            logger.debug("[WebSocket system_stats] Unexpected error: %s", e)


# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------


def init_app_state() -> None:
    """Initialise the backend settings, verify dependencies, and download default assets."""
    clear_cache()
    try:
        check_system_dependencies()
    except Exception as e:
        logger.warning("System dependencies check failed: %s", e)

    load_settings()
    download_default_assets_if_empty()


init_app_state()


# ---------------------------------------------------------------------------
# Media serving
# ---------------------------------------------------------------------------


@app.get("/videos/{filename:path}")
def serve_video(filename: str, range: str = Header(None)) -> Any:
    """Serve a video file from the videos directory with range-request support."""
    safe_path: str = os.path.realpath(os.path.join(VIDEOS_DIR, filename))
    if not safe_path.startswith(os.path.realpath(VIDEOS_DIR)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return stream_media(safe_path, range)


@app.get("/music/{filename:path}")
def serve_music(filename: str, range: str = Header(None)) -> Any:
    """Serve a music file from the music directory with range-request support."""
    safe_path = os.path.realpath(os.path.join(MUSIC_DIR, filename))
    if not safe_path.startswith(os.path.realpath(MUSIC_DIR)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return stream_media(safe_path, range)


@app.get("/output/{filename:path}")
def serve_output(filename: str, range: str = Header(None)) -> Any:
    """Serve a rendered output video with range-request support."""
    safe_path = os.path.realpath(os.path.join(OUTPUT_DIR, filename))
    if not safe_path.startswith(os.path.realpath(OUTPUT_DIR)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return stream_media(safe_path, range)


# ---------------------------------------------------------------------------
# Static file serving + SPA catch-all
# ---------------------------------------------------------------------------

if os.path.exists(FRONTEND_DIST_DIR):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(FRONTEND_DIST_DIR, "assets")),
        name="assets",
    )
    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIST_DIR),
        name="static",
    )
else:
    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(BASE_DIR, "gui/static")),
        name="static",
    )


@app.get("/")
def get_root() -> Any:
    """Serve the SPA index.html (frontend build or static fallback)."""
    dist_index: str = os.path.join(FRONTEND_DIST_DIR, "index.html")
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
app.include_router(schedule_router)
app.include_router(tiktok_router)


@app.get("/{full_path:path}")
def catch_all(full_path: str) -> Any:
    """SPA catch-all: serve index.html for any unrecognised frontend path."""
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(BASE_DIR, "gui/static/index.html"))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _free_server_port(port: int) -> None:
    """Kill known server processes occupying the given port.

    Only targets Python/uvicorn/gunicorn/hypercorn processes to avoid
    accidentally killing unrelated services.

    Args:
        port: The TCP port to check.
    """
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                for conn in proc.net_connections(kind="inet"):
                    if conn.laddr.port == port:
                        proc_name: str = proc.name().lower()
                        if any(n in proc_name for n in SERVER_PROCESS_NAMES):
                            logger.info(
                                "Killing process %d (%s) using port %d",
                                proc.pid,
                                proc.name(),
                                port,
                            )
                            proc.kill()
                        else:
                            logger.warning(
                                "Port %d in use by non-server process %d (%s) — skipping.",
                                port,
                                proc.pid,
                                proc.name(),
                            )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.info("Error while trying to free port %d: %s", port, e)


if __name__ == "__main__":

    class EndpointFilter(logging.Filter):
        """Filter out noisy uvicorn access log paths."""

        def filter(self, record: logging.LogRecord) -> bool:
            msg: str = record.getMessage()
            return not any(p in msg for p in NOISY_LOG_PATHS)

    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

    # Suppress asyncio SSL connection closed warnings
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    # Kill only *known server processes* on port 5000 to avoid killing unrelated services
    _free_server_port(SYSTEM_STATS_PORT)

    # Load config port or default to 5000
    ssl_kwargs: dict[str, str] = {}
    if "--https" in sys.argv:
        if os.path.exists("cert.pem") and os.path.exists("key.pem"):
            ssl_kwargs["ssl_certfile"] = "cert.pem"
            ssl_kwargs["ssl_keyfile"] = "key.pem"
        else:
            logger.info(
                "HTTPS requested but cert.pem or key.pem not found. "
                "Running in HTTP mode."
            )

    port: int = int(os.environ.get("PORT", SYSTEM_STATS_PORT))
    uvicorn.run(app, host="0.0.0.0", port=port, **ssl_kwargs)
