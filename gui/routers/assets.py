"""Video/music assets and gallery routes."""

from __future__ import annotations

import concurrent.futures
import contextlib
import functools
import os
import re
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

import gui.state as shared_state
import gui.thumbnail_cache as thumbnail_cache
from generator import get_video_info
from gui.assets_utils import list_music_files, list_video_files
from gui.config import MUSIC_DIR, OUTPUT_DIR, THUMBNAIL_DIR, VIDEOS_DIR

router: APIRouter = APIRouter()

# --- Constants ---

TEXT_FILE_HASHTAG_RE: re.Pattern = re.compile(r"^hashtags?\s*:\s*(.*)", re.I)
"""Regex for parsing hashtag lines in metadata text files."""

DURATION_RE: re.Pattern = re.compile(r"^Duration\s*:\s*([\d.]+)", re.I)
"""Regex for parsing ``Duration: <seconds>`` lines in metadata text files."""

VALID_FILENAME_CHARS: str = "._-"
"""Characters (besides alphanumeric) allowed in uploaded filenames."""

MAX_FILENAME_LENGTH: int = 255

VIDEO_EXTENSIONS: tuple[str, ...] = (".mp4", ".mov", ".mkv", ".webm", ".avi")
"""Recognised video extensions for thumbnail generation lookup."""


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------


@router.get("/api/assets/videos")
def list_assets_videos() -> list[dict[str, Any]]:
    """List all video files in the videos directory.

    Returns:
        List of dicts with ``filename``, ``url``, ``size``, and ``modified`` keys.
    """
    videos: list[dict[str, Any]] = []
    for fp in list_video_files(VIDEOS_DIR):
        f: str = os.path.basename(fp)
        size: int = os.path.getsize(fp)
        modified: float = os.path.getmtime(fp)
        videos.append(
            {
                "filename": f,
                "url": f"/videos/{f}",
                "size": size,
                "modified": modified,
                "thumbnail": f"/api/assets/videos/thumbnail/{f}?v={int(modified)}",
            }
        )
    return videos


@router.post("/api/assets/videos")
def upload_assets_video(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload a video file to the videos directory.

    Args:
        file: The uploaded file (multipart form data).

    Returns:
        Status response with filename and URL.

    Raises:
        HTTPException: If the filename is invalid or the upload fails.
    """
    safe: str = "".join(
        c for c in file.filename if c.isalnum() or c in VALID_FILENAME_CHARS
    )
    filename: str = safe.lstrip(".")[:MAX_FILENAME_LENGTH] or "unnamed_file"
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    dest_path: str = os.path.join(VIDEOS_DIR, filename)
    try:
        import shutil

        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        thumbnail_cache.enqueue(dest_path, thumbnail_cache.local_thumb_path(dest_path))
        return {
            "status": "success",
            "filename": filename,
            "url": f"/videos/{filename}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {e}") from e


@router.delete("/api/assets/videos/{filename}")
def delete_assets_video(filename: str) -> dict[str, str]:
    """Delete a video file from the videos directory.

    Also clears the corresponding state path if it was active.

    Args:
        filename: The video filename to delete.

    Returns:
        Status message on success.

    Raises:
        HTTPException: If the file is not found or deletion fails.
    """
    filename = os.path.basename(filename)
    dest_path: str = os.path.join(VIDEOS_DIR, filename)
    if not os.path.exists(dest_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    try:
        os.remove(dest_path)
        if shared_state.state["bg_video_path"] == dest_path:
            shared_state.state["bg_video_path"] = None
        if shared_state.state["bg_video_bottom_path"] == dest_path:
            shared_state.state["bg_video_bottom_path"] = None
        try:
            tp = thumbnail_cache.local_thumb_path(dest_path)
            if os.path.exists(tp):
                os.remove(tp)
        except OSError:
            pass
        return {"status": "success", "message": "Video deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {e}") from e


@router.get("/api/assets/videos/thumbnail/{filename}")
def get_assets_video_thumbnail(filename: str) -> FileResponse:
    """Serve (or enqueue) a thumbnail for a local-library video.

    Returns the cached JPEG if it exists; otherwise enqueues background
    generation and returns HTTP 404 so the frontend can retry.

    Args:
        filename: The video filename (must exist in VIDEOS_DIR).
    """
    filename = os.path.basename(filename)
    video_path = os.path.join(VIDEOS_DIR, filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")

    thumb_path = thumbnail_cache.local_thumb_path(video_path)
    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")

    thumbnail_cache.enqueue(video_path, thumb_path)
    raise HTTPException(status_code=404, detail="Thumbnail not yet generated")


# ---------------------------------------------------------------------------
# Music
# ---------------------------------------------------------------------------


@router.get("/api/assets/music")
def list_assets_music() -> list[dict[str, Any]]:
    """List all music files in the music directory.

    Returns:
        List of dicts with ``filename``, ``url``, ``size``, and ``modified`` keys.
    """
    music: list[dict[str, Any]] = []
    for fp in list_music_files(MUSIC_DIR):
        f: str = os.path.basename(fp)
        size = os.path.getsize(fp)
        modified = os.path.getmtime(fp)
        music.append(
            {"filename": f, "url": f"/music/{f}", "size": size, "modified": modified}
        )
    return music


@router.post("/api/assets/music")
def upload_assets_music(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload a music file to the music directory.

    Args:
        file: The uploaded file (multipart form data).

    Returns:
        Status response with filename and URL.
    """
    safe = "".join(
        c for c in file.filename if c.isalnum() or c in VALID_FILENAME_CHARS
    )
    filename = safe.lstrip(".")[:MAX_FILENAME_LENGTH] or "unnamed_file"
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    dest_path = os.path.join(MUSIC_DIR, filename)
    try:
        import shutil

        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {
            "status": "success",
            "filename": filename,
            "url": f"/music/{filename}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload music: {e}") from e


@router.delete("/api/assets/music/{filename}")
def delete_assets_music(filename: str) -> dict[str, str]:
    """Delete a music file from the music directory.

    Args:
        filename: The music filename to delete.

    Returns:
        Status message on success.
    """
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
        raise HTTPException(status_code=500, detail=f"Failed to delete music: {e}") from e


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=256)
def _probe_duration_cached(path: str, size: int, mtime: float) -> float | None:
    """Probe a video file's duration via ffprobe, cached on ``(path, size, mtime)``.

    The ``size``/``mtime`` cache keys ensure a modified file is re-probed even
    when the path is unchanged.

    Args:
        path: Full path to the video file.
        size: File size in bytes (cache key).
        mtime: File modification time in seconds (cache key).

    Returns:
        The video duration in seconds, or ``None`` if it cannot be determined.
    """
    try:
        info: dict[str, Any] | None = get_video_info(path, suppress_errors=True)
        duration: Any = info.get("duration") if info else None
    except Exception:
        return None
    if isinstance(duration, (int, float)) and duration > 0:
        return float(duration)
    return None


