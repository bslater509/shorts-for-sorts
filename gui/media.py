"""Media streaming, thumbnail generation, and file-serving utilities."""

import mimetypes
import os
import subprocess
import traceback

from fastapi import Header, HTTPException
from fastapi.responses import StreamingResponse

from gui.config import MUSIC_DIR, OUTPUT_DIR, VIDEOS_DIR, logger


def stream_media(file_path: str, range_header: str | None):
    """Range-request-aware media streamer for iOS Safari compatibility."""
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    file_size = os.path.getsize(file_path)
    start = 0
    end = file_size - 1

    if range_header:
        range_str = range_header.replace("bytes=", "").split("-")
        try:
            start = int(range_str[0])
            if len(range_str) > 1 and range_str[1]:
                end = int(range_str[1])
        except ValueError:
            pass

    end = min(end, file_size - 1)
    chunk_size = end - start + 1

    def get_chunk():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = chunk_size
            while remaining > 0:
                data = f.read(min(remaining, 1024 * 1024))
                if not data:
                    break
                yield data
                remaining -= len(data)

    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": content_type,
    }

    if range_header:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        status_code = 206
    else:
        status_code = 200

    return StreamingResponse(get_chunk(), status_code=status_code, headers=headers)


def _safe_path(base_dir: str, filename: str) -> str:
    """Resolve a safe file path, preventing directory traversal."""
    safe_path = os.path.realpath(os.path.join(base_dir, filename))
    if not safe_path.startswith(os.path.realpath(base_dir)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return safe_path


def serve_video(filename: str, range_: str = Header(None)):
    return stream_media(_safe_path(VIDEOS_DIR, filename), range_)


def serve_music(filename: str, range_: str = Header(None)):
    return stream_media(_safe_path(MUSIC_DIR, filename), range_)


def serve_output(filename: str, range_: str = Header(None)):
    return stream_media(_safe_path(OUTPUT_DIR, filename), range_)


def generate_video_thumbnail(video_path: str, thumb_path: str, width: int = 480) -> bool:
    """Extract a thumbnail frame from a video at the 2-second mark."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-ss",
        "00:00:02",
        "-vframes",
        "1",
        "-vf",
        f"scale={width}:-1",
        thumb_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=15)
        return True
    except Exception:
        logger.error(
            "Failed to generate thumbnail for %s:\n%s",
            os.path.basename(video_path),
            traceback.format_exc(),
        )
        return False
