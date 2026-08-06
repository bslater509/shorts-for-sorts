"""Background thumbnail worker with persistent on-disk cache.

- Gallery output thumbnails stored in existing THUMBNAIL_DIR (output/thumbnails/).
- Local library thumbnails stored in LOCAL_VIDEO_THUMBNAIL_DIR (cache/thumbnails/videos/),
  content-addressed via sha1(path|size|mtime)[:16].jpg so file changes bust the cache.
- Daemon worker pool (2 threads) pulls from a deduplicated queue; idempotent start/stop.
- precache_all() scans OUTPUT_DIR + VIDEOS_DIR for missing thumbs; also prunes stal
  local thumbs.
"""

from __future__ import annotations

import hashlib
import os
import queue
import threading

from gui.config import (
    LOCAL_VIDEO_THUMBNAIL_DIR,
    OUTPUT_DIR,
    THUMBNAIL_DIR,
    VIDEOS_DIR,
)
from gui.media import generate_video_thumbnail

_WORKER_POOL_SIZE: int = 2
_VIDEO_EXTS: tuple[str, ...] = (".mp4", ".mov", ".mkv", ".webm", ".avi")

_queue: queue.Queue[tuple[str, str] | None] = queue.Queue()
"""Work items: (video_path, thumb_path). None sentinel for shutdown."""

_in_progress: set[str] = set()
"""Deduplication set guarded by _in_progress_lock."""
_in_progress_lock = threading.Lock()

_workers_started: bool = False
"""Ensure start_thumbnail_worker is idempotent."""


def _stable_key(video_path: str) -> str:
    """Deterministic cache key: sha1hex(realpath|size|mtime)[:16]."""
    st = os.stat(video_path)
    raw = f"{os.path.realpath(video_path)}|{st.st_size}|{int(st.st_mtime)}".encode()
    return hashlib.sha1(raw).hexdigest()[:16]


def local_thumb_path(video_path: str) -> str:
    """Return the full cached thumbnail path for a local library video."""
    os.makedirs(LOCAL_VIDEO_THUMBNAIL_DIR, exist_ok=True)
    return os.path.join(LOCAL_VIDEO_THUMBNAIL_DIR, _stable_key(video_path) + ".jpg")


def enqueue(video_path: str, thumb_path: str) -> None:
    """Enqueue thumbnail generation. No-op if already queued/in-progress."""
    with _in_progress_lock:
        if thumb_path in _in_progress:
            return
        _in_progress.add(thumb_path)
    _queue.put((video_path, thumb_path))


def _worker_loop() -> None:
    """Worker thread: pulls jobs and generates thumbnails."""
    while True:
        item = _queue.get()
        if item is None:  # shutdown sentinel
            break
        video_path, thumb_path = item
        try:
            generate_video_thumbnail(video_path, thumb_path)
        except Exception:
            pass  # logged inside generate_video_thumbnail
        finally:
            with _in_progress_lock:
                _in_progress.discard(thumb_path)


def start_thumbnail_worker() -> None:
    """Idempotent: spawn daemon worker threads (MainProcess only)."""
    global _workers_started
    if _workers_started:
        return
    import multiprocessing
    if multiprocessing.current_process().name != "MainProcess":
        return
    _workers_started = True
    for _ in range(_WORKER_POOL_SIZE):
        t = threading.Thread(target=_worker_loop, daemon=True)
        t.start()


def stop_thumbnail_worker() -> None:
    """Send sentinels to workers so they exit cleanly."""
    for _ in range(_WORKER_POOL_SIZE):
        _queue.put(None)


def precache_all() -> None:
    """Scan both output and local library dirs; enqueue missing thumbs.
    Also prune stale local thumbs.
    """
    _precache_output_thumbs()
    _precache_local_thumbs()
    _prune_local_thumbs()


def _precache_output_thumbs() -> None:
    """Enqueue gallery output videos whose .jpg thumb is missing in THUMBNAIL_DIR."""
    if not os.path.isdir(OUTPUT_DIR) or not os.path.isdir(THUMBNAIL_DIR):
        return
    for f in os.listdir(OUTPUT_DIR):
        if not f.lower().endswith(_VIDEO_EXTS):
            continue
        base = os.path.splitext(f)[0]
        thumb = os.path.join(THUMBNAIL_DIR, base + ".jpg")
        if os.path.exists(thumb):
            continue
        enqueue(os.path.join(OUTPUT_DIR, f), thumb)


def _precache_local_thumbs() -> None:
    """Enqueue local library videos whose cached thumb is missing."""
    if not os.path.isdir(VIDEOS_DIR):
        return
    for f in os.listdir(VIDEOS_DIR):
        fp = os.path.join(VIDEOS_DIR, f)
        if not os.path.isfile(fp):
            continue
        if not f.lower().endswith(_VIDEO_EXTS):
            continue
        tp = local_thumb_path(fp)
        if os.path.exists(tp):
            continue
        enqueue(fp, tp)


def _prune_local_thumbs() -> None:
    """Remove local cached thumbs whose source video is gone or has changed."""
    if not os.path.isdir(LOCAL_VIDEO_THUMBNAIL_DIR) or not os.path.isdir(VIDEOS_DIR):
        return
    # Build set of valid thumb paths from current videos
    valid: set[str] = set()
    for f in os.listdir(VIDEOS_DIR):
        fp = os.path.join(VIDEOS_DIR, f)
        if not os.path.isfile(fp):
            continue
        if f.lower().endswith(_VIDEO_EXTS):
            valid.add(local_thumb_path(fp))
    for tf in os.listdir(LOCAL_VIDEO_THUMBNAIL_DIR):
        if not tf.lower().endswith(".jpg"):
            continue
        tp = os.path.join(LOCAL_VIDEO_THUMBNAIL_DIR, tf)
        if tp not in valid:
            import contextlib
            with contextlib.suppress(OSError):
                os.remove(tp)


def enqueue_gallery_missing(video_path: str) -> None:
    """Enqueue a thumbnail for a single gallery video if it doesn't exist."""
    base = os.path.splitext(os.path.basename(video_path))[0]
    thumb = os.path.join(THUMBNAIL_DIR, base + ".jpg")
    if not os.path.exists(thumb):
        enqueue(video_path, thumb)
