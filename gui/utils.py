import os
import shutil
import sys
import urllib.request
import urllib.parse
import json
import time
import subprocess
from openai import OpenAI
import questionary

from gui.state import state, settings
from gui.config import (
    BASE_DIR, VIDEOS_DIR, MUSIC_DIR, logger, console,
    save_settings
)

DEFAULT_VIDEO_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
DEFAULT_MUSIC_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"

def make_preset_path_relative(path):
    if not path or path == "random":
        return path
    if path.startswith(BASE_DIR):
        return os.path.relpath(path, BASE_DIR)
    return path

def resolve_preset_path(path):
    if not path:
        return None
    if path == "random":
        return "random"
    if os.path.isabs(path):
        if os.path.exists(path):
            return path
        parts = path.split(os.sep)
        if "videos" in parts:
            idx = parts.index("videos")
            subpath = os.path.join(*parts[idx:])
            full = os.path.join(BASE_DIR, subpath)
            if os.path.exists(full):
                return full
        if "music" in parts:
            idx = parts.index("music")
            subpath = os.path.join(*parts[idx:])
            full = os.path.join(BASE_DIR, subpath)
            if os.path.exists(full):
                return full
        return path
    else:
        full = os.path.join(BASE_DIR, path)
        if os.path.exists(full):
            return full
        return path

def refresh_opencode_token(auth_path, data):
    openai_data = data.get("openai", {})
    refresh_token = openai_data.get("refresh")
    if not refresh_token:
        return None
        
    url = "https://auth.openai.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
        "refresh_token": refresh_token
    }
    try:
        req_data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            new_access = res_data.get("access_token")
            new_refresh = res_data.get("refresh_token")
            expires_in = res_data.get("expires_in", 3600)
            
            openai_data["access"] = new_access
            openai_data["refresh"] = new_refresh
            openai_data["expires"] = int((time.time() + expires_in) * 1000)
            data["openai"] = openai_data
            
            with open(auth_path, "w") as f:
                json.dump(data, f, indent=2)
            return new_access
    except Exception:
        pass
    return None

def discover_opencode_keys():
    opencode_auth_path = "/root/.local/share/opencode/auth.json"
    # Adjust path if on Windows (e.g. standard local share location or just fallback if doesn't exist)
    if os.name == 'nt':
        # On Windows, local share might correspond to AppData/Local
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            opencode_auth_path = os.path.join(local_app_data, "opencode", "auth.json")
            
    if os.path.exists(opencode_auth_path):
        try:
            with open(opencode_auth_path, "r") as f:
                data = json.load(f)
            opencode_key = data.get("opencode-go", {}).get("key")
            openai_data = data.get("openai", {})
            openai_token = openai_data.get("access")
            expires = openai_data.get("expires", 0)
            
            # If expired or close to expiring (within 2 minutes), refresh
            if openai_token and expires and (expires < time.time() * 1000 + 120000):
                new_token = refresh_opencode_token(opencode_auth_path, data)
                if new_token:
                    openai_token = new_token
            return opencode_key, openai_token
        except Exception:
            pass
    return None, None

