import json
import subprocess
import os

with open("/mnt/gb250/shorts-for-sorts/videos_to_download.json", "r") as f:
    videos = json.load(f)

output_dir = "/mnt/gb250/shorts-for-sorts/videos"
os.makedirs(output_dir, exist_ok=True)

total = len(videos)
for i, v in enumerate(videos, 1):
    print(f"[{i}/{total}] Downloading: {v['title']}")
    
    # Ensure it's max 1080p and mp4 format
    command = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", os.path.join(output_dir, "%(title)s [%(id)s].%(ext)s"),
        v["url"]
    ]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to download {v['title']}: {e}")

print("Download complete!")