def _backfill_duration(filename: str, duration: float) -> None:
    """Append a ``Duration:`` line to a video's metadata sidecar file.

    Used when a duration was obtained via ffprobe because the sidecar was
    missing one, so future gallery loads are served instantly from the ``.txt``.

    Args:
        filename: The video filename; ``output/<basename>.txt`` is updated.
        duration: The video duration in seconds.
    """
    txt_file: str = os.path.join(OUTPUT_DIR, os.path.splitext(filename)[0] + ".txt")
    if not os.path.exists(txt_file):
        return
    try:
        with open(txt_file, "a", encoding="utf-8") as f:
            f.write(f"Duration: {duration:.2f}\n")
    except OSError:
        pass


def _prune_stale_thumbnails() -> None:
    """Remove thumbnail ``.jpg`` files whose source video no longer exists.

    A thumbnail in :data:`THUMBNAIL_DIR` is stale when no video file in
    :data:`OUTPUT_DIR` shares its base filename.  Failures are ignored —
    pruning is best-effort housekeeping.
    """
    if not os.path.isdir(THUMBNAIL_DIR) or not os.path.isdir(OUTPUT_DIR):
        return
    video_basenames: set[str] = {
        os.path.splitext(f)[0]
        for f in os.listdir(OUTPUT_DIR)
        if f.lower().endswith(VIDEO_EXTENSIONS)
    }
    for f in os.listdir(THUMBNAIL_DIR):
        if not f.lower().endswith(".jpg"):
            continue
        if os.path.splitext(f)[0] not in video_basenames:
            with contextlib.suppress(OSError):
                os.remove(os.path.join(THUMBNAIL_DIR, f))


