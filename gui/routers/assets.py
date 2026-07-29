"""Video/music assets and gallery routes."""

from __future__ import annotations

import os
import re
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

import gui.state as shared_state
from gui.assets_utils import list_music_files, list_video_files
from gui.config import MUSIC_DIR, OUTPUT_DIR, THUMBNAIL_DIR, VIDEOS_DIR
from gui.media import generate_video_thumbnail

router: APIRouter = APIRouter()

# --- Constants ---

TEXT_FILE_HASHTAG_RE: re.Pattern = re.compile(r"^hashtags?\s*:\s*(.*)", re.I)
"""Regex for parsing hashtag lines in metadata text files."""

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
        return {
            "status": "success",
            "filename": filename,
            "url": f"/videos/{filename}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {e}")


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
        return {"status": "success", "message": "Video deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {e}")


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
        raise HTTPException(status_code=500, detail=f"Failed to upload music: {e}")


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
        raise HTTPException(status_code=500, detail=f"Failed to delete music: {e}")


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------


@router.get("/api/gallery")
def list_gallery_videos() -> list[dict[str, Any]]:
    """List all rendered output videos with optional metadata from sidecar files.

    Returns:
        List of video info dicts sorted by modification time (newest first).
    """
    videos: list[dict[str, Any]] = []
    for fp in list_video_files(OUTPUT_DIR, exclude_sfx=False):
        f = os.path.basename(fp)
        size = os.path.getsize(fp)
        modified = os.path.getmtime(fp)

        # Read duration
        duration: float | None = None
        try:
            from generator import get_video_info

            info = get_video_info(fp, suppress_errors=True)
            duration = info.get("duration")
        except Exception:
            pass

        title: str = ""
        hashtags: str = ""
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
            except Exception:
                pass

        thumb_filename: str = os.path.splitext(f)[0] + ".jpg"
        thumbnail: str = f"/api/gallery/thumbnail/{thumb_filename}"

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
    videos.sort(key=lambda x: x["modified"], reverse=True)
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
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {e}")


@router.delete("/api/gallery")
def delete_all_gallery_videos() -> dict[str, str]:
    """Delete all rendered output videos.

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
        return {
            "status": "success",
            "message": "All generated videos deleted successfully.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete all videos: {e}"
        )


@router.get("/api/gallery/thumbnail/{filename}")
def get_gallery_thumbnail(filename: str) -> FileResponse:
    """Serve or generate a thumbnail for a gallery video.

    Args:
        filename: The thumbnail filename (``{basename}.jpg``).

    Returns:
        The thumbnail image file.

    Raises:
        HTTPException: If the thumbnail cannot be found or generated (404).
    """
    filename = os.path.basename(filename)
    thumb_path = os.path.join(THUMBNAIL_DIR, filename)

    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")

    base_name = os.path.splitext(filename)[0]
    for ext in VIDEO_EXTENSIONS:
        video_path = os.path.join(OUTPUT_DIR, base_name + ext)
        if os.path.exists(video_path):
            if generate_video_thumbnail(video_path, thumb_path) and os.path.exists(
                thumb_path
            ):
                return FileResponse(thumb_path, media_type="image/jpeg")
            break

    raise HTTPException(status_code=404, detail="Thumbnail not found")
