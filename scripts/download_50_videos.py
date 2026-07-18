import json
import os
import subprocess
import time

CATEGORIES = [
    "cs go surf gameplay no commentary -shorts",
    "asmr cooking baking no talking -shorts",
    "trackmania gameplay no commentary -shorts",
    "power washing simulator gameplay no commentary -shorts",
    "abstract relaxing fractals 3d loop -shorts",
    "city walking tours 1080p no talking -shorts"
]

TARGET_TOTAL = 50
PER_CATEGORY = TARGET_TOTAL // len(CATEGORIES) + 1  # 9 per category

json_path = "/mnt/gb250/shorts-for-sorts/videos_to_download.json"
output_dir = "/mnt/gb250/shorts-for-sorts/videos"

# Load existing
try:
    with open(json_path, "r", encoding="utf-8") as f:
        existing_data = json.load(f)
except FileNotFoundError:
    existing_data = []

existing_urls = {v.get("url") for v in existing_data if v.get("url")}
new_videos = []

total_downloaded = 0

for category in CATEGORIES:
    if total_downloaded >= TARGET_TOTAL:
        break
        
    print(f"\n--- Searching for: {category} ---")
    # Search for up to 15 to account for duplicates/shorts
    command = [
        "yt-dlp",
        f"ytsearch15:{category}",
        "--dump-json",
        "--default-search",
        "ytsearch",
        "--no-playlist",
        "--match-filter",
        "duration > 300 & duration < 1200",
        "--lazy-playlist"
    ]
    
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = process.communicate()
        
        count = 0
        for line in stdout.split("\n"):
            if not line.strip():
                continue
            if count >= PER_CATEGORY or total_downloaded >= TARGET_TOTAL:
                break
            try:
                data = json.loads(line)
                url = data.get("webpage_url")
                if not url or url in existing_urls:
                    continue
                    
                title = data.get("title", "")
                if "shorts" in title.lower() or data.get("duration", 0) < 300 or data.get("duration", 0) > 1200:
                    continue
                    
                vid_info = {
                    "category": category,
                    "title": title,
                    "url": url,
                    "duration": data.get("duration"),
                }
                new_videos.append(vid_info)
                existing_urls.add(url)
                
                print(f"[{total_downloaded+1}/{TARGET_TOTAL}] Downloading: {title}")
                # Download
                dl_command = [
                    "yt-dlp",
                    "-f",
                    "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "-o",
                    os.path.join(output_dir, "%(title)s [%(id)s].%(ext)s"),
                    url
                ]
                subprocess.run(dl_command, check=True)
                
                count += 1
                total_downloaded += 1
            except Exception as e:
                print(f"Failed parsing or downloading: {e}")
                
    except Exception as e:
        print(f"Error searching {category}: {e}")
        
    time.sleep(2)

# Save updated json
existing_data.extend(new_videos)
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(existing_data, f, indent=4)

print(f"\nSuccessfully found and downloaded {len(new_videos)} videos.")
