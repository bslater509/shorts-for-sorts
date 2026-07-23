"""Third-party integration routes: Pexels, YouTube, TikTok."""

import json
import os
import threading
import time
import urllib.parse
import urllib.request

from fastapi import APIRouter, BackgroundTasks, HTTPException

import gui.state as shared_state
from gui.config import (
    BASE_DIR,
    GUI_STATE_FILE,
    OUTPUT_DIR,
    VIDEOS_DIR,
    logger,
    save_settings,
)
from gui.models import (
    PexelsDownloadRequest,
    PexelsSearchRequest,
    TiktokUploadRequest,
    YoutubeDownloadRequest,
    YoutubeSearchRequest,
)
from gui.ws_manager import notify_clients

router = APIRouter()


@router.post("/api/pexels/search")
def search_pexels_api(data: PexelsSearchRequest):
    pexels_key = shared_state.settings.get("pexels_api_key", "").strip()
    if not pexels_key:
        raise HTTPException(
            status_code=400, detail="Pexels API Key is missing. Add it in the Settings panel."
        )

    query = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&orientation=portrait&per_page=12"
    req = urllib.request.Request(
        url, headers={"Authorization": pexels_key, "User-Agent": "Mozilla/5.0"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            videos_raw = res_data.get("videos", [])

            results = []
            for v in videos_raw:
                # Find download vertical video links
                video_files = v.get("video_files", [])
                vertical_files = [
                    vf for vf in video_files if (vf.get("width") or 0) < (vf.get("height") or 0)
                ]
                files_to_check = vertical_files if vertical_files else video_files

                if not files_to_check:
                    continue

                best_file = sorted(files_to_check, key=lambda x: x.get("width") or 0, reverse=True)[
                    0
                ]

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
        raise HTTPException(status_code=500, detail=f"Failed to search Pexels: {str(e)}")


@router.post("/api/pexels/download")
def download_pexels_video(data: PexelsDownloadRequest, background_tasks: BackgroundTasks):
    pexels_key = shared_state.settings.get("pexels_api_key", "").strip()
    if not pexels_key:
        raise HTTPException(status_code=400, detail="Pexels API Key is missing.")

    clean_keyword = "".join(c for c in data.keyword.lower() if c.isalnum() or c == " ").replace(
        " ", "_"
    )
    filename = f"pexels_{clean_keyword}_{data.video_id}.mp4"
    dest_path = os.path.join(VIDEOS_DIR, filename)

    def download_job(url, dest, pos):
        try:
            from generator import download_file

            logger.info(f"[Pexels Download] Starting download for {url} as {pos} video.")
            notify_clients("pexels_download", "info", f"Pexels download started for {pos} video...", level="info")

            download_file(url, dest, f"Pexels Video: {filename}")
            state_key = "bg_video_path" if pos == "top" else "bg_video_bottom_path"
            shared_state.state[state_key] = dest

            # Persist gui state to disk
            with open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(shared_state.state, f, indent=2)

            logger.info(
                f"[Pexels Download] Successfully downloaded to {dest_path} and set as {pos} video."
            )
            notify_clients("pexels_download", "success", f"Pexels video downloaded and set as {pos} video!", level="success")
        except Exception as e:
            logger.error(f"[Pexels Download] Error downloading video: {e}")
            notify_clients("pexels_download", "error", f"Pexels download failed: {e}", level="error")

    background_tasks.add_task(download_job, data.download_url, dest_path, data.position)
    return {"status": "pending", "message": "Download started in background.", "filename": filename}


@router.post("/api/youtube/download")
def download_youtube_video(data: YoutubeDownloadRequest, background_tasks: BackgroundTasks):
    url = data.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL is missing.")
    # Validate URL scheme to prevent SSRF attacks
    import urllib.parse as _urlparse

    _parsed = _urlparse.urlparse(url)
    if _parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400, detail="Invalid URL scheme. Only http/https URLs are allowed."
        )

    def download_job(yt_url, downscale):
        try:
            logger.info(f"[YouTube] Starting download for {yt_url} (downscale: {downscale})")
            notify_clients("youtube_download", "info", "YouTube download started...", level="info")
            import subprocess

            timestamp = int(time.time())
            filename_template = f"youtube_{timestamp}_%(title)s.%(ext)s"
            dest_path = os.path.join(VIDEOS_DIR, filename_template)

            cmd = ["yt-dlp", "--merge-output-format", "mp4", "--restrict-filenames", "--newline"]
            if downscale:
                cmd.extend(["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best"])
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
                    logger.info(f"[YouTube] {line}")
                    
            process.wait()
            
            if process.returncode != 0:
                logger.error(f"[YouTube] Error downloading: yt-dlp exited with code {process.returncode}")
                notify_clients("youtube_download", "error", "YouTube download failed.", level="error")
            else:
                logger.info(f"[YouTube] Successfully downloaded {yt_url}")
                notify_clients("youtube_download", "success", "YouTube download completed!", level="success")
        except Exception as e:
            logger.error(f"[YouTube] Error downloading video: {e}")
            notify_clients("youtube_download", "error", f"YouTube download error: {e}", level="error")

    background_tasks.add_task(download_job, url, data.downscale)
    return {"status": "pending", "message": "YouTube download started in background."}


@router.post("/api/youtube/search")
def search_youtube_api(data: YoutubeSearchRequest):
    query = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    try:
        import subprocess
        import json as _json
        cmd = ["yt-dlp", f"ytsearch{data.limit}:{query}", "--dump-json", "--no-playlist", "--default-search", "ytsearch", "--ignore-errors"]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        results = []
        for line in process.stdout.splitlines():
            if not line.strip(): continue
            try:
                info = _json.loads(line)
                
                # Format duration string
                duration_sec = info.get("duration", 0)
                if duration_sec:
                    mins, secs = divmod(duration_sec, 60)
                    duration_str = f"{int(mins)}:{int(secs):02d}"
                else:
                    duration_str = "Unknown"
                    
                results.append({
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "duration": duration_sec,
                    "duration_str": duration_str,
                    "url": info.get("webpage_url") or f"https://www.youtube.com/watch?v={info.get('id')}",
                    "uploader": info.get("uploader", "Unknown Channel"),
                    "thumbnail": info.get("thumbnail") or (info.get("thumbnails", [{}])[-1].get("url") if info.get("thumbnails") else None)
                })
            except Exception as e:
                logger.warning(f"Error parsing yt-dlp line: {e}")
                pass
                
        return {"videos": results}
    except Exception as e:
        logger.error(f"[YouTube Search] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search YouTube: {str(e)}")


@router.post("/api/tiktok/upload")
def upload_tiktok_video(data: TiktokUploadRequest, background_tasks: BackgroundTasks):
    sessionid = shared_state.settings.get("tiktok_sessionid", "").strip()
    if not sessionid:
        raise HTTPException(
            status_code=400, detail="TikTok session ID is missing. Add it in Settings."
        )

    video_path = os.path.join(OUTPUT_DIR, data.filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    def upload_job():
        try:
            logger.info(f"[TikTok] Starting background upload for {data.filename}")
            import asyncio

            from gui.tiktok_uploader import upload_video

            asyncio.run(upload_video(sessionid, video_path, data.description, data.visibility))
            logger.info(f"[TikTok] Successfully uploaded {data.filename}")
        except Exception as e:
            logger.error(f"[TikTok] Upload failed: {e}")

    background_tasks.add_task(upload_job)
    return {"status": "pending", "message": "TikTok upload started in background."}


@router.post("/api/tiktok/login")
def login_tiktok_browser():
    try:
        logger.info("[TikTok] Launching browser for login...")
        import asyncio

        from gui.tiktok_uploader import login_to_tiktok

        # Run in a separate thread so we don't block the async event loop of fastapi
        def run_login():
            try:
                sid = asyncio.run(login_to_tiktok())
                if sid:
                    shared_state.settings["tiktok_sessionid"] = sid
                    save_settings(shared_state.settings)
                    logger.info("[TikTok] Login successful, saved sessionid.")
                    logger.warning(
                        "[TikTok] Session ID stored in plaintext in config/settings.json. "
                        "Keep this file secure and do not commit it."
                    )
                else:
                    logger.warning("[TikTok] Login finished but no sessionid was found.")
            except Exception as e:
                logger.error(f"[TikTok] Error during login: {e}")

        threading.Thread(target=run_login, daemon=True).start()
        return {
            "status": "pending",
            "message": "Browser opened for TikTok login. Please complete login in the new window.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open login browser: {e}")