def check_system_dependencies():
    ffmpeg_found = shutil.which("ffmpeg") is not None
    ffprobe_found = shutil.which("ffprobe") is not None
    
    # Check for emoji fonts to prevent square glyphs ("tofu")
    if shutil.which("fc-list") is not None:
        try:
            res = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True)
            families = res.stdout.lower()
            if not ("symbola" in families or "emoji" in families):
                console.print("[bold yellow]Warning: No emoji or symbol fonts detected. Subtitle emojis may render as squares.[/]")
                apt_found = shutil.which("apt-get") is not None
                if apt_found:
                    console.print("[yellow]Attempting to install 'fonts-symbola' via apt-get...[/]")
                    try:
                        is_root = False
                        if hasattr(os, "getuid"):
                            is_root = os.getuid() == 0
                        cmd_prefix = [] if is_root else ["sudo"]
                        subprocess.run(cmd_prefix + ["apt-get", "update", "-y"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.run(cmd_prefix + ["apt-get", "install", "-y", "fonts-symbola"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        console.print("[green]Successfully installed 'fonts-symbola'![/]")
                    except Exception as e:
                        logger.warning(f"Failed to auto-install 'fonts-symbola': {e}", exc_info=True)
                        console.print(f"[yellow]Auto-installation of fonts-symbola failed. Emojis may render as squares.[/]")
        except Exception as e:
            logger.warning(f"Error checking system fonts: {e}", exc_info=True)

    if ffmpeg_found and ffprobe_found:
        return
        
    logger.error("System dependencies 'ffmpeg' or 'ffprobe' are missing.")
    console.print("[bold yellow]System dependencies 'ffmpeg' or 'ffprobe' are missing.[/]")
    
    apt_found = shutil.which("apt-get") is not None
    if apt_found:
        console.print("[yellow]Attempting to install 'ffmpeg' using apt-get...[/]")
        try:
            is_root = False
            if hasattr(os, "getuid"):
                is_root = os.getuid() == 0
            cmd_prefix = [] if is_root else ["sudo"]
            
            console.print("[yellow]Running: apt-get update -y[/]")
            subprocess.run(cmd_prefix + ["apt-get", "update", "-y"], check=True)
            
            console.print("[yellow]Running: apt-get install -y ffmpeg[/]")
            subprocess.run(cmd_prefix + ["apt-get", "install", "-y", "ffmpeg"], check=True)
            
            # Recheck
            if shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None:
                console.print("[green]Successfully installed ffmpeg/ffprobe via apt-get.[/]")
                return
        except Exception as e:
            logger.error(f"Auto-installation of ffmpeg failed: {e}", exc_info=True)
            console.print(f"[red]Auto-installation failed: {e}[/]")
            
    logger.error("Required system packages 'ffmpeg' and 'ffprobe' could not be resolved automatically.")
    console.print("[bold red]Please install ffmpeg and ffprobe manually to proceed.[/]")
    console.print("Instructions:")
    console.print("- Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y ffmpeg")
    console.print("- macOS: brew install ffmpeg")
    console.print("- Windows: scoop install ffmpeg or choco install ffmpeg")
    sys.exit(1)

def extract_keywords_from_script(script_text: str) -> str:
    api_key = settings.get("api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = settings.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    default_model = settings.get("model", "gpt-4o-mini")
    model = default_model
    
    opencode_key, _ = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and not base_url:
            base_url = "https://opencode.ai/zen/go/v1"
            
    if not api_key:
        return ""
        
    if base_url and "opencode.ai" in base_url:
        model = "deepseek-v4-flash"
        
    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": "You are a visual research assistant. Analyze the video script and return exactly ONE search term (1-2 words, e.g., 'calm forest', 'neon city', 'space stars') that would make an excellent vertical background loop. Return ONLY the raw search term text with no quotes, punctuation, or explanations."
                },
                {"role": "user", "content": script_text}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip().replace('"', '')
    except Exception as e:
        logger.warning(f"Failed to extract keywords via LLM: {e}")
        return ""

def auto_download_pexels_background(position="top"):
    script = state["script_text"].strip()
    if not script:
        console.print("[red]Error: Script is empty. Please generate or edit a script first to extract keywords.[/]")
        return
        
    pexels_key = settings.get("pexels_api_key", "").strip()
    if not pexels_key:
        console.print("[yellow]Pexels API Key is missing. You can get a free key at https://www.pexels.com/api/[/]")
        pexels_key = questionary.password("Please enter your Pexels API Key to proceed:").ask()
        if not pexels_key:
            console.print("[yellow]Cancelled API download.[/]")
            return
        settings["pexels_api_key"] = pexels_key.strip()
        save_settings(settings)
        
    console.print("[yellow]Extracting visual background search term from script...[/]")
    keyword = extract_keywords_from_script(script)
    if not keyword:
        keyword = questionary.text("LLM failed to extract search term. Enter search keyword manually:").ask()
        if not keyword:
            return
            
    console.print(f"[green]Extracted keyword search term: [bold cyan]\"{keyword}\"[/][/]")
    console.print(f"[yellow]Searching Pexels for vertical videos matching \"{keyword}\"...[/]")
    
    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(keyword)}&orientation=portrait&per_page=10"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": pexels_key,
            "User-Agent": "Mozilla/5.0"
        }
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        console.print(f"[red]Failed to search Pexels API: {e}[/]")
        logger.error(f"Pexels search failed: {e}", exc_info=True)
        return
        
    videos = res_data.get("videos", [])
    if not videos:
        console.print(f"[red]No videos found on Pexels for query \"{keyword}\".[/]")
        return
        
    console.print(f"\n[cyan]Found {len(videos)} matching vertical videos on Pexels. Select one to download:[/]")
    choices = []
    for idx, v in enumerate(videos[:5]):
        duration = v.get("duration", 0)
        user_name = v.get("user", {}).get("name", "Unknown Artist")
        choices.append(questionary.Choice(
            title=f"📹 Video #{idx+1} by {user_name} ({duration}s duration)",
            value=v
        ))
    choices.append(questionary.Choice("<- Cancel", "cancel"))
    
    selected_video = questionary.select("Select background video to download:", choices=choices).ask()
    if not selected_video or selected_video == "cancel":
        return
        
    video_files = selected_video.get("video_files", [])
    if not video_files:
        console.print("[red]Error: Selected video has no downloadable files.[/]")
        return
        
    vertical_files = [vf for vf in video_files if (vf.get("width") or 0) < (vf.get("height") or 0)]
    files_to_check = vertical_files if vertical_files else video_files
    
    best_file = sorted(files_to_check, key=lambda x: x.get("width") or 0, reverse=True)[0]
    download_url = best_file.get("link")
    
    if not download_url:
        console.print("[red]Error: Selected video file has no direct download link.[/]")
        return
        
    clean_keyword = "".join(c for c in keyword.lower() if c.isalnum() or c == " ").replace(" ", "_")
    filename = f"pexels_{clean_keyword}_{selected_video.get('id')}.mp4"
    dest_path = os.path.join(VIDEOS_DIR, filename)
    
    console.print(f"[yellow]Downloading video file ({best_file.get('width')}x{best_file.get('height')})...[/]")
    try:
        from generator import download_file
        download_file(download_url, dest_path, f"Pexels Video: {filename}")
        
        state_key = "bg_video_path" if position == "top" else "bg_video_bottom_path"
        state[state_key] = dest_path
        pos_label = "TOP (Primary Video)" if position == "top" else "BOTTOM (Satisfying Loop)"
        console.print(f"[green]Successfully downloaded and configured background video for {pos_label}: {filename}[/]")
    except Exception as e:
        console.print(f"[red]Failed to download Pexels video: {e}[/]")
        logger.error(f"Failed to download Pexels video: {e}", exc_info=True)

def download_default_assets_if_empty():
    from generator import download_file
    
    # Check background videos
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    video_files = [f for f in os.listdir(VIDEOS_DIR) if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.avi'))]
    if not video_files:
        console.print("[bold yellow]No background videos found in videos/. Downloading a default loop...[/]")
        dest_video = os.path.join(VIDEOS_DIR, "default_loop.mp4")
        try:
            download_file(DEFAULT_VIDEO_URL, dest_video, "Default Video Loop (Big Buck Bunny)")
            state["bg_video_path"] = dest_video
            console.print("[green]Successfully downloaded and selected default loop video.[/]")
        except Exception as e:
            logger.error(f"Failed to download default video loop from {DEFAULT_VIDEO_URL}: {e}", exc_info=True)
            console.print(f"[red]Failed to download default video loop: {e}[/]")
    else:
        # Default to the most recently modified video if not already set
        if not state.get("bg_video_path"):
            latest_video = sorted(video_files, key=lambda x: os.path.getmtime(os.path.join(VIDEOS_DIR, x)), reverse=True)[0]
            state["bg_video_path"] = os.path.join(VIDEOS_DIR, latest_video)
        
    # Check background music
    os.makedirs(MUSIC_DIR, exist_ok=True)
    music_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac'))]
    if not music_files:
        console.print("[bold yellow]No music tracks found in music/. Downloading default background music...[/]")
        dest_music = os.path.join(MUSIC_DIR, "default_music.mp3")
        try:
            download_file(DEFAULT_MUSIC_URL, dest_music, "Default Background Music (SoundHelix Song 1)")
            state["bg_music_path"] = dest_music
            console.print("[green]Successfully downloaded and selected default music track.[/]")
        except Exception as e:
            logger.error(f"Failed to download default music track from {DEFAULT_MUSIC_URL}: {e}", exc_info=True)
            console.print(f"[red]Failed to download default music track: {e}[/]")
    else:
        # Default to the most recently modified music track if not already set
        if not state.get("bg_music_path"):
            latest_music = sorted(music_files, key=lambda x: os.path.getmtime(os.path.join(MUSIC_DIR, x)), reverse=True)[0]
            state["bg_music_path"] = os.path.join(MUSIC_DIR, latest_music)
