"""Video/music assets and gallery routes."""

import os
import re
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

import gui.state as shared_state
from gui.config import (
    MUSIC_DIR,
    OUTPUT_DIR,
    THUMBNAIL_DIR,
    VIDEOS_DIR,
    logger,
)
from gui.media import generate_video_thumbnail

router = APIRouter()


@router.get("/api/assets/videos")
def list_assets_videos():
    if not os.path.exists(VIDEOS_DIR):
        return []
    videos = []
    for f in os.listdir(VIDEOS_DIR):
        if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
            fp = os.path.join(VIDEOS_DIR, f)
            size = os.path.getsize(fp)
            modified = os.path.getmtime(fp)
            videos.append(
                {"filename": f, "url": f"/videos/{f}", "size": size, "modified": modified}
            )
    # Sort by modified time (newest first)
    videos.sort(key=lambda x: x["modified"], reverse=True)
    return videos


@router.post("/api/assets/videos")
def upload_assets_video(file: UploadFile = File(...)):
    safe = "".join(c for c in file.filename if c.isalnum() or c in (".", "_", "-"))
    filename = safe.lstrip(".")[:255] or "unnamed_file"
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Save the file to videos/
    dest_path = os.path.join(VIDEOS_DIR, filename)
    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"status": "success", "filename": filename, "url": f"/videos/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {e}")


@router.delete("/api/assets/videos/{filename}")
def delete_assets_video(filename: str):
    # Safety checks
    filename = os.path.basename(filename)
    dest_path = os.path.join(VIDEOS_DIR, filename)
    if not os.path.exists(dest_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    try:
        os.remove(dest_path)
        # Clear state paths if it matches
        if shared_state.state["bg_video_path"] == dest_path:
            shared_state.state["bg_video_path"] = None
        if shared_state.state["bg_video_bottom_path"] == dest_path:
            shared_state.state["bg_video_bottom_path"] = None
        return {"status": "success", "message": "Video deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {e}")


@router.get("/api/assets/music")
def list_assets_music():
    if not os.path.exists(MUSIC_DIR):
        return []
    music = []
    for f in os.listdir(MUSIC_DIR):
        if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg", ".flac")):
            fp = os.path.join(MUSIC_DIR, f)
            size = os.path.getsize(fp)
            modified = os.path.getmtime(fp)
            music.append({"filename": f, "url": f"/music/{f}", "size": size, "modified": modified})
    # Sort by modified time
    music.sort(key=lambda x: x["modified"], reverse=True)
    return music


@router.post("/api/assets/music")
def upload_assets_music(file: UploadFile = File(...)):
    safe = "".join(c for c in file.filename if c.isalnum() or c in (".", "_", "-"))
    filename = safe.lstrip(".")[:255] or "unnamed_file"
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    dest_path = os.path.join(MUSIC_DIR, filename)
    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"status": "success", "filename": filename, "url": f"/music/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload music: {e}")


@router.delete("/api/assets/music/{filename}")
def delete_assets_music(filename: str):
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


@router.get("/api/gallery")
def list_gallery_videos():
    if not os.path.exists(OUTPUT_DIR):
        return []
    videos = []
    for f in os.listdir(OUTPUT_DIR):
        if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
            fp = os.path.join(OUTPUT_DIR, f)
            size = os.path.getsize(fp)
            modified = os.path.getmtime(fp)

            # Read duration using basic check or placeholder
            duration = None
            try:
                from generator import get_video_info

                info = get_video_info(fp, suppress_errors=True)
                duration = info.get("duration")
            except Exception:
                pass

            title = ""
            hashtags = ""
            txt_file = os.path.splitext(fp)[0] + ".txt"
            if os.path.exists(txt_file):
                try:
                    with open(txt_file, encoding="utf-8") as tf:
                        lines = tf.readlines()
                        if lines:
                            if any(re.match(r"^hashtags?\s*:", line, re.I) for line in lines):
                                # Old format: find line starting with Hashtag(s):
                                for line in lines:
                                    m = re.match(r"^hashtags?\s*:\s*(.*)", line, re.I)
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

            # Thumbnail
            thumb_filename = os.path.splitext(f)[0] + ".jpg"
            thumbnail = f"/api/gallery/thumbnail/{thumb_filename}"

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
    # Sort by newest first
    videos.sort(key=lambda x: x["modified"], reverse=True)
    return videos


@router.delete("/api/gallery/{filename}")
def delete_gallery_video(filename: str):
    filename = os.path.basename(filename)
    dest_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(dest_path):
        raise HTTPException(status_code=404, detail="Compiled video file not found.")

    try:
        os.remove(dest_path)
        basename = os.path.splitext(filename)[0]
        # Remove thumbnail sidecar
        thumb_path = os.path.join(THUMBNAIL_DIR, basename + ".jpg")
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        # Remove metadata sidecar
        meta_path = os.path.join(OUTPUT_DIR, basename + ".txt")
        if os.path.exists(meta_path):
            os.remove(meta_path)
        return {"status": "success", "message": "Compiled video deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {e}")


@router.delete("/api/gallery")
def delete_all_gallery_videos():
    if not os.path.exists(OUTPUT_DIR):
        return {"status": "success", "message": "No videos to delete."}

    try:
        for f in os.listdir(OUTPUT_DIR):
            fp = os.path.join(OUTPUT_DIR, f)
            if os.path.isfile(fp):
                os.remove(fp)
        return {"status": "success", "message": "All generated videos deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete all videos: {e}")


@router.get("/api/gallery/thumbnail/{filename}")
def get_gallery_thumbnail(filename: str):
    """Serve or generate a thumbnail for a gallery video."""
    # Sanitize filename to prevent path traversal
    filename = os.path.basename(filename)
    thumb_path = os.path.join(THUMBNAIL_DIR, filename)

    # If thumbnail already exists, serve it
    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")

    # Try to generate from corresponding video in output/
    base_name = os.path.splitext(filename)[0]
    for ext in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
        video_path = os.path.join(OUTPUT_DIR, base_name + ext)
        if os.path.exists(video_path):
            if generate_video_thumbnail(video_path, thumb_path) and os.path.exists(thumb_path):
                return FileResponse(thumb_path, media_type="image/jpeg")
            break

    raise HTTPException(status_code=404, detail="Thumbnail not found")