@router.get("/api/gallery")
def list_gallery_videos() -> list[dict[str, Any]]:
    """List all rendered output videos with optional metadata from sidecar files.

    Durations are read from ``Duration:`` sidecar lines when available;
    otherwise they are probed concurrently via ffprobe (and backfilled into the
    sidecar so subsequent loads skip the probe).

    Returns:
        List of video info dicts sorted by modification time (newest first).
    """
    _prune_stale_thumbnails()

    videos: list[dict[str, Any]] = []
    pending_probe: list[tuple[dict[str, Any], str]] = []

    for fp in list_video_files(OUTPUT_DIR, exclude_sfx=False):
        f = os.path.basename(fp)
        size = os.path.getsize(fp)
        modified = os.path.getmtime(fp)

        title: str = ""
        hashtags: str = ""
        duration: float | None = None
        txt_file: str = os.path.splitext(fp)[0] + ".txt"
        if os.path.exists(txt_file):
            try:
                with open(txt_file, encoding="utf-8") as tf:
                    lines: list[str] = tf.readlines()
                    if lines:
                        if any(
                            TEXT_FILE_HASHTAG_RE.match(line) for line in lines
                        ):
                            # Old format: find line starting with Hashtag(s):
                            for line in lines:
                                m = TEXT_FILE_HASHTAG_RE.match(line)
                                if m:
                                    hashtags = m.group(1).strip()
                                    break
                        else:
                            # New format: line 0 is title, line 1 is hashtags
                            if len(lines) >= 2:
                                title = lines[0].strip()
                                hashtags = lines[1].strip()
                        # Duration line (any format)
                        for line in lines:
                            m = DURATION_RE.match(line.strip())
                            if m:
                                try:
                                    duration = float(m.group(1))
                                except ValueError:
                                    duration = None
                                break
            except Exception:
                pass

        thumb_filename: str = os.path.splitext(f)[0] + ".jpg"
        thumbnail: str = f"/api/gallery/thumbnail/{thumb_filename}"

        video_entry: dict[str, Any] = {
            "filename": f,
            "url": f"/output/{f}",
            "size": size,
            "modified": modified,
            "duration": duration,
            "title": title,
            "hashtags": hashtags,
            "thumbnail": thumbnail,
        }
        videos.append(video_entry)
        if duration is None:
            pending_probe.append((video_entry, fp))

    # Probe missing durations concurrently so many videos don't serialize ffprobe.
    if pending_probe:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_entry = {
                executor.submit(
                    _probe_duration_cached,
                    fp,
                    os.path.getsize(fp),
                    os.path.getmtime(fp),
                ): (entry, fp)
                for entry, fp in pending_probe
            }
            for future in concurrent.futures.as_completed(future_to_entry):
                entry, fp = future_to_entry[future]
                try:
                    probed: float | None = future.result()
                except Exception:
                    probed = None
                if probed is not None and probed > 0:
                    entry["duration"] = probed
                    _backfill_duration(entry["filename"], probed)

    videos.sort(key=lambda x: x["modified"], reverse=True)

    # Enqueue missing gallery thumbnails for background generation
    for v in videos:
        base = os.path.splitext(v["filename"])[0]
        thumb = os.path.join(THUMBNAIL_DIR, base + ".jpg")
        if not os.path.exists(thumb):
            fp = os.path.join(OUTPUT_DIR, v["filename"])
            thumbnail_cache.enqueue(fp, thumb)

    return videos


@router.delete("/api/gallery/{filename}")
def delete_gallery_video(filename: str) -> dict[str, str]:
    """Delete a rendered video and its thumbnail + metadata sidecar files.

    Args:
        filename: The output video filename to delete.

    Returns:
        Status message on success.
    """
    filename = os.path.basename(filename)
    dest_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(dest_path):
        raise HTTPException(status_code=404, detail="Compiled video file not found.")

    try:
        os.remove(dest_path)
        basename = os.path.splitext(filename)[0]
        thumb_path = os.path.join(THUMBNAIL_DIR, basename + ".jpg")
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        meta_path = os.path.join(OUTPUT_DIR, basename + ".txt")
        if os.path.exists(meta_path):
            os.remove(meta_path)
        return {
            "status": "success",
            "message": "Compiled video deleted successfully.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {e}") from e


@router.delete("/api/gallery")
def delete_all_gallery_videos() -> dict[str, str]:
    """Delete all rendered output videos and their thumbnails.

    Returns:
        Status message on success.
    """
    if not os.path.exists(OUTPUT_DIR):
        return {"status": "success", "message": "No videos to delete."}

    try:
        for f in os.listdir(OUTPUT_DIR):
            fp = os.path.join(OUTPUT_DIR, f)
            if os.path.isfile(fp):
                os.remove(fp)
        if os.path.isdir(THUMBNAIL_DIR):
            for f in os.listdir(THUMBNAIL_DIR):
                fp = os.path.join(THUMBNAIL_DIR, f)
                if os.path.isfile(fp):
                    os.remove(fp)
        return {
            "status": "success",
            "message": "All generated videos deleted successfully.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete all videos: {e}"
        ) from e


@router.get("/api/gallery/thumbnail/{filename}")
def get_gallery_thumbnail(filename: str) -> FileResponse:
    """Serve or enqueue a thumbnail for a gallery output video.

    Returns the cached JPEG if it exists; otherwise enqueues background
    generation and returns HTTP 404 so the frontend can retry.
    """
    filename = os.path.basename(filename)
    thumb_path = os.path.join(THUMBNAIL_DIR, filename)

    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")

    base_name = os.path.splitext(filename)[0]
    for ext in VIDEO_EXTENSIONS:
        video_path = os.path.join(OUTPUT_DIR, base_name + ext)
        if os.path.exists(video_path):
            thumbnail_cache.enqueue(video_path, thumb_path)
            raise HTTPException(status_code=404, detail="Thumbnail not yet generated")

    raise HTTPException(status_code=404, detail="Thumbnail not found")
