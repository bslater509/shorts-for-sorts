"""Media streaming, thumbnail generation, and file-serving utilities."""

from __future__ import annotations

import mimetypes
import os
import subprocess
import traceback
from typing import Any, Generator

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from gui.config import logger

# --- Constants ---

CHUNK_SIZE: int = 1024 * 1024
"""Read chunk size in bytes (1 MiB) for streaming media files."""

DEFAULT_CONTENT_TYPE: str = "application/octet-stream"
"""Fallback MIME type when the file extension is unrecognised."""

THUMBNAIL_SEEK_TIME: str = "00:00:02"
"""Timestamp at which to extract a thumbnail frame from a video."""

FFMPEG_THUMBNAIL_TIMEOUT: int = 15
"""Timeout in seconds for FFmpeg thumbnail extraction."""


def stream_media(
    file_path: str, range_header: str | None
) -> StreamingResponse:
    """Stream a media file with HTTP Range-request support (iOS Safari compatible).

    Args:
        file_path: Absolute path to the media file on disk.
        range_header: The value of the ``Range`` HTTP header, or ``None``.

    Returns:
        A :class:`StreamingResponse` with the appropriate status code
        (``200`` for full content, ``206`` for partial content).

    Raises:
        HTTPException: If the file does not exist (404).
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    file_size: int = os.path.getsize(file_path)
    start: int = 0
    end: int = file_size - 1

    if range_header:
        range_str: list[str] = range_header.replace("bytes=", "").split("-")
        try:
            start = int(range_str[0])
            if len(range_str) > 1 and range_str[1]:
                end = int(range_str[1])
        except ValueError:
            pass

    end = min(end, file_size - 1)
    chunk_size: int = end - start + 1

    def _get_chunk() -> Generator[bytes, None, None]:
        """Generator that yields the requested byte range in chunks."""
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining: int = chunk_size
            while remaining > 0:
                data: bytes = f.read(min(remaining, CHUNK_SIZE))
                if not data:
                    break
                yield data
                remaining -= len(data)

    content_type: str | None = mimetypes.guess_type(file_path)[0]
    if not content_type:
        content_type = DEFAULT_CONTENT_TYPE

    headers: dict[str, str] = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": content_type,
    }

    status_code: int
    if range_header:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        status_code = 206
    else:
        status_code = 200

    return StreamingResponse(
        _get_chunk(), status_code=status_code, headers=headers
    )


def _safe_path(base_dir: str, filename: str) -> str:
    """Resolve a file path safely, preventing directory traversal.

    Args:
        base_dir: The allowed base directory.
        filename: The requested filename (may contain path components).

    Returns:
        The resolved absolute path.

    Raises:
        HTTPException: If the resolved path is outside ``base_dir`` (403).
    """
    safe_path: str = os.path.realpath(os.path.join(base_dir, filename))
    if not safe_path.startswith(os.path.realpath(base_dir)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return safe_path


def generate_video_thumbnail(
    video_path: str, thumb_path: str, width: int = 480
) -> bool:
    """Extract a thumbnail frame from a video at the 2-second mark.

    Args:
        video_path: Path to the source video file.
        thumb_path: Destination path for the JPEG thumbnail.
        width: Target width in pixels (height is auto-scaled).

    Returns:
        ``True`` if the thumbnail was generated successfully, ``False`` otherwise.
    """
    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-ss",
        THUMBNAIL_SEEK_TIME,
        "-vframes",
        "1",
        "-vf",
        f"scale={width}:-1",
        thumb_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=FFMPEG_THUMBNAIL_TIMEOUT)
        return True
    except Exception:
        logger.error(
            "Failed to generate thumbnail for %s:\n%s",
            os.path.basename(video_path),
            traceback.format_exc(),
        )
        return False
