import json
import subprocess
import time

CATEGORIES = [
    "gta v gameplay no commentary -shorts",
    "minecraft parkour gameplay no commentary -shorts",
    "kinetic sand satisfying video -shorts",
    "soap cutting asmr -shorts",
    "relaxing nature drone footage 1080p -shorts",
    "subway surfers gameplay no commentary -shorts",
    "rocket league gameplay no commentary -shorts",
    "3d satisfying render loop -shorts",
    "slime asmr no talking -shorts",
    "snowboarding gopro 1080p -shorts"
]

results = []

for category in CATEGORIES:
    print(f"Searching for: {category}")
    # ytsearch20 to have buffer for filtering
    command = [
        "yt-dlp",
        f"ytsearch20:{category}",
        "--dump-json",
        "--default-search", "ytsearch",
        "--no-playlist",
        "--match-filter", "duration > 300 & duration < 900",
        "--lazy-playlist"
    ]
    
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        
        count = 0
        for line in stdout.split('\n'):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                # Check for shorts by duration or keywords just in case
                title = data.get("title", "").lower()
                if "shorts" in title or data.get("duration", 0) < 300:
                    continue
                
                results.append({
                    "category": category,
                    "title": data.get("title"),
                    "url": data.get("webpage_url"),
                    "duration": data.get("duration")
                })
                count += 1
                if count >= 10:
                    break
            except Exception as e:
                pass
    except Exception as e:
        print(f"Error searching {category}: {e}")

    time.sleep(2) # be nice to youtube

with open("videos_to_download.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=4)

print(f"Found {len(results)} videos.")
