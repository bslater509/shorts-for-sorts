import sys
import os
import re
import atexit
import traceback
import time
from rich.table import Table

from cli import state as shared_state
from cli.config import console, clear_cache
from cli.compiler import compile_video_flow

class ProgressConsole:
    def __init__(self, idx, p_dict):
        self.idx = idx
        self.p_dict = p_dict
        
    def print(self, *args, **kwargs):
        msg = " ".join(str(a) for a in args)
        if "Generating & transcribing sentence" in msg:
            match = re.search(r"sentence (\d+/\d+)", msg)
            if match:
                self.p_dict[self.idx] = f"Voice & Whisper ({match.group(1)})"
            else:
                self.p_dict[self.idx] = "Voice & Whisper"
        elif "[1/4]" in msg or "Generating & transcribing" in msg:
            self.p_dict[self.idx] = "Voice & Whisper"
        elif "[2/4]" in msg:
            self.p_dict[self.idx] = "Transcription"
        elif "[3/4]" in msg:
            self.p_dict[self.idx] = "Subtitles"
        elif "FFmpeg Rendering" in msg:
            match = re.search(r"(\d+\.?\d*)%", msg)
            if match:
                self.p_dict[self.idx] = f"FFmpeg Rendering ({match.group(1)}%)"
            else:
                self.p_dict[self.idx] = "FFmpeg Rendering"
        elif "[4/4]" in msg:
            self.p_dict[self.idx] = "FFmpeg Rendering"
        elif "ℹ️ Found cached" in msg:
            self.p_dict[self.idx] = "Reusing Cache (Voice/Whisper)"
            
    def clear(self):
        pass

def get_progress_percentage(status):
    if status == "Queued":
        return 0
    elif status == "Waiting for LLM":
        return 5
    elif status == "LLM Script":
        return 10
    elif status.startswith("Voice & Whisper"):
        match = re.search(r"\((\d+)/(\d+)\)", status)
        if match:
            s_idx = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                return 10 + int((s_idx / total) * 40)
        return 30
    elif status == "Reusing Cache (Voice/Whisper)":
        return 50
    elif status == "Compiling":
        return 50
    elif status == "Transcription":
        return 52
    elif status == "Subtitles":
        return 55
    elif status.startswith("FFmpeg Rendering"):
        match = re.search(r"\((\d+\.?\d*)%\)", status)
        if match:
            pct = float(match.group(1))
            return 55 + int((pct / 100) * 45)
        return 75
    elif status == "Done":
        return 100
    elif status.startswith("Failed"):
        return None
    return 0

def make_progress_bar(percentage, status, width=15):
    filled = int(width * percentage / 100)
    filled = max(0, min(width, filled))
    empty = width - filled
    
    if status == "Done":
        bar_color = "green"
        pct_color = "green"
        desc = "[bold green]✓ Done[/]"
    elif status == "Queued":
        bar_color = "grey37"
        pct_color = "grey37"
        desc = "[dim]Queued...[/]"
    else:
        bar_color = "cyan"
        pct_color = "yellow"
        desc = f"[bold yellow]🔄 {status}...[/]"
        
    bar = f"[{bar_color}]" + "█" * filled + f"[/{bar_color}][grey37]" + "░" * empty + f"[/grey37]"
    return f"{bar} [{pct_color}]{percentage:3d}%[/{pct_color}] {desc}"

def format_elapsed(duration):
    m = int(duration) // 60
    s = int(duration) % 60
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"

def display_progress_table(progress_dict, total_shorts, job_details):
    table = Table(
        title="[bold magenta]Concurrent Batch Generation Progress[/bold magenta]",
        show_header=True,
        header_style="bold cyan",
        expand=True
    )
    table.add_column("Short #", justify="center", style="dim", width=8)
    table.add_column("Category & Topic", justify="left")
    table.add_column("Voice & Layout", justify="left")
    table.add_column("Status / Progress", justify="left")
    table.add_column("Elapsed", justify="center", style="dim", width=12)
    
    for idx in range(1, total_shorts + 1):
        details = job_details.get(idx, {})
        topic = details.get("topic", "Unknown")
        voice_layout = f"{details.get('voice', 'Unknown')} | {details.get('layout', 'Unknown')}"
        status = progress_dict.get(idx, "Queued")
        
        # Calculate elapsed time
        start_time = progress_dict.get(f"{idx}_start")
        end_time = progress_dict.get(f"{idx}_end")
        
        elapsed_str = "--"
        if start_time:
            if end_time:
                duration = end_time - start_time
                elapsed_str = f"{format_elapsed(duration)} (Done)" if status == "Done" else format_elapsed(duration)
            else:
                duration = time.time() - start_time
                elapsed_str = format_elapsed(duration)
        
        # Calculate percentage
        pct = get_progress_percentage(status)
        
        if pct is None:
            status_str = f"[bold red]✗ {status}[/]"
        else:
            status_str = make_progress_bar(pct, status)
            
        table.add_row(f"#{idx}", topic, voice_layout, status_str, elapsed_str)
        
    return table

