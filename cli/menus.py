import os
import random
import json
import datetime
import shutil
import urllib.request
import urllib.parse
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from rich.live import Live
from openai import OpenAI
import questionary
import yt_dlp

from cli import state as shared_state
from cli.state import VOICES
from cli.config import (
    console, logger, PROMPTS_FILE, PRESETS_FILE, VIDEOS_DIR, MUSIC_DIR, OUTPUT_DIR,
    load_presets, save_custom_preset, delete_custom_preset,
    load_emoji_map, save_emoji_map, save_settings
)
from cli.utils import (
    discover_opencode_keys, resolve_preset_path, make_preset_path_relative,
    auto_download_pexels_background, download_default_assets_if_empty
)
from cli.compiler import compile_video_flow
from cli.batch import batch_job_worker, display_progress_table

DEFAULT_PROMPTS = {
    "Mind-blowing Science Facts": "Write about 3 mind-blowing science facts that sound fake but are 100% real.",
    "Unsolved Historical Mystery": "Write a suspenseful, engaging mystery about the lost colony of Roanoke.",
    "Procrastination Motivation Hack": "Explain the 2-minute rule for beating procrastination and how to start applying it right now.",
    "Chilling Creepypasta Story": "Write a fast-paced, spine-chilling story about a person who gets a text message from their own number.",
    "Time-Saving Life Hacks": "Share 3 simple, practical life hacks that save time in the morning routine.",
    "Dark Psychology Tricks": "Explain 3 subtle dark psychology tricks people use to influence you, and how to defend against them.",
    "Strange Laws Around the World": "Share 3 of the most bizarre laws from different countries that are actually still on the books.",
    "Survival Hacks that Save Lives": "Describe 3 crucial survival tips for extreme scenarios that everyone should memorize.",
    "Mindless Consumerism Traps": "Reveal 3 clever tricks supermarkets and stores use to get you to spend more money without realizing it.",
    "The Paradox of Choice": "Explain the paradox of choice and why having too many options makes us unhappy, in a simple, relatable way.",
    "Bizarre Deep Sea Creatures": "Describe 3 of the weirdest, most terrifying creatures discovered in the deepest parts of the ocean.",
    "How the Pyramids Were Built": "Explain the most popular and fascinating theories about how the Ancient Egyptians constructed the Great Pyramids.",
    "Simple Sleep Hacks": "Share 3 science-backed tips to fall asleep in under 5 minutes and wake up feeling refreshed.",
    "History's Coolest Coincidences": "Tell the story of one of the most unbelievable coincidences in history that shaped the world.",
    "Space Is Way Bigger Than You Think": "Explain the scale of the universe using mind-bending analogies that will make the viewer feel tiny.",
    "Signs of High Intelligence": "Highlight 3 unusual behavioral traits or habits that are scientifically linked to high intelligence.",
    "The Mandela Effect Cases": "Explain the Mandela Effect and share 3 famous examples that will make viewers question their own memory.",
    "Unusual Jobs That Pay Well": "Introduce 3 weird or lesser-known jobs that pay surprisingly high salaries.",
    "How To Read Body Language": "Teach 3 quick tips to read someone's body language instantly, like detecting if they are lying or interested.",
    "Hidden Easter Eggs in Famous Art": "Reveal 3 hidden messages or secrets painted into famous historical artworks like the Mona Lisa or The Last Supper.",
    "The Origin of Common Phrases": "Explain the fascinating, sometimes dark origins of 3 everyday phrases we use without thinking.",
    "Why Time Feels Faster as We Age": "Explain the psychological theory of why years seem to speed up as we grow older, and how to slow it down.",
    "Incredible Animal Superpowers": "Describe 3 animals with incredible, real-life superpowers that seem straight out of comic books.",
    "Quick Memory Improvement Tricks": "Teach 2 memory techniques (like the Memory Palace) that anyone can use to remember lists or names instantly.",
    "Fascinating Psychological Phenomena": "Explain a strange psychological phenomenon, like the Baader-Meinhof phenomenon or Placebo Effect, with a cool example.",
    "Bizarre Science Theories": "Explain a mind-bending, scientifically plausible physics or cosmological theory (like the simulation hypothesis or multiverse) in a simple way.",
    "Ancient Mythological Beasts": "Describe 3 of the most terrifying or fascinating mythical creatures from ancient folklore and their origins.",
    "Stoicism & Mental Toughness": "Explain how to apply the ancient philosophy of Stoicism to manage modern stress and build mental resilience.",
    "How Caffeine Affects Your Brain": "Explain the science of what caffeine actually does to your brain and how to optimize your coffee intake.",
    "Hidden Symbols in Famous Logos": "Reveal the hidden meanings or visual secrets behind 3 famous company logos.",
    "History of the Internet": "Explain a surprising, lesser-known story about how the internet was created or its earliest days.",
    "The Betrayal That Ended an Empire": "Tell the dramatic story of Julius Caesar and Marcus Brutus, focusing on the ultimate betrayal and its shocking consequences.",
    "Hollywood's Most Dramatic Feud": "Describe the intense, decade-long rivalry between Joan Crawford and Bette Davis, and the lengths they went to sabotage each other.",
    "The Most Dramatic Royalty Scandal": "Tell the story of Edward VIII's decision to abdicate the British throne for Wallis Simpson, and the national crisis that followed.",
    "Behind the Scenes Theater Drama": "Tell the historical, dramatic story of the Astor Place Riot of 1849, where a rivalry between two Shakespearean actors led to actual violence in the streets of New York.",
    "The Mystery of the Missing Heiress": "Narrate the mysterious and dramatic disappearance of Dorothy Arnold in 1910, highlighting the shocking theories and family secrets.",
    "Famous Art World Rivals": "Describe the dramatic rivalry between Leonardo da Vinci and Michelangelo, and how their mutual dislike fueled some of the greatest art in history.",
    "The War of the Currents": "Tell the dramatic story of the brutal battle between Thomas Edison and Nikola Tesla over AC vs DC electricity, and the shocking PR stunts used to win.",
    "The Curse of Tutankhamun": "Narrate the drama and mystery surrounding the opening of King Tut's tomb in 1922, highlighting the tragic fates of those involved.",
    "The Poison Cup Duel": "Tell the dramatic, legendary story of the duel between two Renaissance doctors who tried to poison each other to prove whose antidote was superior.",
    "The Shipwreck of the Medusa": "Describe the harrowing, dramatic survival story of the French frigate Méduse in 1816, and the scandalous government cover-up that followed.",
    "The Duel of the Century": "Tell the intense, dramatic story of the fatal 1804 duel between Alexander Hamilton and Aaron Burr, focusing on the decades-long rivalry that led to it.",
    "Reddit AITA Wedding Drama": "Write a dramatic Reddit-style 'Am I the Asshole' post about a bride who cancels her wedding at the altar after finding out a secret about her groom from the maid of honor.",
    "Reddit Secret Inheritance": "Write a dramatic Reddit post from a user who discovered their late grandfather left a massive secret inheritance to them instead of their parents, causing a huge family feud.",
    "Reddit Family DNA Scandal": "Write a suspenseful Reddit post about a person who bought DNA test kits for the family for Christmas, only to accidentally uncover a long-hidden family secret.",
    "Reddit Malicious Compliance": "Write a dramatic Reddit story about a worker who used malicious compliance to expose their micromanaging boss, leading to a complete company restructure.",
    "Reddit Neighbor Property Feud": "Write a dramatic Reddit post about an escalating petty war between two neighbors over a property line that ends in a hilarious, unexpected twist.",
    "Reddit Entitled In-Laws": "Write a dramatic Reddit post about a spouse who finally stood up to their entitled in-laws who tried to take over their home, resulting in a dramatic confrontation.",
    "Reddit Fake Resume Chaos": "Write a dramatic Reddit story about a coworker who lied on their entire resume, got hired for a high-level job, and caused absolute chaos before being spectacularly caught.",
    "Reddit Secret Twin Revelation": "Write a suspenseful Reddit post about a person who discovered they had an identical twin they never knew about, leading to the exposure of a massive family cover-up.",
    "Reddit HOA Revenge": "Write a satisfying Reddit post about a homeowner who took brilliant, malicious compliance revenge against an overreaching, power-tripping HOA board president.",
    "Reddit Fake Lottery Ticket Prank": "Write a dramatic Reddit post about a prank that went way too far when a sibling gave their brother a fake winning lottery ticket, leading to a complete family breakdown.",
    "Reddit AITA Exposing a Liar": "Write an engaging Reddit-style 'Am I the Asshole' post about a user who exposed their friend's fake lifestyle and lies at a group dinner party, causing a split in their friend group.",
    "Reddit Wedding Dress Drama": "Write a dramatic Reddit post about a bride who discovered her future mother-in-law secretly bought a wedding dress identical to hers and planned to wear it to the ceremony.",
    "Reddit Secret Passage Discovery": "Write a suspenseful Reddit story about a tenant who found a hidden door behind a bookshelf in their apartment leading to a secret room containing mysterious items.",
    "Reddit Lottery Ticket Theft": "Write a dramatic Reddit post about a person who won a substantial lottery prize but had the ticket stolen by a trusted family member, resulting in a tense legal standoff.",
    "Reddit High School Reunion Revenge": "Write a satisfying Reddit post about a user who attended their high school reunion and dramatically exposed a former bully who was trying to pitch a fraudulent investment scheme to the attendees.",
    "Reddit Fake Sick Day Catastrophe": "Write a dramatic Reddit story about an employee who called in sick to attend a concert, only to be interviewed live on national television and spotted by their entire company.",
    "Reddit AITA Gender Reveal": "Write an engaging Reddit-style 'Am I the Asshole' post about a guest who accidentally revealed the baby's gender before the official announcement, leading to a massive family fallout."
}

