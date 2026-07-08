import os
import re
import traceback
import time
from rich.table import Table

from gui import state as shared_state
from gui.config import console, logger
from gui.compiler import compile_video_flow
from dataclasses import dataclass, fields
from typing import Optional
from contextlib import redirect_stdout, redirect_stderr

@dataclass
class BatchJobConfig:
    # Required fields (no defaults)
    index: int
    prompt: str
    voice_id: str
    bg_video_path: str
    output_filename: str
    settings: dict

    # Optional fields (with defaults)
    bg_video_bottom_path: Optional[str] = None
    bg_music_path: Optional[str] = None
    music_volume: float = 0.15
    voice_volume: float = 1.0
    sub_font: str = "Arial"
    sub_size: int = 72
    sub_color: str = "#FFFFFF"
    sub_highlight: str = "#00FFFF"
    sub_outline: str = "#000000"
    sub_outline_width: int = 5
    sub_bold: bool = False
    enable_emojis: bool = False
    word_pop: bool = False
    word_pop_scale: float = 1.0
    inactive_dim: bool = False
    inactive_alpha: str = "FF"
    voice_speed: Optional[float] = None
    sub_uppercase: bool = True
    sub_border_style: int = 1
    sub_shadow_width: int = 0
    sub_bg_color: str = "#000000"
    sub_bg_alpha: str = "80"
    single_word_mode: bool = False
    emoji_position: str = "above"
    emoji_font: str = "Symbola"
    sub_animation_style: str = "tiktok_pop"
    script_temp: float = 0.7
    meta_temp: float = 0.7
    model: str = "gpt-4o-mini"
    system_prompt: str = ""
    generated_title: Optional[str] = None
    generated_hashtags: Optional[str] = None
    script_text: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "BatchJobConfig":
        valid_fields = {f.name for f in fields(cls)}
        kwargs = {k: data[k] for k in data if k in valid_fields}
        return cls(**kwargs)

class ProgressConsole:
    def __init__(self, idx, p_dict):
        self.idx = idx
        self.p_dict = p_dict
        
    def print(self, *args, **kwargs):
        msg = " ".join(str(a) for a in args)
        try:
            if "Generating voice for sentence" in msg:
                match = re.search(r"sentence (\d+/\d+)", msg)
                if match:
                    self.p_dict[self.idx] = f"Voice Generation ({match.group(1)})"
                else:
                    self.p_dict[self.idx] = "Voice Generation"
            elif "Transcribing audio..." in msg or "Transcribing full audio file" in msg:
                match = re.search(r"(\d+)%", msg)
                if match:
                    self.p_dict[self.idx] = f"Transcription ({match.group(1)}%)"
                else:
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
                self.p_dict[self.idx] = "Reusing Cache (Voice)"
        except Exception:
            pass
            
    def clear(self):
        pass

def get_progress_percentage(status):
    if status == "Queued":
        return 0
    elif status == "Waiting for LLM":
        return 5
    elif status.startswith("LLM Script"):
        return 10
    elif status == "LLM Metadata":
        return 15
    elif status == "Waiting for Compilation":
        return 20
    elif status.startswith("Voice Generation"):
        match = re.search(r"\((\d+)/(\d+)\)", status)
        if match:
            s_idx = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                return 20 + int((s_idx / total) * 25)
        return 30
    elif status == "Reusing Cache (Voice)":
        return 45
    elif status == "Compiling":
        return 28
    elif status.startswith("Transcription"):
        match = re.search(r"\((\d+)%\)", status)
        if match:
            pct = int(match.group(1))
            return 45 + int((pct / 100) * 10)
        return 48
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

def orchestrate_batch_job(job_config, progress_dict, llm_executor, video_executor):
    # Validate job config early to catch missing required keys
    BatchJobConfig.from_dict(job_config)
    idx = job_config["index"]
    progress_dict[f"{idx}_start"] = time.time()
    try:
        progress_dict[idx] = "Waiting for LLM"
        
        # 1. Run LLM in ThreadPool
        future_llm = llm_executor.submit(llm_job_worker, job_config, progress_dict)
        success, script_text, err_msg = future_llm.result()
        
        if not success:
            progress_dict[idx] = f"Failed: {err_msg}"
            progress_dict[f"{idx}_end"] = time.time()
            return (idx, False, err_msg)
            
        job_config["script_text"] = script_text
        
        progress_dict[idx] = "Waiting for Compilation"
        
        # 2. Run Video Generation in ProcessPool
        future_video = video_executor.submit(video_job_worker, job_config, progress_dict)
        return future_video.result()
        
    except Exception as e:
        progress_dict[idx] = f"Failed: {str(e)}"
        progress_dict[f"{idx}_end"] = time.time()
        return (idx, False, str(e))

