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

@router.get("/api/settings")
def get_api_settings():
    # reload settings from disk first
    load_settings()
    return shared_state.settings



@router.post("/api/settings")
def save_api_settings(data: SettingsModel):
    # Convert model to dict
    settings_dict = data.model_dump()

    success = save_settings(settings_dict)
    if success:
        return {"status": "success", "message": "Settings saved successfully."}
    else:
        raise HTTPException(status_code=500, detail="Failed to save settings to disk.")



@router.get("/api/presets")
def get_api_presets():
    # Combination of builtin and custom presets
    presets = load_presets()
    return presets



@router.post("/api/presets")
def save_api_preset(data: PresetModel):
    preset_dict = data.model_dump()
    name = preset_dict.pop("name")
    success = save_custom_preset(name, preset_dict)
    if success:
        return {"status": "success", "message": f"Preset '{name}' saved successfully."}
    else:
        raise HTTPException(status_code=500, detail="Failed to save preset.")



@router.delete("/api/presets/{name}")
def delete_api_preset(name: str):
    success = delete_custom_preset(name)
    if success:
        return {"status": "success", "message": f"Preset '{name}' deleted successfully."}
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Preset '{name}' could not be deleted (might be builtin or not found).",
        )



@router.get("/api/state")
def get_api_state():
    return shared_state.state



@router.post("/api/state")
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



