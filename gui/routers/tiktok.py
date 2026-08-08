"""TikTok upload routes using the ``tiktok-uploader`` library.

Uploads gallery videos from the output directory to TikTok in the
background.  The blocking Playwright upload runs in a threadpool
executor so the FastAPI event loop is never stalled.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import threading
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

import gui.state as shared_state
from gui.config import OUTPUT_DIR, logger
from gui.ws_manager import notify_clients

router: APIRouter = APIRouter()

_last_status: dict[str, Any] = {
    "state": "idle",
    "filename": None,
    "error": None,
    "stage": "idle",
    "percent": 0,
}
"""Last TikTok upload result, exposed via ``GET /api/tiktok/status``."""

_upload_progress: dict[str, Any] = {"stage": "idle", "percent": 0}
"""Live upload progress, updated from the worker thread during an upload."""

_upload_lock: asyncio.Lock = asyncio.Lock()
"""Serialises uploads so two uploads can never run concurrently."""

_upload_thread_lock: threading.Lock = threading.Lock()
"""Serialises uploads across both gallery (async) and batch (thread) callers."""


def _set_progress(stage: str, percent: int, filename: str) -> None:
    """Update the live upload progress and broadcast it to clients.

    Updates ``_upload_progress`` and the ``stage``/``percent`` keys of
    ``_last_status`` so both the websocket notifications and the poll
    endpoint stay in sync.  Safe to call from the worker thread —
    ``notify_clients`` schedules the broadcast on the event loop via
    ``asyncio.run_coroutine_threadsafe``.

    Args:
        stage: Human-readable description of the current stage.
        percent: Approximate completion percentage (0-100).
        filename: The video file currently being uploaded.
    """
    global _upload_progress, _last_status
    _upload_progress = {"stage": stage, "percent": percent}
    # Update _last_status in place too so the poll endpoint always has fresh data
    _last_status = {**_last_status, "stage": stage, "percent": percent}
    notify_clients(
        "tiktok_upload",
        "progress",
        stage,
        level="info",
        metadata={"filename": filename, "stage": stage, "percent": percent, "error": None},
    )


def _do_upload(path: str, description: str, sessionid: str) -> None:
    """Blocking TikTok upload — runs in a dedicated thread.

    Args:
        path: Absolute path to the video file to upload.
        description: Caption text (title + hashtags) for the post.
        sessionid: TikTok session cookie value used for authentication.
    """
    import tiktok_uploader.upload as tu_upload
    from tiktok_uploader.upload import TikTokUploader
    from gui.progress_utils import log_subprocess_start, log_subprocess_end

    filename: str = os.path.basename(path)

    # Monkey-patch to remove TikTok's onboarding overlay which intercepts clicks
    original_set_description = tu_upload._set_description
    def patched_set_description(page, desc):
        _set_progress("Writing caption…", 65, filename)
        try:
            page.evaluate('''
                const joyride = document.getElementById("react-joyride-portal");
                if (joyride) joyride.remove();
                const overlay = document.querySelector(".react-joyride__overlay");
                if (overlay) overlay.remove();
                const cookieBanner = document.querySelector("tiktok-cookie-banner");
                if (cookieBanner) cookieBanner.remove();
            ''')
        except Exception as e:
            logger.warning("Failed to remove overlays: %s", e)
        return original_set_description(page, desc)

    # Monkey-patch _post_video to also clean up overlays just in case they appear late
    original_post_video = tu_upload._post_video
    def patched_post_video(page):
        _set_progress("Posting to TikTok…", 85, filename)
        with contextlib.suppress(Exception):
            page.evaluate('''
                const cookieBanner = document.querySelector("tiktok-cookie-banner");
                if (cookieBanner) cookieBanner.remove();
            ''')
        result = original_post_video(page)
        _set_progress("Waiting for confirmation…", 95, filename)
        return result

    # Monkey-patch complete_upload_form to report progress for each stage.
    # complete_upload_form calls _go_to_upload, _set_video, _set_description
    # and _post_video in order; the sub-steps that can't be patched directly
    # are reported before/after the wrapped calls below.
    original_complete_upload_form = tu_upload.complete_upload_form

    def patched_complete_upload_form(page, path, description, schedule, skip_split_window, *args, **kwargs):
        # Stage: navigating to upload page
        _set_progress("Navigating to upload page…", 10, filename)
        # _go_to_upload is harder to intercept; instead wrap _set_video within
        # this context to report the file-upload and processing stages.
        original_set_video = tu_upload._set_video
        def patched_set_video(page, path="", **kw):
            _set_progress("Uploading video file…", 20, filename)
            result = original_set_video(page, path=path, **kw)
            _set_progress("Video processing…", 50, filename)
            return result
        tu_upload._set_video = patched_set_video

        try:
            result = original_complete_upload_form(page, path, description, schedule, skip_split_window, *args, **kwargs)
        finally:
            tu_upload._set_video = original_set_video
        return result

    tu_upload._set_description = patched_set_description
    tu_upload._post_video = patched_post_video
    tu_upload.complete_upload_form = patched_complete_upload_form

    try:
        # Pass the sessionid directly in a correctly formed cookie dict to bypass a bug in tiktok-uploader
        # where it creates a sessionid cookie without a domain/path, which Playwright rejects.
        cookie = {"name": "sessionid", "value": sessionid, "domain": ".tiktok.com", "path": "/"}
        t0 = log_subprocess_start("playwright-upload")
        with TikTokUploader(cookies_list=[cookie], headless=True, browser="chromium") as uploader:
            success = uploader.upload_video(path, description=description)
        log_subprocess_end("playwright-upload", t0)
    finally:
        tu_upload._set_description = original_set_description
        tu_upload._post_video = original_post_video
        tu_upload.complete_upload_form = original_complete_upload_form

    if not success:
        raise RuntimeError("TikTok upload failed. The session ID may have expired or the browser timed out.")


def _build_description(filename: str, path: str) -> str:
    """Build the TikTok caption from the video's sidecar ``.txt`` file.

    The first line that is not a hashtag is treated as the title; any
    hashtag lines are appended after it to form the full caption.  Falls
    back to the filename stem when no sidecar file exists.

    Args:
        filename: The video filename (used for the fallback stem).
        path: Absolute path to the video file.

    Returns:
        The caption, truncated to a maximum of 300 characters.
    """
    lines: list[str] = []
    txt_path: str = os.path.splitext(path)[0] + ".txt"
    if os.path.exists(txt_path):
        try:
            with open(txt_path, encoding="utf-8") as f:
                lines = [ln.strip() for ln in f.read().splitlines() if ln.strip()]
        except OSError as e:
            logger.warning("Failed to read sidecar file %s: %s", txt_path, e)

    title: str | None = None
    hashtags: list[str] = []
    for ln in lines:
        if ln.startswith("#"):
            hashtags.append(ln)
        elif title is None:
            title = ln

    parts: list[str] = []
    if title:
        parts.append(title)
    parts.extend(hashtags)

    # Use a space to join so that tiktok-uploader's `description.split(" ")` correctly
    # parses the hashtags and selects them from the TikTok dropdown.
    description: str = " ".join(parts).strip()
    if not description:
        description = os.path.splitext(filename)[0]
    return description[:300]


def post_video_blocking(path: str, description: str, sessionid: str) -> None:
    """Upload a video to TikTok synchronously from a background thread.

    Acquires ``_upload_thread_lock`` so it cannot run concurrently with a
    gallery upload.  Resets ``_last_status`` / ``_upload_progress`` to idle
    on completion (success or failure).

    Args:
        path: Absolute path to the video file to upload.
        description: Caption text for the post.
        sessionid: TikTok session cookie value.

    Raises:
        RuntimeError: If the upload fails.
    """
    global _last_status, _upload_progress
    with _upload_thread_lock:
        try:
            _do_upload(path, description, sessionid)
        finally:
            _last_status = {
                "state": "idle",
                "filename": None,
                "error": None,
                "stage": "idle",
                "percent": 0,
            }
            _upload_progress = {"stage": "idle", "percent": 0}


async def _background_upload(path: str, description: str, sessionid: str) -> None:
    """Run the blocking upload in a dedicated thread and broadcast the result.

    Args:
        path: Absolute path to the video file to upload.
        description: Caption text for the post.
        sessionid: TikTok session cookie value.
    """
    import threading
    global _last_status, _upload_progress
    filename: str = os.path.basename(path)

    async with _upload_lock:
        _last_status = {
            "state": "uploading",
            "filename": filename,
            "error": None,
            "stage": "Starting…",
            "percent": 5,
        }
        _set_progress("Starting…", 5, filename)
        notify_clients(
            "tiktok_upload",
            "info",
            f"TikTok upload started for {filename}...",
            level="info",
            metadata={"filename": filename, "error": None},
        )

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def target():
            try:
                with _upload_thread_lock:
                    _do_upload(path, description, sessionid)
                loop.call_soon_threadsafe(future.set_result, None)
            except Exception as e:
                loop.call_soon_threadsafe(future.set_exception, e)

        try:
            thread = threading.Thread(target=target)
            thread.start()
            await future
        except Exception as e:
            _last_status = {
                "state": "error",
                "filename": filename,
                "error": str(e),
                "stage": "Failed",
                "percent": 0,
            }
            _upload_progress = {"stage": "idle", "percent": 0}
            logger.error(
                "[TikTok Upload] Failed for %s: %s", filename, e, exc_info=True
            )
            notify_clients(
                "tiktok_upload",
                "error",
                f"TikTok upload failed for {filename}: {e}",
                level="error",
                metadata={"filename": filename, "error": str(e)},
            )
            return

        _set_progress("Done", 100, filename)
        _last_status = {
            "state": "done",
            "filename": filename,
            "error": None,
            "stage": "Done",
            "percent": 100,
        }
        _upload_progress = {"stage": "idle", "percent": 0}
        logger.info("[TikTok Upload] Successfully uploaded %s", filename)
        notify_clients(
            "tiktok_upload",
            "success",
            f"TikTok upload completed for {filename}!",
            level="success",
            metadata={"filename": filename, "error": None},
        )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/api/tiktok/status")
def get_tiktok_status() -> dict[str, Any]:
    """Return the last TikTok upload result.

    Returns:
        Dictionary with ``state`` (``"idle"``, ``"uploading"``, ``"done"``
        or ``"error"``), the affected ``filename``, an optional ``error``
        message, and the live ``stage``/``percent`` progress keys.
    """
    return dict(_last_status)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@router.post("/api/tiktok/post/{filename}")
def post_to_tiktok(
    filename: str, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Post a gallery video from the output directory to TikTok.

    Validates the configured session ID and the target video file, then
    schedules the upload to run in the background.

    Args:
        filename: Name of the video file inside ``OUTPUT_DIR``.
        background_tasks: FastAPI background task manager.

    Returns:
        Status response indicating the upload has started.

    Raises:
        HTTPException: If the TikTok session ID is missing, the file does
            not exist, or an upload is already in progress.
    """
    sessionid: str = str(
        shared_state.settings.get("tiktok_sessionid", "") or ""
    ).strip()
    if not sessionid:
        raise HTTPException(
            status_code=400,
            detail="TikTok session ID is missing. Add it in the Settings panel.",
        )

    path: str = os.path.join(OUTPUT_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(
            status_code=404, detail=f"Video '{filename}' not found."
        )

    if _last_status.get("state") == "uploading":
        raise HTTPException(status_code=409, detail="Upload already in progress")

    description: str = _build_description(filename, path)
    background_tasks.add_task(_background_upload, path, description, sessionid)
    return {"status": "started", "filename": filename}
