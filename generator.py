import os
import subprocess
import json
import asyncio
import urllib.request
import sys
import random
import logging
import ffmpeg

logger = logging.getLogger("shorts_creator.generator")
if not logger.handlers and not logging.getLogger("shorts_creator").handlers:
    logger.addHandler(logging.NullHandler())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_PATH = os.path.join(MODELS_DIR, "kokoro-v1.0.onnx")
VOICES_PATH = os.path.join(MODELS_DIR, "voices-v1.0.bin")

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

def download_file(url: str, dest: str, description: str):
    print(f"Downloading {description} from {url}...")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    
    def progress_hook(count, block_size, total_size):
        if total_size > 0:
            percent = min(100, int(count * block_size * 100 / total_size))
            sys.stdout.write(f"\rDownloading... {percent}%")
            sys.stdout.flush()
            
    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress_hook)
        print("\nDownload complete.")
    except Exception as e:
        print() # New line after the progress carriage return
        logger.error(f"Failed to download {description} from {url}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to download {description} from {url}. Please check your internet connection. Error: {e}")

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    if cs == 100:
        cs = 0
        s += 1
        if s == 60:
            s = 0
            m += 1
            if m == 60:
                m = 0
                h += 1
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

_KOKORO_SESSION = None
_KOKORO_INSTANCE = None

async def generate_voice(text: str, voice: str, output_path: str):
    """
    Generates local voice audio from text using Kokoro ONNX.
    Downloads the model files if they are not present.
    """
    global _KOKORO_SESSION, _KOKORO_INSTANCE
    
    try:
        if not os.path.exists(MODEL_PATH):
            download_file(MODEL_URL, MODEL_PATH, "Kokoro ONNX model (82MB)")
        if not os.path.exists(VOICES_PATH):
            download_file(VOICES_URL, VOICES_PATH, "Kokoro voices data (25MB)")
    except Exception as e:
        logger.error(f"Voice generation failed during dependency download: {e}", exc_info=True)
        raise
        
    try:
        import soundfile as sf
    except ImportError as e:
        logger.error("Failed to import 'soundfile'. Ensure it is installed.", exc_info=True)
        raise RuntimeError("Failed to import 'soundfile'. Please run 'pip install soundfile' to install it.") from e
    
    lang = "en-us"
    if voice.startswith("bf_") or voice.startswith("bm_"):
        lang = "en-gb"
        
    if _KOKORO_INSTANCE is None:
        try:
            import onnxruntime as rt
            from kokoro_onnx import Kokoro
            
            # Configure SessionOptions to explicitly set threads and avoid affinity errors
            sess_opts = rt.SessionOptions()
            num_threads = os.cpu_count() or 1
            sess_opts.intra_op_num_threads = num_threads
            sess_opts.inter_op_num_threads = num_threads
            
            # Check if kokoro-onnx installed with kokoro-onnx[gpu] feature or ONNX_PROVIDER is set
            providers = ["CPUExecutionProvider"]
            import importlib.util
            gpu_enabled = importlib.util.find_spec("onnxruntime-gpu")
            if gpu_enabled:
                providers = rt.get_available_providers()
                
            env_provider = os.getenv("ONNX_PROVIDER")
            if env_provider:
                providers = [env_provider]
                
            _KOKORO_SESSION = rt.InferenceSession(MODEL_PATH, sess_options=sess_opts, providers=providers)
            _KOKORO_INSTANCE = Kokoro.from_session(_KOKORO_SESSION, VOICES_PATH)
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro ONNX model: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize Kokoro ONNX model: {e}") from e
        
    try:
        # Run the CPU-bound Kokoro model creation
        samples, sample_rate = _KOKORO_INSTANCE.create(
            text,
            voice=voice,
            speed=1.0,
            lang=lang
        )
        sf.write(output_path, samples, sample_rate)
    except Exception as e:
        logger.error(f"Error during audio generation or saving: {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate/save voice audio: {e}") from e