def print_header():
    console.clear()
    console.print("[bold cyan]========================================[/]")
    console.print("[bold cyan]       AI TikTok Shorts Creator        [/]")
    console.print("[bold cyan]========================================[/]")
    console.print()

def load_prompt_templates():
    if not os.path.exists(PROMPTS_FILE):
        try:
            with open(PROMPTS_FILE, "w") as f:
                json.dump(DEFAULT_PROMPTS, f, indent=4)
        except Exception as e:
            logger.warning(f"Could not initialize prompts file {PROMPTS_FILE}: {e}", exc_info=True)
            console.print(f"[red]Warning: Could not initialize prompts file: {e}[/]")
            return DEFAULT_PROMPTS
    try:
        with open(PROMPTS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load prompts file {PROMPTS_FILE}: {e}", exc_info=True)
        console.print(f"[red]Warning: Could not load prompts file, using defaults: {e}[/]")
        return DEFAULT_PROMPTS

def generate_script():
    console.print("[bold yellow]1. SCRIPT GENERATION[/]")
    templates = load_prompt_templates()
    choices = [questionary.Choice(title=k, value=v) for k, v in templates.items()]
    choices.append(questionary.Choice(title="Write Custom Prompt...", value="__custom__"))
    choices.append(questionary.Choice(title="<- Cancel", value="__cancel__"))
    
    selected_template = questionary.select("Select a prompt template or write custom:", choices=choices).ask()
    if not selected_template or selected_template == "__cancel__":
        console.print("[yellow]Generation cancelled.[/]")
        return
        
    if selected_template == "__custom__":
        prompt = questionary.text("Enter prompt/topic for the AI script:").ask()
        if not prompt:
            console.print("[yellow]Generation cancelled: prompt cannot be empty.[/]")
            return
    else:
        prompt = selected_template
        
    voice_choices = [questionary.Choice(title=name, value=val) for name, val in VOICES]
    voice = questionary.select("Select TTS Voice:", choices=voice_choices, default=shared_state.state["selected_voice"]).ask()
    if not voice:
        return
    if voice != shared_state.state["selected_voice"]:
        shared_state.state["selected_voice"] = voice
        shared_state.state["loaded_preset_name"] = None
    
    default_model = shared_state.settings.get("model", "gpt-4o-mini")
    model_override = questionary.text(f"Script Model Name (optional, default: {default_model}):").ask()
    
    # Get settings values
    api_key = shared_state.settings.get("api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = shared_state.settings.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    model = model_override.strip() or default_model
    
    opencode_key, _ = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and not base_url:
            base_url = "https://opencode.ai/zen/go/v1"
            
    if not api_key:
        logger.error("API Key is missing when attempting script generation.")
        console.print("[red]Error: API Key is required to generate script. Set it in Settings.[/]")
        return
        
    if not model:
        if base_url and "opencode.ai" in base_url:
            model = "deepseek-v4-flash"
        else:
            model = "gpt-4o-mini"
            
    console.print(f"[yellow]Generating script using model '{model}'...[/]")
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    max_words = shared_state.settings.get("max_words", 130)
    system_prompt = (
        "You are an expert TikTok and YouTube Shorts content creator. "
        "Write a highly engaging, viral vertical video script about the topic provided by the user. "
        "Guidelines:\n"
        "- Hook: Write a powerful hook in the first 3 seconds to grab attention.\n"
        "- Format: The script should be conversational, punchy, and fast-paced.\n"
        f"- Length: Strictly under {max_words} words (approx. {int(max_words/2.3)} seconds when spoken).\n"
        "- Content: Include 3 key points or a compelling narrative.\n"
        "- Formatting: Output ONLY the spoken words. Do NOT include sound effect cues, stage directions, or brackets like [Music] or [Host]."
    )
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        script_text = response.choices[0].message.content.strip()
        shared_state.state["script_text"] = script_text
        console.print("\n[green]Script successfully generated![/]")
        console.print("[bold white]Preview of script:[/]")
        console.print(f"[italic]{script_text}[/]\n")
    except Exception as e:
        logger.error(f"Script generation failed for prompt '{prompt}': {e}", exc_info=True)
        console.print(f"[red]Script generation failed: {str(e)}[/]")
        console.print("[yellow]Detailed error logs are available in logs/app.log[/]")

def edit_script():
    console.print("[bold yellow]2. EDIT GENERATED SCRIPT (Strictly spoken words only)[/]")
    if not shared_state.state["script_text"]:
        console.print("[yellow]No script generated yet. You can write a new script here or generate one first.[/]")
    
    edited_text = questionary.text(
        "Edit the script below (press Escape then Enter to save/confirm):",
        default=shared_state.state["script_text"],
        multiline=True
    ).ask()
    
    if edited_text is not None:
        shared_state.state["script_text"] = edited_text.strip()
        console.print("[green]Script updated successfully![/]")

def configure_background(position="top"):
    state_key = "bg_video_path" if position == "top" else "bg_video_bottom_path"
    pos_label = "TOP (Primary Video)" if position == "top" else "BOTTOM (Satisfying Loop)"
    
    console.print(f"[bold yellow]3. CONFIGURE BACKGROUND VIDEO - {pos_label}[/]")
    
    # Ensure videos directory exists
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    
    # Gather existing videos in VIDEOS_DIR
    video_files = []
    if os.path.exists(VIDEOS_DIR):
        video_files = [f for f in os.listdir(VIDEOS_DIR) if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.avi'))]
        video_files = sorted(video_files, key=lambda x: os.path.getmtime(os.path.join(VIDEOS_DIR, x)), reverse=True)
        
    choices = []
    current_val = shared_state.state[state_key]
    current_name = "Random Selection" if current_val == "random" else (os.path.basename(current_val) if current_val else "None")
    console.print(f"Current Video: [cyan]{current_name}[/]\n")
    
    for f in video_files:
        size_mb = os.path.getsize(os.path.join(VIDEOS_DIR, f)) // (1024 * 1024)
        choices.append(questionary.Choice(title=f"📹 {f} ({size_mb} MB)", value=f"file:{f}"))
        
    choices.append(questionary.Choice(title="🎲 [Random Video from videos/]", value="random"))
    choices.append(questionary.Choice(title="➕ [Download a new video from YouTube]", value="youtube"))
    choices.append(questionary.Choice(title="📂 [Use an arbitrary local video path]", value="local"))
    choices.append(questionary.Choice(title="<- Back to Main Menu", value="back"))
    
    selected = questionary.select(f"Select background video source for {pos_label}:", choices=choices).ask()
    if not selected or selected == "back":
        return
        
    if selected == "random":
        shared_state.state[state_key] = "random"
        console.print(f"[green]Successfully configured {pos_label} to select a random video on compilation.[/]")
        
    elif selected.startswith("file:"):
        filename = selected[len("file:"):]
        full_path = os.path.join(VIDEOS_DIR, filename)
        if not os.path.exists(full_path):
            console.print(f"[red]Error: Selected video file '{full_path}' does not exist.[/]")
            return
        shared_state.state[state_key] = full_path
        console.print(f"[green]Successfully loaded video for {pos_label}: {filename}[/]")
        
    elif selected == "local":
        local_path = questionary.text("Enter Local File Path:").ask()
        if not local_path:
            return
        if not os.path.exists(local_path):
            console.print(f"[red]Error: Local file path '{local_path}' does not exist.[/]")
            return
        ext = os.path.splitext(local_path)[1].lower()
        if ext not in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
            console.print("[red]Error: Invalid video format. Must be mp4, mov, mkv, webm, or avi.[/]")
            return
            
        original_filename = os.path.basename(local_path)
        dest_path = os.path.join(VIDEOS_DIR, original_filename)
        
        # Avoid conflict by generating a unique name if it already exists
        if os.path.exists(dest_path):
            base, extension = os.path.splitext(original_filename)
            counter = 1
            while os.path.exists(os.path.join(VIDEOS_DIR, f"{base}_{counter}{extension}")):
                counter += 1
            dest_path = os.path.join(VIDEOS_DIR, f"{base}_{counter}{extension}")
            
        console.print(f"[yellow]Copying local video to videos folder: {os.path.basename(dest_path)}...[/]")
        try:
            shutil.copy2(local_path, dest_path)
            shared_state.state[state_key] = dest_path
            console.print(f"[green]Successfully loaded local video for {pos_label}: {os.path.basename(dest_path)}[/]")
        except Exception as e:
            logger.error(f"Failed to copy local video from {local_path} to {dest_path}: {e}", exc_info=True)
            console.print(f"[red]Failed to copy local video: {str(e)}[/]")
            
    elif selected == "youtube":
        yt_url = questionary.text("Enter YouTube URL:").ask()
        if not yt_url:
            return
            
        console.print(f"[yellow]Analyzing YouTube video: {yt_url}...[/]")
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': os.path.join(VIDEOS_DIR, "%(title)s.%(ext)s"),
            'max_filesize': 500 * 1024 * 1024,
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(yt_url, download=False)
                dest_path = ydl.prepare_filename(info)
                
                if os.path.exists(dest_path):
                    console.print(f"[green]Video already exists: {os.path.basename(dest_path)}. Skipping download.[/]")
                    shared_state.state[state_key] = dest_path
                    return
                
                console.print(f"[yellow]Downloading YouTube video: {info.get('title', 'Unknown Title')}...[/]")
                ydl.params['quiet'] = False
                ydl.params['no_warnings'] = False
                info = ydl.extract_info(yt_url, download=True)
                
                downloads = info.get('requested_downloads')
                if downloads and isinstance(downloads, list) and len(downloads) > 0:
                    first_download = downloads[0]
                    if isinstance(first_download, dict):
                        path = (first_download.get('filepath') or 
                                first_download.get('filename') or 
                                first_download.get('_filename'))
                else:
                    path = (info.get('filepath') or 
                            info.get('filename') or 
                            info.get('_filename') or 
                            ydl.prepare_filename(info))
                            
            if not os.path.exists(path) or path.endswith(".part"):
                filename = os.path.basename(dest_path)
                matching = [f for f in os.listdir(VIDEOS_DIR) if f.startswith(os.path.splitext(filename)[0]) and not f.endswith(".part")]
                if matching:
                    path = os.path.join(VIDEOS_DIR, matching[0])
                    
            if not os.path.exists(path) or path.endswith(".part"):
                raise FileNotFoundError("Downloaded YouTube file not found or is incomplete (.part).")
                
            shared_state.state[state_key] = path
            console.print(f"[green]YouTube video downloaded and loaded for {pos_label}: {os.path.basename(path)}[/]")
        except Exception as e:
            logger.error(f"YouTube download failed for URL '{yt_url}': {e}", exc_info=True)
            console.print(f"[red]YouTube download failed: {str(e)}[/]")

def configure_background_music():
    console.print("[bold yellow]4. CONFIGURE BACKGROUND MUSIC[/]")
    
    # Gather existing music in MUSIC_DIR
    music_files = []
    if os.path.exists(MUSIC_DIR):
        music_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac'))]
        music_files = sorted(music_files, key=lambda x: os.path.getmtime(os.path.join(MUSIC_DIR, x)), reverse=True)
        
    choices = []
    current_music_name = os.path.basename(shared_state.state["bg_music_path"]) if shared_state.state["bg_music_path"] else "None"
    console.print(f"Current Background Music: [cyan]{current_music_name}[/]\n")
    
    for f in music_files:
        size_mb = os.path.getsize(os.path.join(MUSIC_DIR, f)) / (1024 * 1024)
        choices.append(questionary.Choice(title=f"🎵 {f} ({size_mb:.2f} MB)", value=f"file:{f}"))
        
    choices.append(questionary.Choice(title="➕ [Download music from URL]", value="download"))
    choices.append(questionary.Choice(title="📂 [Use an arbitrary local audio path]", value="local"))
    choices.append(questionary.Choice(title="❌ [Disable/Remove Background Music]", value="disable"))
    choices.append(questionary.Choice(title="<- Back to Main Menu", value="back"))
    
    selected = questionary.select("Select background music source:", choices=choices).ask()
    if not selected or selected == "back":
        return
        
    if selected.startswith("file:"):
        filename = selected[len("file:"):]
        full_path = os.path.join(MUSIC_DIR, filename)
        if not os.path.exists(full_path):
            console.print(f"[red]Error: Selected music file '{full_path}' does not exist.[/]")
            return
        shared_state.state["bg_music_path"] = full_path
        console.print(f"[green]Successfully loaded background music: {filename}[/]")
        
    elif selected == "disable":
        shared_state.state["bg_music_path"] = None
        console.print("[green]Background music disabled.[/]")
        
    elif selected == "local":
        local_path = questionary.text("Enter Local Audio File Path:").ask()
        if not local_path:
            return
        if not os.path.exists(local_path):
            console.print(f"[red]Error: Local file path '{local_path}' does not exist.[/]")
            return
        ext = os.path.splitext(local_path)[1].lower()
        if ext not in [".mp3", ".wav", ".m4a", ".ogg", ".flac"]:
            console.print("[red]Error: Invalid audio format. Must be mp3, wav, m4a, ogg, or flac.[/]")
            return
            
        original_filename = os.path.basename(local_path)
        dest_path = os.path.join(MUSIC_DIR, original_filename)
        
        if os.path.exists(dest_path):
            base, extension = os.path.splitext(original_filename)
            counter = 1
            while os.path.exists(os.path.join(MUSIC_DIR, f"{base}_{counter}{extension}")):
                counter += 1
            dest_path = os.path.join(MUSIC_DIR, f"{base}_{counter}{extension}")
            
        console.print(f"[yellow]Copying local audio to music folder: {os.path.basename(dest_path)}...[/]")
        try:
            shutil.copy2(local_path, dest_path)
            shared_state.state["bg_music_path"] = dest_path
            console.print(f"[green]Successfully loaded local audio: {os.path.basename(dest_path)}[/]")
        except Exception as e:
            logger.error(f"Failed to copy local audio from {local_path} to {dest_path}: {e}", exc_info=True)
            console.print(f"[red]Failed to copy local audio: {str(e)}[/]")
            
    elif selected == "download":
        music_url = questionary.text("Enter Audio URL (or YouTube URL):").ask()
        if not music_url:
            return
            
        console.print(f"[yellow]Downloading audio: {music_url}...[/]")
        
        if "youtube.com" in music_url.lower() or "youtu.be" in music_url.lower():
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(MUSIC_DIR, "%(title)s.%(ext)s"),
                'max_filesize': 100 * 1024 * 1024,
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(music_url, download=True)
                    title = info.get('title', 'Downloaded Audio')
                    dest_path = os.path.join(MUSIC_DIR, f"{title}.mp3")
                    matching = [f for f in os.listdir(MUSIC_DIR) if f.startswith(title[:10]) and f.endswith(".mp3")]
                    if matching:
                        dest_path = os.path.join(MUSIC_DIR, matching[0])
                    
                    shared_state.state["bg_music_path"] = dest_path
                    console.print(f"[green]Successfully downloaded YouTube audio: {os.path.basename(dest_path)}[/]")
            except Exception as e:
                logger.error(f"YouTube audio download failed for URL '{music_url}': {e}", exc_info=True)
                console.print(f"[red]Failed to download YouTube audio: {str(e)}[/]")
        else:
            try:
                import urllib.request
                import sys
                filename = music_url.split("/")[-1].split("?")[0]
                if not filename or not filename.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac')):
                    filename = "downloaded_music.mp3"
                dest_path = os.path.join(MUSIC_DIR, filename)
                
                def progress_hook(count, block_size, total_size):
                    if total_size > 0:
                        percent = min(100, int(count * block_size * 100 / total_size))
                        sys.stdout.write(f"\rDownloading... {percent}%")
                        sys.stdout.flush()
                        
                urllib.request.urlretrieve(music_url, dest_path, reporthook=progress_hook)
                print()
                shared_state.state["bg_music_path"] = dest_path
                console.print(f"[green]Downloaded audio: {filename}[/]")
            except Exception as e:
                logger.error(f"Direct audio download failed for URL '{music_url}': {e}", exc_info=True)
                console.print(f"[red]Failed to download audio: {str(e)}[/]")
                
    if shared_state.state["bg_music_path"]:
        default_music_vol = shared_state.settings.get("music_volume", 0.15)
        default_voice_vol = shared_state.settings.get("voice_volume", 1.0)
        custom_vols = questionary.confirm("Configure custom volume levels for this short?", default=False).ask()
        if custom_vols:
            voice_vol_str = questionary.text("Voiceover volume (0.0 to 2.0):", default=str(default_voice_vol)).ask()
            music_vol_str = questionary.text("Background music volume (0.0 to 1.0):", default=str(default_music_vol)).ask()
            try:
                shared_state.state["voice_volume"] = float(voice_vol_str)
            except ValueError:
                shared_state.state["voice_volume"] = default_voice_vol
            try:
                shared_state.state["music_volume"] = float(music_vol_str)
            except ValueError:
                shared_state.state["music_volume"] = default_music_vol
            console.print(f"[green]Volumes set: Voice={shared_state.state['voice_volume']}, Music={shared_state.state['music_volume']}[/]")
        else:
            shared_state.state["voice_volume"] = None
            shared_state.state["music_volume"] = None

def generate_fully_random_short():
    console.print("[bold yellow]GENERATE FULLY RANDOM SHORT[/]")
    
    # 1. Check API Key
    api_key = shared_state.settings.get("api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = shared_state.settings.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    default_model = shared_state.settings.get("model", "gpt-4o-mini")
    model = default_model
    
    opencode_key, _ = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and not base_url:
            base_url = "https://opencode.ai/zen/go/v1"
            
    if not api_key:
        console.print("[red]Error: API Key is required to generate script. Set it in Settings.[/]")
        return

    # Check background videos & music to make sure they are available or download defaults
    download_default_assets_if_empty()

    # Ask how many shorts to generate
    default_batch = str(shared_state.settings.get("default_batch_size", 5))
    num_shorts_str = questionary.text("How many random shorts do you want to generate?", default=default_batch).ask()
    if not num_shorts_str:
        return
    try:
        num_shorts = int(num_shorts_str)
        if num_shorts <= 0:
            console.print("[red]Please enter a positive integer.[/]")
            return
    except ValueError:
        console.print("[red]Invalid number entered.[/]")
        return

    if num_shorts == 1:
        # 2. Select a random topic
        templates = load_prompt_templates()
        if not templates:
            console.print("[red]Error: No prompt templates found.[/]")
            return
        template_title, prompt = random.choice(list(templates.items()))
        
        # 3. Select a random TTS voice
        voice_name, voice_id = random.choice(VOICES)
        
        # 4. Select a random preset
        presets = load_presets()
        if not presets:
            console.print("[red]Error: No presets found.[/]")
            return
        preset_name, preset = random.choice(list(presets.items()))
        
        # 5. Determine backgrounds & music
        # Randomize layout: choose split-screen or full-screen randomly
        is_split = random.choice([True, False])
        if is_split:
            top_video = "random"
            bottom_video = "random"
        else:
            top_video = "random"
            bottom_video = None
        
        # Select background music from music/ directory
        os.makedirs(MUSIC_DIR, exist_ok=True)
        music_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac'))]
        if music_files:
            chosen_music = os.path.join(MUSIC_DIR, random.choice(music_files))
        else:
            # Fall back to preset's music selection
            chosen_music = resolve_preset_path(preset.get("bg_music_path"))

        # Subtitle styling randomized
        sub_font = random.choice(["Arial", "Impact", "Georgia", "Courier New", "Times New Roman"])
        sub_size = random.randint(64, 84)
        sub_color = "#FFFFFF"
        vibrant_colors = ["#FFFF00", "#00FFFF", "#00FF00", "#FF00FF", "#FF3333", "#FF9900", "#0080FF", "#FF55BB", "#33FF33"]
        sub_highlight = random.choice(vibrant_colors)
        sub_outline = "#000000"
        sub_outline_width = random.randint(4, 7)
        sub_bold = random.choice([True, False])
        
        enable_emojis = random.choice([True, False])
        word_pop = random.choice([True, False])
        word_pop_scale = round(random.uniform(1.10, 1.25), 2) if word_pop else 1.0
        inactive_dim = random.choice([True, False])
        inactive_alpha = random.choice(["44", "66", "88", "AA"]) if inactive_dim else "FF"
        
        # Script temperature
        script_temp = round(random.uniform(0.5, 0.9), 2)

        # 6. Display a summary of the randomized choices
        console.print("\n[bold cyan]🎲 Randomized Choices Summary:[/]")
        console.print(f"  • [bold]Prompt Category:[/] {template_title}")
        console.print(f"  • [bold]Prompt/Topic:[/] [italic]{prompt}[/]")
        console.print(f"  • [bold]TTS Voice:[/] {voice_name} ({voice_id})")
        console.print(f"  • [bold]Preset Style (Base):[/] {preset_name}")
        console.print(f"  • [bold]Subtitle Font:[/] {sub_font} ({sub_size}px, Bold={sub_bold})")
        console.print(f"  • [bold]Subtitle Colors:[/] Text={sub_color} | Highlight={sub_highlight} | Outline={sub_outline} ({sub_outline_width}px)")
        console.print(f"  • [bold]Animations/Style:[/] Pop={word_pop} (x{word_pop_scale}) | Dim={inactive_dim} ({inactive_alpha}) | Emojis={enable_emojis}")
        console.print(f"  • [bold]LLM Temperature:[/] {script_temp}")
        
        if bottom_video:
            layout_str = f"Split-Screen (Top: {os.path.basename(top_video) if top_video and top_video != 'random' else top_video} | Bottom: {os.path.basename(bottom_video) if bottom_video and bottom_video != 'random' else bottom_video})"
        else:
            layout_str = f"Full Screen (Top: {os.path.basename(top_video) if top_video and top_video != 'random' else top_video})"
        console.print(f"  • [bold]Video Layout:[/] {layout_str}")
        console.print(f"  • [bold]Background Music:[/] {os.path.basename(chosen_music) if chosen_music else 'None'}")
        console.print()
        
        confirm = questionary.confirm("Do you want to proceed with generating and compiling this randomized short?").ask()
        if not confirm:
            console.print("[yellow]Cancelled random generation.[/]")
            return
            
        # 7. Apply to global state (overwrites active session state)
        shared_state.state["selected_voice"] = voice_id
        shared_state.state["bg_video_path"] = top_video
        shared_state.state["bg_video_bottom_path"] = bottom_video
        shared_state.state["bg_music_path"] = chosen_music
        shared_state.state["music_volume"] = preset.get("music_volume")
        shared_state.state["voice_volume"] = preset.get("voice_volume")
        shared_state.state["loaded_preset_name"] = f"{preset_name} (Randomized)"
        
        # Subtitle styling loaded
        shared_state.state["sub_font"] = sub_font
        shared_state.state["sub_size"] = sub_size
        shared_state.state["sub_color"] = sub_color
        shared_state.state["sub_highlight"] = sub_highlight
        shared_state.state["sub_outline"] = sub_outline
        shared_state.state["sub_outline_width"] = sub_outline_width
        shared_state.state["sub_bold"] = sub_bold
        shared_state.state["enable_emojis"] = enable_emojis
        shared_state.state["word_pop"] = word_pop
        shared_state.state["word_pop_scale"] = word_pop_scale
        shared_state.state["inactive_dim"] = inactive_dim
        shared_state.state["inactive_alpha"] = inactive_alpha

        # 8. Generate the script using the OpenAI API
        if base_url and "opencode.ai" in base_url:
            model = "deepseek-v4-flash"
        else:
            model = "gpt-4o-mini"
            
        console.print(f"\n[yellow]Generating script using model '{model}'...[/]")
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        max_words = shared_state.settings.get("max_words", 130)
        system_prompt = (
            "You are an expert TikTok and YouTube Shorts content creator. "
            "Write a highly engaging, viral vertical video script about the topic provided by the user. "
            "Guidelines:\n"
            "- Hook: Write a powerful hook in the first 3 seconds to grab attention.\n"
            "- Format: The script should be conversational, punchy, and fast-paced.\n"
            f"- Length: Strictly under {max_words} words (approx. {int(max_words/2.3)} seconds when spoken).\n"
            "- Content: Include 3 key points or a compelling narrative.\n"
            "- Formatting: Output ONLY the spoken words. Do NOT include sound effect cues, stage directions, or brackets like [Music] or [Host]."
        )
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=script_temp
            )
            script_text = response.choices[0].message.content.strip()
            shared_state.state["script_text"] = script_text
            console.print("\n[green]Script successfully generated![/]")
            console.print("[bold white]Preview of script:[/]")
            console.print(f"[italic]{script_text}[/]\n")
        except Exception as e:
            logger.error(f"Random short script generation failed: {e}", exc_info=True)
            console.print(f"[red]Script generation failed: {str(e)}[/]")
            console.print("[yellow]Detailed error logs are available in logs/app.log[/]")
            return

        # 9. Trigger Compilation (skip secondary confirmation!)
        compile_video_flow(skip_confirm=True)
    else:
        # Batch generation flow
        confirm = questionary.confirm(f"Are you sure you want to generate and compile {num_shorts} randomized shorts in bulk?").ask()
        if not confirm:
            console.print("[yellow]Cancelled bulk random generation.[/]")
            return
            
        # Save active session state to restore later
        old_state = shared_state.state.copy()
        
        templates = load_prompt_templates()
        if not templates:
            console.print("[red]Error: No prompt templates found.[/]")
            return
            
        presets = load_presets()
        if not presets:
            console.print("[red]Error: No presets found.[/]")
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        success_count = 0
        failed_videos = []
        successful_videos = []
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        max_words = shared_state.settings.get("max_words", 130)
        system_prompt = (
            "You are an expert TikTok and YouTube Shorts content creator. "
            "Write a highly engaging, viral vertical video script about the topic provided by the user. "
            "Guidelines:\n"
            "- Hook: Write a powerful hook in the first 3 seconds to grab attention.\n"
            "- Format: The script should be conversational, punchy, and fast-paced.\n"
            f"- Length: Strictly under {max_words} words (approx. {int(max_words/2.3)} seconds when spoken).\n"
            "- Content: Include 3 key points or a compelling narrative.\n"
            "- Formatting: Output ONLY the spoken words. Do NOT include sound effect cues, stage directions, or brackets like [Music] or [Host]."
        )
        
        if base_url and "opencode.ai" in base_url:
            model = "deepseek-v4-flash"
        else:
            model = "gpt-4o-mini"
            
        # Prepare all job configurations
        job_configs = {}
        job_details = {}
        
        for i in range(1, num_shorts + 1):
            # 1. Random choices
            template_title, prompt = random.choice(list(templates.items()))
            voice_name, voice_id = random.choice(VOICES)
            preset_name, preset = random.choice(list(presets.items()))
            
            # Randomize layout: choose split-screen or full-screen randomly
            is_split = random.choice([True, False])
            if is_split:
                top_video = "random"
                bottom_video = "random"
            else:
                top_video = "random"
                bottom_video = None
                
            # Select background music from music/ directory
            os.makedirs(MUSIC_DIR, exist_ok=True)
            music_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac'))]
            if music_files:
                chosen_music = os.path.join(MUSIC_DIR, random.choice(music_files))
            else:
                chosen_music = resolve_preset_path(preset.get("bg_music_path"))
                
            # Randomize subtitle properties
            sub_font = random.choice(["Arial", "Impact", "Georgia", "Courier New", "Times New Roman"])
            sub_size = random.randint(64, 84)
            sub_color = "#FFFFFF"
            vibrant_colors = ["#FFFF00", "#00FFFF", "#00FF00", "#FF00FF", "#FF3333", "#FF9900", "#0080FF", "#FF55BB", "#33FF33"]
            sub_highlight = random.choice(vibrant_colors)
            sub_outline = "#000000"
            sub_outline_width = random.randint(4, 7)
            sub_bold = random.choice([True, False])
            
            enable_emojis = random.choice([True, False])
            word_pop = random.choice([True, False])
            word_pop_scale = round(random.uniform(1.10, 1.25), 2) if word_pop else 1.0
            inactive_dim = random.choice([True, False])
            inactive_alpha = random.choice(["44", "66", "88", "AA"]) if inactive_dim else "FF"
            
            # Script temperature
            script_temp = round(random.uniform(0.5, 0.9), 2)
            
            output_filename = f"rendered_batch_{timestamp}_{i}.mp4"
            
            job_configs[i] = {
                "index": i,
                "prompt": prompt,
                "voice_id": voice_id,
                "bg_video_path": top_video,
                "bg_video_bottom_path": bottom_video,
                "bg_music_path": chosen_music,
                "music_volume": preset.get("music_volume"),
                "voice_volume": preset.get("voice_volume"),
                "sub_font": sub_font,
                "sub_size": sub_size,
                "sub_color": sub_color,
                "sub_highlight": sub_highlight,
                "sub_outline": sub_outline,
                "sub_outline_width": sub_outline_width,
                "sub_bold": sub_bold,
                "enable_emojis": enable_emojis,
                "word_pop": word_pop,
                "word_pop_scale": word_pop_scale,
                "inactive_dim": inactive_dim,
                "inactive_alpha": inactive_alpha,
                "script_temp": script_temp,
                "output_filename": output_filename,
                "model": model,
                "system_prompt": system_prompt,
                "settings": shared_state.settings.copy()
            }
            
            job_details[i] = {
                "topic": f"[{template_title}] {prompt[:35]}...",
                "voice": voice_name,
                "layout": "Split-Screen" if is_split else "Full Screen"
            }
            
        max_workers = shared_state.settings.get("max_workers")
        if not max_workers:
            max_workers = os.cpu_count() or 1
        else:
            try:
                max_workers = int(max_workers)
            except ValueError:
                max_workers = os.cpu_count() or 1
        console.print(f"\n[bold yellow]Spawning {num_shorts} batch generation jobs in parallel (max_workers={max_workers})...[/]")
        
        try:
            with multiprocessing.Manager() as manager:
                progress_dict = manager.dict()
                llm_lock = manager.Lock()
                for i in range(1, num_shorts + 1):
                    progress_dict[i] = "Queued"
                    
                executor = ProcessPoolExecutor(max_workers=max_workers)
                futures = []
                try:
                    for i in range(1, num_shorts + 1):
                        futures.append(executor.submit(batch_job_worker, job_configs[i], progress_dict, llm_lock))
                        
                    with Live(display_progress_table(progress_dict, num_shorts, job_details), console=console, refresh_per_second=4) as live:
                        while not all(f.done() for f in futures):
                            time.sleep(0.25)
                            live.update(display_progress_table(progress_dict, num_shorts, job_details))
                        live.update(display_progress_table(progress_dict, num_shorts, job_details))
                        
                    # Collect results
                    for f in futures:
                        try:
                            idx, success, output_info = f.result()
                            if success:
                                success_count += 1
                                successful_videos.append(output_info)
                            else:
                                failed_videos.append(f"Short {idx} ({output_info})")
                        except Exception as e:
                            failed_videos.append(f"Execution error: {str(e)}")
                    
                    executor.shutdown(wait=True)
                except KeyboardInterrupt:
                    console.print("\n[bold red]Stopping batch generation... Terminating worker processes...[/]")
                    for f in futures:
                        f.cancel()
                    if hasattr(executor, "_processes"):
                        for p in list(executor._processes.values()):
                            try:
                                p.terminate()
                            except Exception:
                                pass
                    try:
                        executor.shutdown(wait=False, cancel_futures=True)
                    except Exception:
                        pass
                    
                    if os.name == "nt":
                        import subprocess
                        try:
                            subprocess.run(["taskkill", "/F", "/IM", "ffmpeg.exe"], capture_output=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        except Exception:
                            pass
                            
                    console.print("[red]Batch generation aborted by user.[/]")
                    return
                except Exception as e:
                    try:
                        executor.shutdown(wait=False)
                    except Exception:
                        pass
                    raise e
        except KeyboardInterrupt:
            console.print("[red]Batch generation process interrupted.[/]")
            return
        finally:
            # Restore state
            shared_state.state.clear()
            shared_state.state.update(old_state)
                
        # Batch Summary
        console.print(f"\n[bold green]========================================[/]")
        console.print(f"[bold green]🎉 BATCH RUN COMPLETED![/]")
        console.print(f"[bold green]========================================[/]")
        console.print(f"Successfully created: {success_count}/{num_shorts} videos.")
        if successful_videos:
            console.print("\n[bold white]Successful Videos (Saved in output/):[/]")
            for f in successful_videos:
                console.print(f"  • {f}")
        if failed_videos:
            console.print("\n[bold red]Failed Videos:[/]")
            for f in failed_videos:
                console.print(f"  • {f}")
        console.print(f"[bold green]========================================[/]\n")

def configure_settings():
    console.print("[bold yellow]6. SETTINGS MANAGEMENT[/]")
    
    current_key = shared_state.settings.get("api_key", "")
    current_base = shared_state.settings.get("base_url", "")
    current_model = shared_state.settings.get("model", "gpt-4o-mini")
    current_max_words = shared_state.settings.get("max_words", 130)
    current_w_key = shared_state.settings.get("whisper_api_key", "")
    current_w_base = shared_state.settings.get("whisper_base_url", "")
    current_local_whisper = shared_state.settings.get("local_whisper", True)
    current_local_model = shared_state.settings.get("local_whisper_model", "tiny")
    current_pexels_key = shared_state.settings.get("pexels_api_key", "")
    
    # Subtitle defaults
    current_voice_vol = shared_state.settings.get("voice_volume", 1.0)
    current_music_vol = shared_state.settings.get("music_volume", 0.15)
    current_sub_font = shared_state.settings.get("sub_font", "Arial")
    current_sub_size = shared_state.settings.get("sub_size", 72)
    current_sub_color = shared_state.settings.get("sub_color", "#FFFFFF")
    current_sub_highlight = shared_state.settings.get("sub_highlight", "#00FFFF")
    current_sub_outline = shared_state.settings.get("sub_outline", "#000000")
    current_sub_outline_width = shared_state.settings.get("sub_outline_width", 5)
    current_sub_bold = shared_state.settings.get("sub_bold", True)
    
    # Subtitle Animation & Emojis defaults
    current_word_pop = shared_state.settings.get("word_pop", True)
    current_word_pop_scale = shared_state.settings.get("word_pop_scale", 1.15)
    current_inactive_dim = shared_state.settings.get("inactive_dim", True)
    current_inactive_alpha = shared_state.settings.get("inactive_alpha", "88")
    current_enable_emojis = shared_state.settings.get("enable_emojis", True)

    settings_cat = questionary.select(
        "Select settings category to configure:",
        choices=[
            questionary.Choice("1. API Keys & AI Models", "api"),
            questionary.Choice("2. Subtitle Styling", "subtitles"),
            questionary.Choice("3. Default Audio Volumes", "volumes"),
            questionary.Choice("4. Subtitle Animations & Emojis", "animations"),
            questionary.Choice("5. Manage Emoji Dictionary", "emojis"),
            questionary.Choice("6. Video Rendering & Performance Settings", "rendering"),
            questionary.Choice("<- Back to Main Menu", "back")
        ]
    ).ask()
    
    if not settings_cat or settings_cat == "back":
        return
        
    if settings_cat == "api":
        api_key = questionary.password("OpenAI API Key (or OpenCode key):", default=current_key).ask()
        base_url = questionary.text("OpenAI Base URL (optional):", default=current_base).ask()
        model = questionary.text("Script Generation Model Name:", default=current_model).ask()
        max_words = questionary.text("Script word count limit (default 130):", default=str(current_max_words)).ask()
        whisper_key = questionary.password("Whisper API Key (optional fallback):", default=current_w_key).ask()
        whisper_base_url = questionary.text("Whisper Base URL (optional fallback):", default=current_w_base).ask()
        pexels_key = questionary.password("Pexels API Key (for auto backgrounds):", default=current_pexels_key).ask()
        
        use_local = questionary.confirm("Use local Whisper for transcription?", default=current_local_whisper).ask()
        
        local_model = current_local_model
        if use_local:
            local_model = questionary.select(
                "Select local Whisper model:",
                choices=["tiny", "base", "small", "medium"],
                default=current_local_model
            ).ask()
        
        if api_key is not None: shared_state.settings["api_key"] = api_key.strip()
        if base_url is not None: shared_state.settings["base_url"] = base_url.strip()
        if model is not None: shared_state.settings["model"] = model.strip() or "gpt-4o-mini"
        if max_words is not None:
            try: shared_state.settings["max_words"] = int(max_words.strip())
            except ValueError: pass
        if whisper_key is not None: shared_state.settings["whisper_api_key"] = whisper_key.strip()
        if whisper_base_url is not None: shared_state.settings["whisper_base_url"] = whisper_base_url.strip()
        if pexels_key is not None: shared_state.settings["pexels_api_key"] = pexels_key.strip()
        if use_local is not None: shared_state.settings["local_whisper"] = use_local
        if local_model is not None: shared_state.settings["local_whisper_model"] = local_model

    elif settings_cat == "subtitles":
        font_name = questionary.text("Font Family Name (e.g. Arial, Impact, Montserrat):", default=current_sub_font).ask()
        font_size = questionary.text("Font Size (e.g. 64, 72, 80):", default=str(current_sub_size)).ask()
        primary_color = questionary.text("Primary Text Color (HEX e.g. #FFFFFF):", default=current_sub_color).ask()
        highlight_color = questionary.text("Active Word Highlight Color (HEX e.g. #00FFFF):", default=current_sub_highlight).ask()
        outline_color = questionary.text("Outline Color (HEX e.g. #000000):", default=current_sub_outline).ask()
        outline_width = questionary.text("Outline Width (e.g. 3, 5, 8):", default=str(current_sub_outline_width)).ask()
        bold = questionary.confirm("Use Bold text?", default=current_sub_bold).ask()
        
        if font_name is not None: shared_state.settings["sub_font"] = font_name.strip()
        if font_size is not None:
            try: shared_state.settings["sub_size"] = int(font_size)
            except ValueError: pass
        if primary_color is not None: shared_state.settings["sub_color"] = primary_color.strip()
        if highlight_color is not None: shared_state.settings["sub_highlight"] = highlight_color.strip()
        if outline_color is not None: shared_state.settings["sub_outline"] = outline_color.strip()
        if outline_width is not None:
            try: shared_state.settings["sub_outline_width"] = int(outline_width)
            except ValueError: pass
        if bold is not None: shared_state.settings["sub_bold"] = bold

    elif settings_cat == "volumes":
        voice_vol = questionary.text("Default Voiceover Volume (0.0 to 2.0):", default=str(current_voice_vol)).ask()
        music_vol = questionary.text("Default Background Music Volume (0.0 to 1.0):", default=str(current_music_vol)).ask()
        
        if voice_vol is not None:
            try: shared_state.settings["voice_volume"] = float(voice_vol)
            except ValueError: pass
        if music_vol is not None:
            try: shared_state.settings["music_volume"] = float(music_vol)
            except ValueError: pass

    elif settings_cat == "animations":
        word_pop = questionary.confirm("Enable Active Word Pop (scaling effect)?", default=current_word_pop).ask()
        word_pop_scale = current_word_pop_scale
        if word_pop:
            scale_str = questionary.text("Active Word Scaling Factor (e.g. 1.15, 1.20):", default=str(current_word_pop_scale)).ask()
            if scale_str:
                try: word_pop_scale = float(scale_str)
                except ValueError: pass
                
        inactive_dim = questionary.confirm("Enable Inactive Word Dimming?", default=current_inactive_dim).ask()
        inactive_alpha = current_inactive_alpha
        if inactive_dim:
            inactive_alpha = questionary.select(
                "Select Inactive Words Dimming Level:",
                choices=[
                    questionary.Choice("Light Dimming (approx. 73% Opacity) [alpha: 44]", "44"),
                    questionary.Choice("Medium Dimming (approx. 47% Opacity) [alpha: 88]", "88"),
                    questionary.Choice("Heavy Dimming (approx. 27% Opacity) [alpha: BB]", "BB")
                ],
                default=current_inactive_alpha
            ).ask()
            
        enable_emojis = questionary.confirm("Enable Contextual Dynamic Emoji Injection?", default=current_enable_emojis).ask()
        
        if word_pop is not None: shared_state.settings["word_pop"] = word_pop
        if word_pop_scale is not None: shared_state.settings["word_pop_scale"] = word_pop_scale
        if inactive_dim is not None: shared_state.settings["inactive_dim"] = inactive_dim
        if inactive_alpha is not None: shared_state.settings["inactive_alpha"] = inactive_alpha
        if enable_emojis is not None: shared_state.settings["enable_emojis"] = enable_emojis

    elif settings_cat == "emojis":
        while True:
            emoji_map = load_emoji_map()
            console.clear()
            console.print("[bold yellow]Emoji Mapping Dictionary[/]")
            console.print(f"Total mappings: [cyan]{len(emoji_map)}[/]\n")
            
            sample_keys = list(emoji_map.keys())[:10]
            console.print("Sample mappings:")
            for k in sample_keys:
                console.print(f"  • {k} -> {emoji_map[k]}")
            if len(emoji_map) > 10:
                console.print(f"  ... and {len(emoji_map) - 10} more.")
            console.print()
            
            action = questionary.select(
                "Select emoji dictionary action:",
                choices=[
                    questionary.Choice("➕ Add New Mapping", "add"),
                    questionary.Choice("✏️ Edit/Remove Existing Mapping", "edit"),
                    questionary.Choice("🔄 Reset to Default Map", "reset"),
                    questionary.Choice("<- Back to Settings Menu", "back")
                ]
            ).ask()
            
            if not action or action == "back":
                break
                
            if action == "add":
                word_to_add = questionary.text("Enter lowercase word/stem (e.g. 'ghost'):").ask()
                if not word_to_add:
                    continue
                word_to_add = word_to_add.strip().lower()
                emoji_to_add = questionary.text("Enter emoji (e.g. '👻'):").ask()
                if not emoji_to_add:
                    continue
                emoji_map[word_to_add] = emoji_to_add.strip()
                if save_emoji_map(emoji_map):
                    console.print(f"[green]Added {word_to_add} -> {emoji_to_add}[/]")
                else:
                    console.print("[red]Error: Failed to save emoji map.[/]")
                questionary.press_any_key_to_continue().ask()
                
            elif action == "edit":
                if not emoji_map:
                    console.print("[yellow]Emoji dictionary is empty.[/]")
                    questionary.press_any_key_to_continue().ask()
                    continue
                sorted_keys = sorted(emoji_map.keys())
                choices = [questionary.Choice(f"{k} -> {emoji_map[k]}", k) for k in sorted_keys]
                choices.append(questionary.Choice("<- Back", "back"))
                
                selected_key = questionary.select("Select mapping to edit/delete:", choices=choices).ask()
                if not selected_key or selected_key == "back":
                    continue
                    
                edit_action = questionary.select(
                    f"Select action for '{selected_key}' mapping:",
                    choices=[
                        questionary.Choice("Edit Emoji", "edit_val"),
                        questionary.Choice("❌ Delete Mapping", "delete_val"),
                        questionary.Choice("<- Cancel", "cancel")
                    ]
                ).ask()
                
                if edit_action == "edit_val":
                    new_val = questionary.text(f"Enter new emoji for '{selected_key}' (current: {emoji_map[selected_key]}):").ask()
                    if new_val:
                        emoji_map[selected_key] = new_val.strip()
                        save_emoji_map(emoji_map)
                        console.print("[green]Mapping updated successfully![/]")
                elif edit_action == "delete_val":
                    del emoji_map[selected_key]
                    save_emoji_map(emoji_map)
                    console.print("[green]Mapping deleted successfully![/]")
                questionary.press_any_key_to_continue().ask()
                
            elif action == "reset":
                confirm = questionary.confirm("Are you sure you want to reset all mappings to defaults? Custom additions will be lost!").ask()
                if confirm:
                    from cli.config import DEFAULT_EMOJI_MAP as raw_default_map
                    if save_emoji_map(raw_default_map):
                        console.print("[green]Emoji dictionary successfully reset to defaults.[/]")
                    else:
                        console.print("[red]Failed to reset emoji dictionary.[/]")
                questionary.press_any_key_to_continue().ask()
            
    elif settings_cat == "rendering":
        current_preset = shared_state.settings.get("render_preset", "veryfast")
        current_res = shared_state.settings.get("render_resolution", "1080p")
        current_encoder = shared_state.settings.get("video_encoder", "libx264")
        current_max_workers = shared_state.settings.get("max_workers", os.cpu_count() or 1)
        current_default_batch = shared_state.settings.get("default_batch_size", 5)
        
        video_encoder = questionary.select(
            "Select FFmpeg Video Encoder (CPU or AMD/NVIDIA/Intel GPU acceleration):",
            choices=[
                questionary.Choice("libx264 (CPU - Default standard compatibility)", "libx264"),
                questionary.Choice("h264_amf (AMD GPU Acceleration - H.264 - Recommended for your RX 6700 XT)", "h264_amf"),
                questionary.Choice("hevc_amf (AMD GPU Acceleration - HEVC)", "hevc_amf"),
                questionary.Choice("h264_nvenc (NVIDIA GPU Acceleration)", "h264_nvenc"),
                questionary.Choice("h264_qsv (Intel GPU Acceleration)", "h264_qsv")
            ],
            default=current_encoder
        ).ask()

        render_preset = questionary.select(
            "Select FFmpeg rendering speed preset (faster presets compile quicker but have slightly larger size/lower quality):",
            choices=[
                questionary.Choice("ultrafast (Fastest render, largest file size)", "ultrafast"),
                questionary.Choice("superfast (Very fast render)", "superfast"),
                questionary.Choice("veryfast (Default fast render)", "veryfast"),
                questionary.Choice("faster (Medium-fast render)", "faster"),
                questionary.Choice("fast (Balanced render)", "fast"),
                questionary.Choice("medium (Standard render, best quality/size)", "medium")
            ],
            default=current_preset
        ).ask()
        
        render_resolution = questionary.select(
            "Select video output resolution (720p is ~2.25x faster to render than 1080p):",
            choices=[
                questionary.Choice("1080p (1080x1920 - Full HD)", "1080p"),
                questionary.Choice("720p (720x1280 - HD)", "720p")
            ],
            default=current_res
        ).ask()

        max_workers = questionary.text(
            f"Maximum parallel batch jobs (default is CPU count: {os.cpu_count()}):",
            default=str(current_max_workers)
        ).ask()

        default_batch_size_str = questionary.text(
            "Default number of shorts to generate in a batch:",
            default=str(current_default_batch)
        ).ask()
        
        if video_encoder is not None:
            shared_state.settings["video_encoder"] = video_encoder
        if render_preset is not None:
            shared_state.settings["render_preset"] = render_preset
        if render_resolution is not None:
            shared_state.settings["render_resolution"] = render_resolution
        if max_workers is not None:
            try:
                shared_state.settings["max_workers"] = int(max_workers)
            except ValueError:
                pass
        if default_batch_size_str is not None:
            try:
                shared_state.settings["default_batch_size"] = int(default_batch_size_str)
            except ValueError:
                pass

    if save_settings(shared_state.settings):
        console.print("[green]Settings saved successfully![/]")
    else:
        console.print("[red]Failed to save settings to disk.[/]")

def view_history():
    console.print("[bold yellow]7. VIEW HISTORY & MANAGE VIDEOS[/]")
    while True:
        if not os.path.exists(OUTPUT_DIR):
            console.print("[yellow]Output directory does not exist.[/]")
            break
            
        files = sorted(
            [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".mp4")],
            key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)),
            reverse=True
        )
        
        if not files:
            console.print("[yellow]No compiled videos found in output/ directory.[/]")
            break
            
        choices = []
        for f in files:
            full_path = os.path.join(OUTPUT_DIR, f)
            size_mb = os.path.getsize(full_path) // (1024 * 1024)
            choices.append(questionary.Choice(title=f"📹 {f} ({size_mb} MB)", value=f))
            
        choices.append(questionary.Choice(title="<- Back to Main Menu", value="back"))
        
        selected_file = questionary.select("Select a video to manage:", choices=choices).ask()
        if not selected_file or selected_file == "back":
            break
            
        # Manage single file
        full_path = os.path.join(OUTPUT_DIR, selected_file)
        console.print(f"\n[bold white]File Info:[/]")
        console.print(f"Name: {selected_file}")
        console.print(f"Path: {full_path}")
        console.print(f"Size: {os.path.getsize(full_path) // (1024 * 1024)} MB")
        
        action = questionary.select(
            "Select action:",
            choices=[
                questionary.Choice(title="❌ Delete File", value="delete"),
                questionary.Choice(title="<- Back to History", value="back")
            ]
        ).ask()
        
        if action == "delete":
            confirm = questionary.confirm(f"Are you sure you want to delete {selected_file}?").ask()
            if confirm:
                try:
                    os.remove(full_path)
                    console.print(f"[green]Successfully deleted {selected_file}.[/]")
                except Exception as e:
                    console.print(f"[red]Failed to delete file: {str(e)}[/]")

def manage_presets_menu():
    console.print("[bold yellow]8. PRESET TEMPLATES MANAGEMENT[/]")
    presets = load_presets()
    
    choices = [
        questionary.Choice("1. Load Preset Template", "load"),
        questionary.Choice("2. Save Current Config as Preset", "save"),
        questionary.Choice("3. Delete Custom Preset", "delete"),
        questionary.Choice("<- Back to Main Menu", "back")
    ]
    
    action = questionary.select("Select preset action:", choices=choices).ask()
    if not action or action == "back":
        return
        
    if action == "load":
        if not presets:
            console.print("[yellow]No presets found.[/]")
            return
        preset_choices = [questionary.Choice(title=name, value=name) for name in presets.keys()]
        preset_choices.append(questionary.Choice("<- Back", "back"))
        
        to_load = questionary.select("Select Preset to Load:", choices=preset_choices).ask()
        if not to_load or to_load == "back":
            return
            
        p = presets[to_load]
        shared_state.state["selected_voice"] = p.get("selected_voice", shared_state.state["selected_voice"])
        shared_state.state["bg_video_path"] = resolve_preset_path(p.get("bg_video_path"))
        shared_state.state["bg_video_bottom_path"] = resolve_preset_path(p.get("bg_video_bottom_path"))
        shared_state.state["bg_music_path"] = resolve_preset_path(p.get("bg_music_path"))
        shared_state.state["music_volume"] = p.get("music_volume")
        shared_state.state["voice_volume"] = p.get("voice_volume")
        shared_state.state["loaded_preset_name"] = to_load
        
        # Subtitle styling attributes
        shared_state.state["sub_font"] = p.get("sub_font")
        shared_state.state["sub_size"] = p.get("sub_size")
        shared_state.state["sub_color"] = p.get("sub_color")
        shared_state.state["sub_highlight"] = p.get("sub_highlight")
        shared_state.state["sub_outline"] = p.get("sub_outline")
        shared_state.state["sub_outline_width"] = p.get("sub_outline_width")
        shared_state.state["sub_bold"] = p.get("sub_bold")
        
        # Dimming / POP / Emoji properties
        shared_state.state["word_pop"] = p.get("word_pop")
        shared_state.state["word_pop_scale"] = p.get("word_pop_scale")
        shared_state.state["inactive_dim"] = p.get("inactive_dim")
        shared_state.state["inactive_alpha"] = p.get("inactive_alpha")
        shared_state.state["enable_emojis"] = p.get("enable_emojis")
        
        console.print(f"[green]Successfully loaded preset '{to_load}' and applied styles to current session state.[/]")
        
    elif action == "save":
        preset_name = questionary.text("Enter unique name for this new preset template:").ask()
        if not preset_name:
            return
            
        # Assemble dictionary
        new_preset = {
            "name": preset_name,
            "selected_voice": shared_state.state["selected_voice"],
            "bg_video_path": make_preset_path_relative(shared_state.state["bg_video_path"]),
            "bg_video_bottom_path": make_preset_path_relative(shared_state.state["bg_video_bottom_path"]),
            "bg_music_path": make_preset_path_relative(shared_state.state["bg_music_path"]),
            "music_volume": shared_state.state["music_volume"] if shared_state.state["music_volume"] is not None else shared_state.settings.get("music_volume", 0.15),
            "voice_volume": shared_state.state["voice_volume"] if shared_state.state["voice_volume"] is not None else shared_state.settings.get("voice_volume", 1.0),
            
            # Styles
            "sub_font": shared_state.state["sub_font"] if shared_state.state["sub_font"] is not None else shared_state.settings.get("sub_font", "Arial"),
            "sub_size": shared_state.state["sub_size"] if shared_state.state["sub_size"] is not None else shared_state.settings.get("sub_size", 72),
            "sub_color": shared_state.state["sub_color"] if shared_state.state["sub_color"] is not None else shared_state.settings.get("sub_color", "#FFFFFF"),
            "sub_highlight": shared_state.state["sub_highlight"] if shared_state.state["sub_highlight"] is not None else shared_state.settings.get("sub_highlight", "#00FFFF"),
            "sub_outline": shared_state.state["sub_outline"] if shared_state.state["sub_outline"] is not None else shared_state.settings.get("sub_outline", "#000000"),
            "sub_outline_width": shared_state.state["sub_outline_width"] if shared_state.state["sub_outline_width"] is not None else shared_state.settings.get("sub_outline_width", 5),
            "sub_bold": shared_state.state["sub_bold"] if shared_state.state["sub_bold"] is not None else shared_state.settings.get("sub_bold", True),
            
            # Dynamics
            "word_pop": shared_state.state["word_pop"] if shared_state.state["word_pop"] is not None else shared_state.settings.get("word_pop", True),
            "word_pop_scale": shared_state.state["word_pop_scale"] if shared_state.state["word_pop_scale"] is not None else shared_state.settings.get("word_pop_scale", 1.15),
            "inactive_dim": shared_state.state["inactive_dim"] if shared_state.state["inactive_dim"] is not None else shared_state.settings.get("inactive_dim", True),
            "inactive_alpha": shared_state.state["inactive_alpha"] if shared_state.state["inactive_alpha"] is not None else shared_state.settings.get("inactive_alpha", "88"),
            "enable_emojis": shared_state.state["enable_emojis"] if shared_state.state["enable_emojis"] is not None else shared_state.settings.get("enable_emojis", True)
        }
        
        if save_custom_preset(preset_name, new_preset):
            shared_state.state["loaded_preset_name"] = preset_name
            console.print(f"[green]Preset '{preset_name}' saved successfully![/]")
        else:
            console.print("[red]Failed to save custom preset.[/]")
            
    elif action == "delete":
        custom_presets = {}
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, "r") as f:
                    custom_presets = json.load(f)
            except Exception:
                pass
        
        if not custom_presets:
            console.print("[yellow]No custom presets found to delete. Built-in presets cannot be deleted.[/]")
            return
            
        choices = [questionary.Choice(title=name, value=name) for name in custom_presets.keys()]
        choices.append(questionary.Choice("<- Back", "back"))
        
        to_delete = questionary.select("Select Custom Preset to Delete:", choices=choices).ask()
        if not to_delete or to_delete == "back":
            return
            
        confirm = questionary.confirm(f"Are you sure you want to delete custom preset '{to_delete}'?").ask()
        if confirm:
            if delete_custom_preset(to_delete):
                if shared_state.state.get("loaded_preset_name") == to_delete:
                    shared_state.state["loaded_preset_name"] = None
                console.print(f"[green]Deleted custom preset '{to_delete}' successfully.[/]")
            else:
                console.print("[red]Failed to delete custom preset.[/]")
