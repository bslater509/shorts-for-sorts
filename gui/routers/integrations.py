"""Third-party integration routes: Pexels, YouTube."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

import gui.state as shared_state
import gui.thumbnail_cache as thumbnail_cache
from gui.config import GUI_STATE_FILE, VIDEOS_DIR, logger
from gui.models import (
    PexelsDownloadRequest,
    PexelsSearchRequest,
    YoutubeDownloadRequest,
    YoutubeSearchRequest,
)
from gui.ws_manager import notify_clients

router: APIRouter = APIRouter()


# ---------------------------------------------------------------------------
# Pexels
# ---------------------------------------------------------------------------


@router.post("/api/pexels/search")
def search_pexels_api(data: PexelsSearchRequest) -> dict[str, Any]:
    """Search Pexels for vertical-format stock videos.

    Args:
        data: Search request with a non-empty query string.

    Returns:
        List of matching video results with metadata.

    Raises:
        HTTPException: If the Pexels API key is missing or the API call fails.
    """
    pexels_key: str = shared_state.settings.get("pexels_api_key", "").strip()
    if not pexels_key:
        raise HTTPException(
            status_code=400,
            detail="Pexels API Key is missing. Add it in the Settings panel.",
        )

    query: str = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    url: str = (
        f"https://api.pexels.com/videos/search"
        f"?query={urllib.parse.quote(query)}"
        f"&orientation=portrait&per_page=12"
    )
    req = urllib.request.Request(
        url,
        headers={"Authorization": pexels_key, "User-Agent": "Mozilla/5.0"},
    )

    try:
        with urllib.request.urlopen(req) as response:
            res_data: dict[str, Any] = json.loads(
                response.read().decode("utf-8")
            )
            videos_raw: list[dict[str, Any]] = res_data.get("videos", [])

            results: list[dict[str, Any]] = []
            for v in videos_raw:
                video_files: list[dict[str, Any]] = v.get("video_files", [])
                vertical_files: list[dict[str, Any]] = [
                    vf
                    for vf in video_files
                    if (vf.get("width") or 0) < (vf.get("height") or 0)
                ]
                files_to_check: list[dict[str, Any]] = (
                    vertical_files if vertical_files else video_files
                )
                if not files_to_check:
                    continue

                best_file = sorted(
                    files_to_check,
                    key=lambda x: x.get("width") or 0,
                    reverse=True,
                )[0]

                results.append(
                    {
                        "id": v.get("id"),
                        "thumbnail": v.get("image"),
                        "duration": v.get("duration"),
                        "user": v.get("user", {}).get("name", "Unknown Artist"),
                        "width": best_file.get("width"),
                        "height": best_file.get("height"),
                        "download_url": best_file.get("link"),
                    }
                )
            return {"videos": results}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search Pexels: {str(e)}"
        ) from e


@router.post("/api/pexels/download")
def download_pexels_video(
    data: PexelsDownloadRequest, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Download a Pexels video file in the background and auto-select it.

    Args:
        data: Download request with URL, video ID, keyword, and position.
        background_tasks: FastAPI background task manager.

    Returns:
        Status response indicating the download has started.
    """
    pexels_key = shared_state.settings.get("pexels_api_key", "").strip()
    if not pexels_key:
        raise HTTPException(
            status_code=400, detail="Pexels API Key is missing."
        )

    clean_keyword: str = "".join(
        c for c in data.keyword.lower() if c.isalnum() or c == " "
    ).replace(" ", "_")
    filename: str = f"pexels_{clean_keyword}_{data.video_id}.mp4"
    dest_path: str = os.path.join(VIDEOS_DIR, filename)

    def _download_job(url: str, dest: str, pos: str) -> None:
        """Background job to download and set the video as active."""
        try:
            from generator import download_file

            logger.info("[Pexels Download] Starting download for %s as %s video.", url, pos)
            notify_clients(
                "pexels_download",
                "info",
                f"Pexels download started for {pos} video...",
                level="info",
            )

            download_file(url, dest, f"Pexels Video: {filename}")
            state_key: str = (
                "bg_video_path" if pos == "top" else "bg_video_bottom_path"
            )
            shared_state.state[state_key] = dest

            with open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(shared_state.state, f, indent=2)

            logger.info(
                "[Pexels Download] Successfully downloaded to %s and set as %s video.",
                dest_path,
                pos,
            )
            notify_clients(
                "pexels_download",
                "success",
                f"Pexels video downloaded and set as {pos} video!",
                level="success",
            )
            thumbnail_cache.enqueue(dest, thumbnail_cache.local_thumb_path(dest))
        except Exception as e:
            logger.error(
                "[Pexels Download] Error downloading video: %s", e, exc_info=True
            )
            notify_clients(
                "pexels_download",
                "error",
                f"Pexels download failed: {e}",
                level="error",
            )

    background_tasks.add_task(_download_job, data.download_url, dest_path, data.position)
    return {
        "status": "pending",
        "message": "Download started in background.",
        "filename": filename,
    }


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------