def get_video_info(video_path: str) -> dict:
    """
    Queries ffprobe for video width, height, and duration.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Background video file not found at: {video_path}")
        
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "json",
        video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        err_msg = (
            f"FFprobe failed to analyze background video '{os.path.basename(video_path)}'. "
            f"The video file may be corrupt or in an unsupported format.\n"
            f"Command run: {' '.join(cmd)}\n"
            f"Error details: {e.stderr.strip()}"
        )
        logger.error(err_msg, exc_info=True)
        raise RuntimeError(err_msg) from e
    except Exception as e:
        logger.error(f"An unexpected error occurred while running ffprobe on '{video_path}': {e}", exc_info=True)
        raise RuntimeError(f"An unexpected error occurred while running ffprobe on '{video_path}': {e}") from e

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON output from ffprobe for '{video_path}': {e}") from e

    if "streams" in info and len(info["streams"]) > 0:
        stream = info["streams"][0]
        try:
            return {
                "width": int(stream.get("width", 0)),
                "height": int(stream.get("height", 0)),
                "duration": float(stream.get("duration") or 0.0)
            }
        except (ValueError, TypeError) as e:
            raise RuntimeError(f"Invalid stream format metadata in video file '{video_path}': {e}")
    return {"width": 0, "height": 0, "duration": 0.0}

def hex_to_ass_color(hex_str: str) -> str:
    """
    Converts standard HEX color string (#RRGGBB or RRGGBB) to ASS color format (&HBBGGRR).
    """
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) == 6:
        r = hex_str[0:2]
        g = hex_str[2:4]
        b = hex_str[4:6]
        return f"&H{b}{g}{r}"
    elif len(hex_str) == 8:
        r = hex_str[0:2]
        g = hex_str[2:4]
        b = hex_str[4:6]
        a = hex_str[6:8]
        return f"&H{a}{b}{g}{r}"
    return "&HFFFFFF"

def find_emoji_for_word(word: str, emoji_map: dict) -> str:
    if not emoji_map:
        return ""
    clean_w = "".join(c for c in word.lower() if c.isalnum())
    if not clean_w:
        return ""
    sorted_keys = sorted(emoji_map.keys(), key=len, reverse=True)
    for key in sorted_keys:
        clean_key = key.lower()
        if clean_w.startswith(clean_key) or clean_key in clean_w:
            return emoji_map[key]
    return ""

def generate_ass_subtitles(words: list, output_path: str, style_opts: dict = None, emoji_map: dict = None):
    """
    Groups words into short phrases and writes a styled ASS subtitle file
    with active word highlighting, word pop, inactive dimming, and contextual emojis.
    """
    if not style_opts:
        style_opts = {}
        
    font_name = style_opts.get("font_name", "Arial")
    font_size = style_opts.get("font_size", 72)
    primary_color = style_opts.get("primary_color", "#FFFFFF")
    highlight_color = style_opts.get("highlight_color", "#00FFFF")
    outline_color = style_opts.get("outline_color", "#000000")
    outline_width = style_opts.get("outline_width", 5)
    bold_val = -1 if style_opts.get("bold", True) else 0
    alignment = style_opts.get("alignment", 5)
    margin_v = style_opts.get("margin_v", 10)

    # Subtitle animation options
    word_pop = style_opts.get("word_pop", True)
    word_pop_scale = style_opts.get("word_pop_scale", 1.15)
    inactive_dim = style_opts.get("inactive_dim", True)
    inactive_alpha = style_opts.get("inactive_alpha", "88")
    enable_emojis = style_opts.get("enable_emojis", True)

    scale_pct = int(word_pop_scale * 100)

    ass_primary = hex_to_ass_color(primary_color)
    ass_highlight = hex_to_ass_color(highlight_color)
    ass_outline = hex_to_ass_color(outline_color)

    phrases = []
    current_phrase = []
    
    for word_info in words:
        word = word_info["word"].strip()
        start = word_info["start"]
        end = word_info["end"]
        
        if not current_phrase:
            current_phrase.append({"word": word, "start": start, "end": end})
        else:
            prev = current_phrase[-1]
            time_span = end - current_phrase[0]["start"]
            gap = start - prev["end"]
            
            # Group into max 3 words, max 1.5 seconds, max gap 0.3s
            if len(current_phrase) < 3 and time_span < 1.5 and gap < 0.3:
                current_phrase.append({"word": word, "start": start, "end": end})
            else:
                phrases.append(current_phrase)
                current_phrase = [{"word": word, "start": start, "end": end}]
    if current_phrase:
        phrases.append(current_phrase)
        
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # Alignment 5 = Middle center
        f"Style: Default,{font_name},{font_size},{ass_primary},&H00FFFF,{ass_outline},&H000000,{bold_val},0,0,0,100,100,0,0,1,{outline_width},0,{alignment},10,10,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]
    
    for phrase in phrases:
        phrase_words = [p["word"] for p in phrase]
        
        # Determine if any word in the phrase has an emoji
        phrase_emojis = []
        has_any_emoji = False
        for word_info in phrase:
            w_emoji = find_emoji_for_word(word_info["word"], emoji_map) if (enable_emojis and emoji_map) else ""
            phrase_emojis.append(w_emoji)
            if w_emoji:
                has_any_emoji = True

        for idx, active_word_info in enumerate(phrase):
            start_str = format_time(active_word_info["start"])
            
            # Stretch the end time to the next word's start to prevent subtitle blinking
            if idx < len(phrase) - 1:
                end_str = format_time(phrase[idx + 1]["start"])
            else:
                end_str = format_time(active_word_info["end"])
                
            text_parts = []
            for w_idx, w in enumerate(phrase_words):
                if w_idx == idx:
                    # Active word: pop and full opacity with highlight color
                    active_tags = "\\alpha&H00&"
                    if word_pop:
                        active_tags += f"\\fscx{scale_pct}\\fscy{scale_pct}"
                    active_tags += f"\\c{ass_highlight}&"
                    text_parts.append(f"{{{active_tags}}}{w}{{\\r}}")
                else:
                    # Inactive word: dim if enabled
                    if inactive_dim:
                        text_parts.append(f"{{\\alpha&H{inactive_alpha}&}}{w}{{\\r}}")
                    else:
                        text_parts.append(w)
            
            phrase_text = " ".join(text_parts)
            
            if has_any_emoji:
                # If there's an emoji for the active word, display it, otherwise use \h to preserve vertical height
                emoji_top = phrase_emojis[idx] if phrase_emojis[idx] else "\\h"
                dialogue_text = f"{emoji_top}\\N{phrase_text}"
            else:
                dialogue_text = phrase_text
                
            lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{dialogue_text}")
            
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        logger.error(f"Failed to write ASS subtitles to '{output_path}': {e}", exc_info=True)
        raise RuntimeError(f"Failed to write ASS subtitles: {e}") from e

def compile_video(
    bg_video_path: str,
    audio_path: str,
    subs_path: str,
    output_path: str,
    audio_duration: float,
    music_path: str = None,
    voice_volume: float = 1.0,
    music_volume: float = 0.15,
    bg_video_bottom_path: str = None,
    render_preset: str = 'veryfast',
    render_resolution: str = '1080p',
    progress_callback = None
):
    """
    Renders the final vertical video using FFmpeg.
    If bg_video_bottom_path is provided, crops both top and bottom videos to 9:8 and stacks them (split screen).
    Otherwise, crops to 9:16 and scales to 1080x1920 (single screen).
    Loops backgrounds, blends voiceover, and burns subtitles.
    Optionally blends looped background music with custom volumes.
    """
    # 1. Get original top video details
    info_top = get_video_info(bg_video_path)
    w_top = info_top["width"]
    h_top = info_top["height"]
    bg_top_duration = info_top.get("duration", 0.0)
    
    if w_top == 0 or h_top == 0:
        raise ValueError(f"Could not retrieve video dimensions for {bg_video_path}")
        
    # Calculate random start offset for top background video
    start_offset_top = 0.0
    if bg_top_duration > audio_duration:
        start_offset_top = random.uniform(0.0, bg_top_duration - audio_duration)
        print(f"Selecting random top background start offset: {start_offset_top:.2f}s (duration: {bg_top_duration:.2f}s)")
        
    is_split = bg_video_bottom_path is not None and os.path.exists(bg_video_bottom_path)
    
    if is_split:
        # Get bottom video details
        info_bottom = get_video_info(bg_video_bottom_path)
        w_bottom = info_bottom["width"]
        h_bottom = info_bottom["height"]
        bg_bottom_duration = info_bottom.get("duration", 0.0)
        
        if w_bottom == 0 or h_bottom == 0:
            raise ValueError(f"Could not retrieve video dimensions for {bg_video_bottom_path}")
            
        start_offset_bottom = 0.0
        if bg_bottom_duration > audio_duration:
            start_offset_bottom = random.uniform(0.0, bg_bottom_duration - audio_duration)
            print(f"Selecting random bottom background start offset: {start_offset_bottom:.2f}s (duration: {bg_bottom_duration:.2f}s)")
            
        # 9:8 ratio is 1.125
        target_ratio = 1.125
        
        # Crop Top Video to 9:8
        current_ratio_top = float(w_top) / float(h_top)
        if current_ratio_top > target_ratio:
            crop_w_top = int(h_top * target_ratio) // 2 * 2
            crop_h_top = h_top
            offset_x_top = (w_top - crop_w_top) // 2
            offset_y_top = 0
        else:
            crop_w_top = w_top
            crop_h_top = int(w_top / target_ratio) // 2 * 2
            offset_x_top = 0
            offset_y_top = (h_top - crop_h_top) // 2
            
        # Crop Bottom Video to 9:8
        current_ratio_bottom = float(w_bottom) / float(h_bottom)
        if current_ratio_bottom > target_ratio:
            crop_w_bottom = int(h_bottom * target_ratio) // 2 * 2
            crop_h_bottom = h_bottom
            offset_x_bottom = (w_bottom - crop_w_bottom) // 2
            offset_y_bottom = 0
        else:
            crop_w_bottom = w_bottom
            crop_h_bottom = int(w_bottom / target_ratio) // 2 * 2
            offset_x_bottom = 0
            offset_y_bottom = (h_bottom - crop_h_bottom) // 2
    else:
        # Compute standard 9:16 crop dimensions
        target_ratio = 9.0 / 16.0
        current_ratio = float(w_top) / float(h_top)
        
        if current_ratio > target_ratio:
            # Landscape: crop width
            crop_w = int(h_top * target_ratio) // 2 * 2
            crop_h = h_top
            offset_x = (w_top - crop_w) // 2
            offset_y = 0
        else:
            # Narrow portrait: crop height
            crop_w = w_top
            crop_h = int(w_top / target_ratio) // 2 * 2
            offset_x = 0
            offset_y = (h_top - crop_h) // 2

    # Burn subtitles info
    subs_filename = os.path.basename(subs_path)
    subs_dir = os.path.dirname(subs_path)

    # 2. Build input streams
    input_args_top = {"stream_loop": -1}
    if start_offset_top > 0.0:
        input_args_top["ss"] = f"{start_offset_top:.2f}"
    
    top_video_in = ffmpeg.input(bg_video_path, **input_args_top).video

    target_w = 1080 if render_resolution == '1080p' else 720
    target_h = 1920 if render_resolution == '1080p' else 1280

    if is_split:
        input_args_bottom = {"stream_loop": -1}
        if start_offset_bottom > 0.0:
            input_args_bottom["ss"] = f"{start_offset_bottom:.2f}"
        bottom_video_in = ffmpeg.input(bg_video_bottom_path, **input_args_bottom).video

        # Crop, scale and stack top and bottom streams
        top_v = top_video_in.filter('crop', crop_w_top, crop_h_top, offset_x_top, offset_y_top).filter('scale', target_w, target_h // 2)
        bottom_v = bottom_video_in.filter('crop', crop_w_bottom, crop_h_bottom, offset_x_bottom, offset_y_bottom).filter('scale', target_w, target_h // 2)
        v_stream = ffmpeg.filter([top_v, bottom_v], 'vstack')
    else:
        v_stream = top_video_in.filter('crop', crop_w, crop_h, offset_x, offset_y).filter('scale', target_w, target_h)

    # Apply subtitles to the video stream
    v_stream = v_stream.filter('subtitles', filename=subs_filename)

    # Add smooth transitions: Video Fade-in / Fade-out (0.5s duration)
    v_stream = v_stream.filter('fade', type='in', start_time=0, duration=0.5)
    v_stream = v_stream.filter('fade', type='out', start_time=audio_duration - 0.5, duration=0.5)

    # 3. Audio Streams Setup
    voice_audio = ffmpeg.input(audio_path).audio.filter('volume', voice_volume)

    has_music = music_path and os.path.exists(music_path)
    if has_music:
        music_audio = ffmpeg.input(music_path, stream_loop=-1).audio.filter('volume', music_volume)
        
        # Mix voice and music
        a_stream = ffmpeg.filter([voice_audio, music_audio], 'amix', inputs=2, duration='first', dropout_transition=0)
    else:
        a_stream = voice_audio

    # 4. output node
    out = ffmpeg.output(
        v_stream,
        a_stream,
        output_path,
        vcodec='libx264',
        preset=render_preset,
        crf=23,
        acodec='aac',
        audio_bitrate='192k',
        t=f"{audio_duration:.2f}"
    )

    # Compile ffmpeg-python stream spec to command line arguments list
    cmd = ffmpeg.compile(out, overwrite_output=True)

    # Run FFmpeg inside the folder where subtitles are stored so that relative path works flawlessly
    cwd = subs_dir if subs_dir else None
    
    stderr_lines = []
    return_code = -1
    try:
        import re
        with subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            bufsize=1,
            encoding='utf-8',
            errors='replace'
        ) as process:
            while True:
                line = process.stderr.readline()
                if not line:
                    break
                stderr_lines.append(line)
                
                # Parse progress: "time=00:00:05.12"
                if "time=" in line:
                    match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})", line)
                    if match:
                        hours = int(match.group(1))
                        minutes = int(match.group(2))
                        seconds = int(match.group(3))
                        centiseconds = int(match.group(4))
                        elapsed = hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
                        if audio_duration > 0:
                            pct = min(100.0, (elapsed / audio_duration) * 100.0)
                            if progress_callback:
                                try:
                                    progress_callback(pct)
                                except Exception:
                                    pass
                    else:
                        match_sec = re.search(r"time=(\d{2}):(\d{2}):(\d{2})", line)
                        if match_sec:
                            hours = int(match_sec.group(1))
                            minutes = int(match_sec.group(2))
                            seconds = int(match_sec.group(3))
                            elapsed = hours * 3600 + minutes * 60 + seconds
                            if audio_duration > 0:
                                pct = min(100.0, (elapsed / audio_duration) * 100.0)
                                if progress_callback:
                                    try:
                                        progress_callback(pct)
                                    except Exception:
                                        pass
            process.wait()
            return_code = process.returncode
    except Exception as e:
        logger.error(f"Failed to execute FFmpeg command compiled via ffmpeg-python: {e}", exc_info=True)
        raise RuntimeError(f"FFmpeg execution failed: {e}") from e
    
    if return_code != 0:
        full_stderr = "".join(stderr_lines)
        err_msg = (
            f"FFmpeg compilation failed with exit code {return_code}.\n"
            f"FFmpeg command: {' '.join(cmd)}\n"
            f"Error details: {full_stderr.strip()}"
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg)

