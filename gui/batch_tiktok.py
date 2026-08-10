"""TikTok posting for completed batch videos.

Contains ``_tiktok_post_worker`` (background daemon that uploads finished
videos) and ``_delete_posted_video`` (cleanup after a successful post).

``batch_state`` is imported lazily inside functions to avoid a circular
import with ``gui.batch_engine``.
"""

from __future__ import annotations

import contextlib
import os
import time
from typing import Any

import gui.state as shared_state
from gui.config import logger
from gui.ws_manager import broadcast_batch_status, notify_clients


def _delete_posted_video(output_filename: str) -> None:
    """Delete an output video and its sidecar files after a successful TikTok post.

    Removes the video file, its ``.txt`` sidecar, and its thumbnail — mirroring
    the Gallery's ``delete_gallery_video`` behaviour.

    Args:
        output_filename: The video filename inside ``OUTPUT_DIR``.
    """
    from gui.config import OUTPUT_DIR, THUMBNAIL_DIR

    basename: str = os.path.splitext(output_filename)[0]
    for path in (
        os.path.join(OUTPUT_DIR, output_filename),
        os.path.join(OUTPUT_DIR, f"{basename}.txt"),
        os.path.join(THUMBNAIL_DIR, f"{basename}.jpg"),
    ):
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info("[TikTok Post] Deleted %s", path)
        except OSError as e:
            logger.warning("[TikTok Post] Failed to delete %s: %s", path, e)


def _tiktok_post_worker(post_queue: Any) -> None:
    """Background daemon worker that posts completed batch videos to TikTok.

    Dequeues job indices from ``post_queue``, uploads each video, deletes the
    file on success, and records the result in ``batch_state``.  Stops when it
    receives ``None`` as a sentinel value.

    Args:
        post_queue: Queue of job indices (or ``None`` to stop).
    """
    import asyncio as _asyncio
    import queue as _queue
    import threading as _threading_mod

    from gui.batch_engine import batch_state

    # Playwright's sync API raises if it detects an asyncio event loop running
    # in the current thread.  This worker thread inherits the FastAPI process's
    # loop reference, so we clear it here before any upload attempt.
    with contextlib.suppress(Exception):
        _asyncio.set_event_loop(None)

    sessionid: str = str(
        shared_state.settings.get("tiktok_sessionid", "") or ""
    ).strip()

    while True:
        try:
            idx = post_queue.get(timeout=5.0)
        except _queue.Empty:
            # Keep waiting — only the None sentinel stops this worker
            continue

        if idx is None:
            # Sentinel — stop the worker
            post_queue.task_done()
            break

        if batch_state.get("should_cancel"):
            logger.info("[TikTok Post] Skipping job #%d — batch cancelled", idx)
            if "tiktok_post_results" not in batch_state:
                batch_state["tiktok_post_results"] = {}
            batch_state["tiktok_post_results"][idx] = {
                "status": "skipped",
                "error": "Batch cancelled",
            }
            batch_state["shared_progress"][idx] = "Done"
            post_queue.task_done()
            continue

        config = batch_state.get("job_configs", {}).get(idx, {})
        output_filename: str = config.get("output_filename", "")

        try:
            from gui.config import OUTPUT_DIR
            from gui.routers.tiktok import _build_description, post_video_blocking

            path: str = os.path.join(OUTPUT_DIR, output_filename)
            description: str = _build_description(output_filename, path)

            # Apply per-job stagger delay (e.g., for scheduled human-like posting)
            delays: dict[int, float] = batch_state.get("tiktok_delays", {}) or {}
            delay: float = delays.get(idx, 0)
            if delay > 0:
                logger.info(
                    "[TikTok Post] Delaying job #%d by %.0f min", idx, delay / 60
                )
                batch_state["shared_progress"][
                    idx
                ] = f"Posting to TikTok… (in ~{int(delay / 60)}m)"
                from gui.routers.batch import build_batch_status
                broadcast_batch_status(build_batch_status())
                time.sleep(delay)

            logger.info("[TikTok Post] Uploading job #%d: %s", idx, output_filename)
            batch_state["shared_progress"][idx] = "Posting to TikTok…"

            # Broadcast updated status to clients
            from gui.routers.batch import build_batch_status
            broadcast_batch_status(build_batch_status())

            # Spawn a fresh thread for the upload to ensure a clean event loop
            upload_thread = _threading_mod.Thread(
                target=post_video_blocking,
                args=(path, description, sessionid),
                daemon=True,
            )
            upload_thread.start()
            upload_thread.join()

            # Success — delete the file and record result
            _delete_posted_video(output_filename)
            if "tiktok_post_results" not in batch_state:
                batch_state["tiktok_post_results"] = {}
            batch_state["tiktok_post_results"][idx] = {"status": "posted"}
            batch_state["shared_progress"][idx] = "Done"
            logger.info("[TikTok Post] Job #%d posted and deleted successfully", idx)
            notify_clients(
                "tiktok_upload",
                "success",
                f"Job #{idx} posted to TikTok!",
                level="success",
                metadata={"filename": output_filename, "error": None},
            )

        except Exception as e:
            logger.error("[TikTok Post] Job #%d upload failed: %s", idx, e, exc_info=True)
            if "tiktok_post_results" not in batch_state:
                batch_state["tiktok_post_results"] = {}
            batch_state["tiktok_post_results"][idx] = {
                "status": "failed",
                "error": str(e),
            }
            batch_state["shared_progress"][idx] = "Done"
            notify_clients(
                "tiktok_upload",
                "error",
                f"Job #{idx} TikTok post failed: {e}",
                level="error",
                metadata={"filename": output_filename, "error": str(e)},
            )

        finally:
            # Always broadcast updated status and mark the queue item done
            try:
                from gui.routers.batch import build_batch_status
                broadcast_batch_status(build_batch_status())
            except Exception:
                pass
            post_queue.task_done()