def retry_with_backoff(func, max_attempts=3, base_delay=1.0):
    """Retry a callable on transient errors with exponential backoff.
    Retries on ConnectionError, Timeout, and exceptions mentioning
    rate/timeout/connection/overloaded.  Does NOT retry on bad request
    or auth errors (those are configuration problems).
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            err_str = str(e).lower()
            # Never retry bad-request / auth errors
            if "bad request" in err_str or "auth" in err_str or "unauthorized" in err_str or "401" in err_str or "403" in err_str:
                raise
            is_retryable = (
                isinstance(e, (ConnectionError, TimeoutError))
                or any(w in err_str for w in ["rate", "timeout", "connection", "overloaded", "api_error"])
            )
            if not is_retryable or attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)

def llm_job_worker(job_config, progress_dict):
    idx = job_config["index"]
    progress_dict[idx] = "LLM Script"
    try:
        from openai import OpenAI
        from gui.utils import discover_opencode_keys
        
        profiles = job_config["settings"].get("llm_profiles", [])
        active_id = job_config["settings"].get("active_llm_profile_id")
        active_profile = {}
        for p in profiles:
            if p.get("id") == active_id:
                active_profile = p
                break
        if not active_profile and profiles:
            active_profile = profiles[0]
            
        api_key = active_profile.get("api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = active_profile.get("base_url") or os.environ.get("OPENAI_BASE_URL")
        
        opencode_key, _ = discover_opencode_keys()
        if not api_key:
            api_key = opencode_key
            if api_key and not base_url:
                base_url = "https://opencode.ai/zen/go/v1"
                if job_config.get("model") in [None, "", "gpt-4o-mini"]:
                    job_config["model"] = "deepseek-v4-flash"
                
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        # Streaming LLM call with retry + buffered progress
        script_text = ""
        _last_ts = time.time()
        _last_wc = 0
        
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=job_config["model"],
                    messages=[
                        {"role": "system", "content": job_config["system_prompt"]},
                        {"role": "user", "content": job_config["prompt"]}
                    ],
                    temperature=job_config["script_temp"],
                    stream=True
                )
                break
            except Exception as e:
                err_str = str(e).lower()
                if "bad request" in err_str or "auth" in err_str or "unauthorized" in err_str or "401" in err_str or "403" in err_str:
                    raise
                is_retryable = (
                    isinstance(e, (ConnectionError, TimeoutError))
                    or any(w in err_str for w in ["rate", "timeout", "connection", "overloaded", "api_error"])
                )
                if not is_retryable or attempt == 2:
                    raise
                progress_dict[idx] = f"LLM Script (retry {attempt+1}/3)"
                time.sleep(1.0 * (2 ** attempt))
        
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content is not None:
                script_text += chunk.choices[0].delta.content
                word_count = len(script_text.split())
                now = time.time()
                if word_count - _last_wc >= 5 or now - _last_ts >= 0.25:
                    progress_dict[idx] = f"LLM Script ({word_count} words)"
                    _last_ts = now
                    _last_wc = word_count
                
        script_text = script_text.strip()
        
        try:
            progress_dict[idx] = "LLM Metadata"
            meta_prompt = f"Based on the following script, provide 1 short, catchy title (under 5 words) and exactly 5 trending TikTok hashtags. Format your response exactly as follows:\nTITLE: <title>\nHASHTAGS: <hashtags>\n\nScript:\n{script_text}"
            
            for attempt in range(3):
                try:
                    meta_response = client.chat.completions.create(
                        model=job_config["model"],
                        messages=[{"role": "user", "content": meta_prompt}],
                        temperature=job_config.get("meta_temp", 0.7)
                    )
                    break
                except Exception as e:
                    err_str = str(e).lower()
                    if "bad request" in err_str or "auth" in err_str or "unauthorized" in err_str or "401" in err_str or "403" in err_str:
                        raise
                    is_retryable = (
                        isinstance(e, (ConnectionError, TimeoutError))
                        or any(w in err_str for w in ["rate", "timeout", "connection", "overloaded", "api_error"])
                    )
                    if not is_retryable or attempt == 2:
                        raise
                    progress_dict[idx] = f"LLM Metadata (retry {attempt+1}/3)"
                    time.sleep(1.0 * (2 ** attempt))
            meta_text = meta_response.choices[0].message.content.strip()
            
            title = "batch_video"
            hashtags = ""
            for line in meta_text.split('\n'):
                if line.startswith("TITLE:"):
                    title = line.replace("TITLE:", "").strip()
                elif line.startswith("HASHTAGS:"):
                    hashtags = line.replace("HASHTAGS:", "").strip()
                    
            safe_title = re.sub(r'[\s\-]+', '_', title.lower())
            safe_title = re.sub(r'[^\w_]', '', safe_title).strip('_')
            if not safe_title:
                safe_title = "batch_video"
                
            orig_filename = job_config["output_filename"]
            timestamp_match = re.search(r"rendered_batch_(\d+)_", orig_filename)
            timestamp = timestamp_match.group(1) if timestamp_match else str(int(time.time()))
            
            new_filename = f"{safe_title}_{timestamp}_{idx}.mp4"
            job_config["output_filename"] = new_filename
            job_config["generated_title"] = title
            job_config["generated_hashtags"] = hashtags
        except Exception as e:
            # Fallback if secondary call fails
            job_config["generated_title"] = "Batch Video"
            job_config["generated_hashtags"] = "#shorts #video"
            
        return True, script_text, None

    except Exception as e:
        return False, None, str(e)

def video_job_worker(job_config, progress_dict):
        
    idx = job_config["index"]
    output_filename = job_config["output_filename"]
    
    # Update process-local state and settings dictionaries
    shared_state.state.clear()
    shared_state.state.update({
        "script_text": job_config["script_text"],
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
        try: progress_dict[idx] = "Compiling"
        except Exception:
            logger.warning(f"Batch job {idx}: failed to update progress (manager may have shut down)", exc_info=True)
        
        def ffmpeg_progress(pct):
            try:
                pct = float(pct)
            except (TypeError, ValueError):
                pct = 0.0
            console.print(f"FFmpeg Rendering ({pct:.1f}%)")

        with open(os.devnull, 'w') as devnull, \
             redirect_stdout(devnull), \
             redirect_stderr(devnull):
            success = retry_with_backoff(
                lambda: compile_video_flow(skip_confirm=True, custom_output_filename=output_filename, progress_callback=ffmpeg_progress)
            )
            if success:
                try:
                    from gui.config import OUTPUT_DIR
                    base_name = os.path.splitext(output_filename)[0]
                    txt_path = os.path.join(OUTPUT_DIR, f"{base_name}.txt")
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(f"{job_config.get('generated_title', 'Batch Video')}\n")
                        f.write(f"{job_config.get('generated_hashtags', '#shorts')}\n\n")
                        f.write(f"Script:\n{job_config.get('script_text', '')}\n")
                except Exception:
                    logger.warning(f"Batch job {idx}: failed to write metadata .txt (manager may have shut down)", exc_info=True)
        
        if success:
            try:
                progress_dict[idx] = "Done"
                progress_dict[f"{idx}_end"] = time.time()
            except Exception:
                logger.warning(f"Batch job {idx}: failed to update progress (manager may have shut down)", exc_info=True)
            return (idx, True, output_filename)
        else:
            try:
                progress_dict[idx] = "Failed"
                progress_dict[f"{idx}_end"] = time.time()
            except Exception:
                logger.warning(f"Batch job {idx}: failed to update progress (manager may have shut down)", exc_info=True)
            return (idx, False, "Compilation failed (check logs/app.log)")
    except Exception as e:
        logger.error(f"Batch job {idx} exception: {e}\n{traceback.format_exc()}")
        try:
            progress_dict[idx] = f"Failed: {str(e)}"
            progress_dict[f"{idx}_end"] = time.time()
        except Exception:
            logger.warning(f"Batch job {idx}: failed to update progress (manager may have shut down)", exc_info=True)
        return (idx, False, str(e))