def batch_job_worker(job_config, progress_dict, llm_lock=None):
    # Silence stdout/stderr to avoid CLI pollution
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
    
    # Disable cache clearing on exit for this process
    try:
        atexit.unregister(clear_cache)
    except Exception:
        pass
        
    idx = job_config["index"]
    output_filename = job_config["output_filename"]
    
    progress_dict[f"{idx}_start"] = time.time()
    
    # Update process-local state and settings dictionaries
    shared_state.state.clear()
    shared_state.state.update({
        "script_text": "",
        "selected_voice": job_config["voice_id"],
        "bg_video_path": job_config["bg_video_path"],
        "bg_video_bottom_path": job_config["bg_video_bottom_path"],
        "bg_music_path": job_config["bg_music_path"],
        "music_volume": job_config["music_volume"],
        "voice_volume": job_config["voice_volume"],
        "sub_font": job_config["sub_font"],
        "sub_size": job_config["sub_size"],
        "sub_color": job_config["sub_color"],
        "sub_highlight": job_config["sub_highlight"],
        "sub_outline": job_config["sub_outline"],
        "sub_outline_width": job_config["sub_outline_width"],
        "sub_bold": job_config["sub_bold"],
        "enable_emojis": job_config["enable_emojis"],
        "word_pop": job_config["word_pop"],
        "word_pop_scale": job_config["word_pop_scale"],
        "inactive_dim": job_config["inactive_dim"],
        "inactive_alpha": job_config["inactive_alpha"],
        "voice_speed": job_config.get("voice_speed", 1.0),
        "loaded_preset_name": "Randomized Batch Job",
    })
    
    shared_state.settings.clear()
    shared_state.settings.update(job_config["settings"])
    
    # Monkeypatch the config console for progress redirection in this worker process
    progress_console = ProgressConsole(idx, progress_dict)
    console.print = progress_console.print
    console.clear = progress_console.clear
    
    try:
        def generate_script():
            from openai import OpenAI
            api_key = shared_state.settings.get("api_key") or os.environ.get("OPENAI_API_KEY")
            base_url = shared_state.settings.get("base_url") or os.environ.get("OPENAI_BASE_URL")
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            response = client.chat.completions.create(
                model=job_config["model"],
                messages=[
                    {"role": "system", "content": job_config["system_prompt"]},
                    {"role": "user", "content": job_config["prompt"]}
                ],
                temperature=job_config["script_temp"]
            )
            return response.choices[0].message.content.strip()

        if llm_lock is not None:
            progress_dict[idx] = "Waiting for LLM"
            with llm_lock:
                progress_dict[idx] = "LLM Script"
                script_text = generate_script()
        else:
            progress_dict[idx] = "LLM Script"
            script_text = generate_script()

        shared_state.state["script_text"] = script_text
        progress_dict[idx] = "Compiling"
        
        def ffmpeg_progress(pct):
            console.print(f"FFmpeg Rendering ({pct:.1f}%)")

        success = compile_video_flow(skip_confirm=True, custom_output_filename=output_filename, progress_callback=ffmpeg_progress)
        if success:
            progress_dict[idx] = "Done"
            progress_dict[f"{idx}_end"] = time.time()
            return (idx, True, output_filename)
        else:
            progress_dict[idx] = "Failed"
            progress_dict[f"{idx}_end"] = time.time()
            return (idx, False, "Compilation failed (check logs/app.log)")
    except Exception as e:
        from cli.config import logger
        logger.error(f"Batch job {idx} exception: {e}\n{traceback.format_exc()}")
        progress_dict[idx] = f"Failed: {str(e)}"
        progress_dict[f"{idx}_end"] = time.time()
        return (idx, False, str(e))
