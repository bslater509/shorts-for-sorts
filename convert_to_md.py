import json
import os

with open("/mnt/gb250/shorts-for-sorts/videos_to_download.json", "r") as f:
    videos = json.load(f)

artifact_dir = "/root/.gemini/antigravity-cli/brain/cdf2a77c-ba56-4bd5-b2c0-1d9cbc17769e"
artifact_path = os.path.join(artifact_dir, "videos_to_download_review.md")

md_content = "# YouTube Background Videos Review\n\n"
md_content += f"Here is the list of {len(videos)} videos found across 10 categories matching your criteria (horizontal, 1080p, 5-15 mins). *Note: Some categories had fewer than 10 exact matches due to the strict 5-15 minute filter. Let me know if you approve this list or if we should fetch more to hit exactly 100.*\n\n"

current_category = ""
for v in videos:
    if v["category"] != current_category:
        current_category = v["category"]
        cat_name = current_category.replace(" -shorts", "").title()
        md_content += f"\n## {cat_name}\n"
        md_content += "| Title | Duration | URL |\n| --- | --- | --- |\n"
    
    mins = v['duration'] // 60
    secs = v['duration'] % 60
    dur_str = f"{mins}:{secs:02d}"
    
    # Escape pipes in titles
    title = v['title'].replace('|', '&#124;')
    
    md_content += f"| {title} | {dur_str} | [Link]({v['url']}) |\n"

with open(artifact_path, "w") as f:
    f.write(md_content)