@router.post("/api/youtube/download")
def download_youtube_video(
    data: YoutubeDownloadRequest, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Download a YouTube video in the background using yt-dlp.

    Args:
        data: Download request with URL and optional downscale flag.
        background_tasks: FastAPI background task manager.

    Returns:
        Status response indicating the download has started.
    """
    url: str = data.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL is missing.")

    # Validate URL scheme to prevent SSRF attacks
    import urllib.parse as _urlparse

    _parsed = _urlparse.urlparse(url)
    if _parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL scheme. Only http/https URLs are allowed.",
        )

    def _download_job(yt_url: str, downscale: bool) -> None:
        """Background job to download the video."""
        try:
            logger.info(
                "[YouTube] Starting download for %s (downscale: %s)",
                yt_url,
                downscale,
            )
            notify_clients(
                "youtube_download",
                "info",
                "YouTube download started...",
                level="info",
            )
            import subprocess

            timestamp: int = int(time.time())
            filename_template: str = f"youtube_{timestamp}_%(title)s.%(ext)s"
            dest_path: str = os.path.join(VIDEOS_DIR, filename_template)

            cmd: list[str] = [
                "yt-dlp",
                "--merge-output-format",
                "mp4",
                "--restrict-filenames",
                "--newline",
            ]
            if downscale:
                cmd.extend(
                    [
                        "-f",
                        "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
                    ]
                )
            else:
                cmd.extend(["-f", "bestvideo+bestaudio/best"])

            cmd.extend(["-o", dest_path, yt_url])

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info("[YouTube] %s", line)

            process.wait()

            if process.returncode != 0:
                logger.error(
                    "[YouTube] Error downloading: yt-dlp exited with code %d",
                    process.returncode,
                )
                notify_clients(
                    "youtube_download",
                    "error",
                    "YouTube download failed.",
                    level="error",
                )
            else:
                logger.info("[YouTube] Successfully downloaded %s", yt_url)
                notify_clients(
                    "youtube_download",
                    "success",
                    "YouTube download completed!",
                    level="success",
                )
                import glob as _glob
                pattern = os.path.join(VIDEOS_DIR, f"youtube_{timestamp}_*")
                for match in _glob.glob(pattern):
                    if os.path.isfile(match):
                        thumbnail_cache.enqueue(
                            match, thumbnail_cache.local_thumb_path(match)
                        )
        except Exception as e:
            logger.error(
                "[YouTube] Error downloading video: %s", e, exc_info=True
            )
            notify_clients(
                "youtube_download",
                "error",
                f"YouTube download error: {e}",
                level="error",
            )

    background_tasks.add_task(_download_job, url, data.downscale)
    return {
        "status": "pending",
        "message": "YouTube download started in background.",
    }


@router.post("/api/youtube/search")
def search_youtube_api(data: YoutubeSearchRequest) -> dict[str, Any]:
    """Search YouTube videos using yt-dlp.

    Args:
        data: Search request with a query and optional result limit.

    Returns:
        List of video search results with metadata.
    """
    query = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        import subprocess

        cmd: list[str] = [
            "yt-dlp",
            f"ytsearch{data.limit}:{query}",
            "--dump-json",
            "--no-playlist",
            "--default-search",
            "ytsearch",
            "--ignore-errors",
        ]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        results: list[dict[str, Any]] = []
        for line in process.stdout.splitlines():
            if not line.strip():
                continue
            try:
                import json as _json

                info: dict[str, Any] = _json.loads(line)

                duration_sec: int = info.get("duration", 0)
                if duration_sec:
                    mins, secs = divmod(duration_sec, 60)
                    duration_str: str = f"{int(mins)}:{int(secs):02d}"
                else:
                    duration_str = "Unknown"

                results.append(
                    {
                        "id": info.get("id"),
                        "title": info.get("title"),
                        "duration": duration_sec,
                        "duration_str": duration_str,
                        "url": info.get("webpage_url")
                        or f"https://www.youtube.com/watch?v={info.get('id')}",
                        "uploader": info.get("uploader", "Unknown Channel"),
                        "thumbnail": info.get("thumbnail")
                        or (
                            info.get("thumbnails", [{}])[-1].get("url")
                            if info.get("thumbnails")
                            else None
                        ),
                    }
                )
            except Exception as e:
                logger.warning("Error parsing yt-dlp line: %s", e)

        return {"videos": results}
    except Exception as e:
        logger.error("[YouTube Search] Error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to search YouTube: {str(e)}"
        ) from e
