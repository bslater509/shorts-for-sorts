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

logging.getLogger("asyncio").setLevel(logging.ERROR)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_PATH = os.path.join(MODELS_DIR, "kokoro-v1.0.onnx")
VOICES_PATH = os.path.join(MODELS_DIR, "voices.json")

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"

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

_TTS_INSTANCE = None

import threading
# Use RLock (reentrant lock) so the same thread can acquire the lock multiple times.
# This prevents a deadlock where generate_voice holds the lock and calls
# init_tts_session(), which also tries to acquire the same lock.
_TTS_LOCK = threading.RLock()

def init_tts_session():
    global _TTS_INSTANCE
    with _TTS_LOCK:
        if _TTS_INSTANCE is not None:
            return
            
        if not os.path.exists(MODEL_PATH):
            download_file(MODEL_URL, MODEL_PATH, "Kokoro ONNX Model")
        if not os.path.exists(VOICES_PATH):
            download_file(VOICES_URL, VOICES_PATH, "Kokoro Voices Profile")
            
        try:
            from kokoro_onnx import Kokoro
        except ImportError as e:
            logger.error("Failed to import 'kokoro_onnx'. Ensure it is installed.", exc_info=True)
            raise RuntimeError("Failed to import 'kokoro_onnx'. Please run 'pip install kokoro-onnx' to install it.") from e
            
        logger.info(f"Loading Kokoro TTS model (CPU ONNX)...")
        try:
            _TTS_INSTANCE = Kokoro(MODEL_PATH, VOICES_PATH)
            logger.info("Kokoro model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro model: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize Kokoro model: {e}") from e

def unload_tts_model():
    """Unloads the TTS model from memory to free it up for batch processes."""
    global _TTS_INSTANCE
    with _TTS_LOCK:
        if _TTS_INSTANCE is not None:
            import gc
            del _TTS_INSTANCE
            _TTS_INSTANCE = None
            gc.collect()
            logger.info("Kokoro model unloaded from memory.")

def generate_voice(text: str, voice: str, output_path: str, default_speed: float = 1.0):
    """
    Generates local voice audio from text using Kokoro TTS.
    """
    global _TTS_INSTANCE
    import re
    import numpy as np
    import soundfile as sf
    import os
    
    # Acquire lock immediately to prevent races
    with _TTS_LOCK:
        if _TTS_INSTANCE is None:
            init_tts_session()
        
    # Convert pause tags to ellipses for natural pauses.
    text_with_pauses = re.sub(r'\[(pause|silence)=.*?\]', '... ', text)
    # Strip any other remaining tags like [slow], [voice=...]
    clean_text = re.sub(r'\[.*?\]', '', text_with_pauses).strip()
    
    if not clean_text:
        # fallback to a tiny bit of silence if nothing was generated
        sample_rate = 24000
        final_audio = np.zeros(sample_rate, dtype=np.float32)
        sf.write(output_path, final_audio, sample_rate)
        return
    
    try:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            tmp_path = tmp_audio.name
            
        try:
            with _TTS_LOCK:
                # Provide a fallback voice if the specified voice is not recognized by Kokoro
                target_voice = voice if voice else "af_bella"
                samples, sample_rate = _TTS_INSTANCE.create(clean_text, voice=target_voice, speed=default_speed, lang="en-us")
                sf.write(tmp_path, samples, sample_rate)
            
            # Apply FFmpeg post-processing: EQ
            stream = ffmpeg.input(tmp_path)
            
            # Radio/Podcast EQ: High-pass at 80Hz, boost bass at 200Hz, boost treble at 3000Hz
            stream = ffmpeg.filter(stream, 'highpass', f=80)
            stream = ffmpeg.filter(stream, 'lowshelf', g=3, f=200)
            stream = ffmpeg.filter(stream, 'highshelf', g=4, f=3000)
                
            stream = ffmpeg.output(stream, output_path, loglevel="error")
            ffmpeg.run(stream, overwrite_output=True)
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        logger.error(f"Error during Kokoro voice generation: {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate voice audio with Kokoro: {e}") from e


def get_video_info(video_path: str, suppress_errors: bool = False) -> dict:
    """
    Queries ffprobe for video width, height, and duration.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found at: {video_path}")
        
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
            f"FFprobe failed to analyze video '{os.path.basename(video_path)}'. "
            f"The video file may be corrupt or in an unsupported format.\n"
            f"Command run: {' '.join(cmd)}\n"
            f"Error details: {e.stderr.strip()}"
        )
        if not suppress_errors:
            logger.error(err_msg, exc_info=True)
        raise RuntimeError(err_msg) from e
    except Exception as e:
        if not suppress_errors:
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
    logger.warning(f"hex_to_ass_color: malformed hex input '{hex_str}' — defaulting to white")
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

def hex_and_alpha_to_ass(hex_str: str, alpha_str: str = "00") -> str:
    """
    Converts a HEX color (e.g. #000000) and alpha transparency (e.g. 00-FF)
    to ASS color format with alpha (&HAABBGGRR).
    """
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) == 6:
        r = hex_str[0:2]
        g = hex_str[2:4]
        b = hex_str[4:6]
    else:
        r, g, b = "00", "00", "00"
    
    alpha = alpha_str.strip()
    if not alpha:
        alpha = "00"
    elif len(alpha) == 1:
        alpha = "0" + alpha
    return f"&H{alpha}{b}{g}{r}"

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

    # New styling options
    uppercase = style_opts.get("uppercase", True)
    border_style = style_opts.get("border_style", 1)  # 1: Outline+Shadow, 3: Opaque Box
    shadow_width = style_opts.get("shadow_width", 0)
    back_color = style_opts.get("back_color", "#000000")
    back_alpha = style_opts.get("back_alpha", "00")
    words_per_screen = str(style_opts.get("words_per_screen", "3"))
    emoji_position = style_opts.get("emoji_position", "above") if enable_emojis else "none"
    emoji_font = style_opts.get("emoji_font", "Symbola")
    animation_style = style_opts.get("sub_animation_style", "tiktok_pop")

    scale_pct = int(word_pop_scale * 100)

    ass_primary = hex_to_ass_color(primary_color)
    ass_highlight = hex_to_ass_color(highlight_color)
    ass_outline = hex_to_ass_color(outline_color)
    ass_back = hex_and_alpha_to_ass(back_color, back_alpha)

    # Animation style colors for style setup
    if animation_style in ("karaoke_sweep", "typewriter_swipe"):
        primary_style_color = ass_highlight
        if animation_style == "typewriter_swipe":
            secondary_style_color = "&HFF000000"  # Fully transparent for upcoming words
        elif inactive_dim:
            secondary_style_color = hex_and_alpha_to_ass(primary_color, inactive_alpha)
        else:
            secondary_style_color = ass_primary
    else:
        primary_style_color = ass_primary
        secondary_style_color = "&H00FFFF" # default secondary

    phrases = []
    current_phrase = []
    
    for word_info in words:
        word = word_info["word"].strip()
        if uppercase:
            word = word.upper()
        start = word_info["start"]
        end = word_info["end"]
        
        word_dict = {"word": word, "start": start, "end": end}
        if "sentence_idx" in word_info:
            word_dict["sentence_idx"] = word_info["sentence_idx"]

        if not current_phrase:
            current_phrase.append(word_dict)
        else:
            prev = current_phrase[-1]
            time_span = end - current_phrase[0]["start"]
            gap = start - prev["end"]
            
            same_sentence = False
            if "sentence_idx" in word_info and "sentence_idx" in current_phrase[0]:
                same_sentence = (word_info["sentence_idx"] == current_phrase[0]["sentence_idx"])
            
            if words_per_screen == "1":
                should_group = False
            elif words_per_screen == "3":
                should_group = len(current_phrase) < 3 and gap < 0.5
            else:
                # "sentence" or default
                if "sentence_idx" in word_info:
                    should_group = same_sentence
                else:
                    should_group = time_span < 10.0 and gap < 0.5

            if should_group:
                current_phrase.append(word_dict)
            else:
                phrases.append(current_phrase)
                current_phrase = [word_dict]
    if current_phrase:
        phrases.append(current_phrase)
        
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 1",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # Custom border style, outline width, shadow width, and back color (shadow/box background color)
        f"Style: Default,{font_name},{font_size},{primary_style_color},{secondary_style_color},{ass_outline},{ass_back},{bold_val},0,0,0,100,100,0,0,{border_style},{outline_width},{shadow_width},{alignment},60,60,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]
    
    if animation_style in ("karaoke_sweep", "typewriter_swipe"):
        for p_idx, phrase in enumerate(phrases):
            phrase_start_str = format_time(phrase[0]["start"])
            if p_idx < len(phrases) - 1:
                phrase_end_str = format_time(phrases[p_idx + 1][0]["start"])
            else:
                phrase_end_str = format_time(phrase[-1]["end"])
                
            # Determine if any word in the phrase has an emoji
            phrase_emojis = []
            first_emoji = ""
            for word_info in phrase:
                w_emoji = find_emoji_for_word(word_info["word"], emoji_map) if emoji_position != "none" and emoji_map else ""
                phrase_emojis.append(w_emoji)
                if w_emoji and not first_emoji:
                    first_emoji = w_emoji
                    
            text_parts = []
            last_end = phrase[0]["start"]
            for idx, w_info in enumerate(phrase):
                w = w_info["word"]
                start = w_info["start"]
                end = w_info["end"]
                
                # Check for gap between words
                if start > last_end:
                    gap_cs = int(round((start - last_end) * 100))
                    if gap_cs > 0:
                        text_parts.append(f"{{\\kf{gap_cs}}}")
                
                word_dur = end - start
                word_cs = int(round(word_dur * 100))
                if word_cs <= 0:
                    word_cs = 1
                
                w_text = w
                if emoji_position == "same_line" and phrase_emojis[idx]:
                    wrapped_emoji = f"{{\\fn{emoji_font}}}{phrase_emojis[idx]}{{\\fn}}"
                    w_text = f"{wrapped_emoji} {w_text}"
                
                if idx < len(phrase) - 1:
                    text_parts.append(f"{{\\kf{word_cs}}}{w_text} ")
                else:
                    text_parts.append(f"{{\\kf{word_cs}}}{w_text}")
                last_end = end
                
            phrase_text = "".join(text_parts)
            
            if emoji_position == "above" and first_emoji:
                emoji_top = f"{{\\fn{emoji_font}}}{first_emoji}{{\\fn}}"
                dialogue_text = f"{emoji_top}\\N{phrase_text}"
            else:
                dialogue_text = phrase_text
                
            lines.append(f"Dialogue: 0,{phrase_start_str},{phrase_end_str},Default,,0,0,0,,{dialogue_text}")
    else:
        for phrase in phrases:
            phrase_words = [p["word"] for p in phrase]
            
            # Determine if any word in the phrase has an emoji
            phrase_emojis = []
            for word_info in phrase:
                w_emoji = find_emoji_for_word(word_info["word"], emoji_map) if emoji_position != "none" and emoji_map else ""
                phrase_emojis.append(w_emoji)
    
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
                        # Determine active_tags based on style
                        if animation_style == "bouncy_bounce":
                            active_tags = f"\\alpha&H00&\\c{ass_highlight}&\\fscx100\\fscy100\\t(0,80,\\fscx135\\fscy135)\\t(80,180,\\fscx100\\fscy100)"
                        elif animation_style == "cinematic_zoom":
                            active_tags = f"\\c{ass_highlight}&\\fscx70\\fscy70\\alpha&HAA&\\t(0,120,\\fscx100\\fscy100\\alpha&H00&)"
                        elif animation_style == "glow_shake":
                            active_tags = f"\\alpha&H00&\\c{ass_highlight}&\\frz-6\\t(0,100,\\frz6)\\t(100,200,\\frz0)"
                        elif animation_style == "neon_flicker":
                            active_tags = f"\\alpha&H00&\\c{ass_highlight}&\\t(0,50,\\3c{ass_highlight}&\\3a&H33&)\\t(50,150,\\3c{ass_outline}&\\3a&H00&)\\t(150,200,\\3c{ass_highlight}&\\3a&H33&)"
                        elif animation_style == "pulse_grow":
                            active_tags = f"\\alpha&H00&\\c{ass_highlight}&\\fscx100\\fscy100\\frz0\\t(0,70,\\fscx140\\fscy140\\frz-5)\\t(70,140,\\fscx95\\fscy95\\frz5)\\t(140,200,\\fscx105\\fscy105\\frz0)"
                        elif animation_style == "fade_in_slide":
                            active_tags = f"\\alpha&HFF&\\fscy60\\t(0,120,\\alpha&H00&\\fscy100)"
                        else:  # tiktok_pop
                            active_tags = "\\alpha&H00&"
                            if word_pop:
                                active_tags += f"\\fscx{scale_pct}\\fscy{scale_pct}"
                            active_tags += f"\\c{ass_highlight}&"
                            
                        w_text = w
                        if emoji_position == "same_line" and phrase_emojis[idx]:
                            wrapped_emoji = f"{{\\fn{emoji_font}}}{phrase_emojis[idx]}{{\\fn}}"
                            w_text = f"{wrapped_emoji} {w_text}"
                        text_parts.append(f"{{{active_tags}}}{w_text}{{\\r}}")
                    else:
                        # Inactive word: dim if enabled
                        if inactive_dim:
                            text_parts.append(f"{{\\alpha&H{inactive_alpha}&}}{w}{{\\r}}")
                        else:
                            text_parts.append(w)
                
                phrase_text = " ".join(text_parts)
                
                if emoji_position == "above" and phrase_emojis[idx]:
                    emoji_top = f"{{\\fn{emoji_font}}}{phrase_emojis[idx]}{{\\fn}}"
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
    render_preset: str = 'fast',
    render_resolution: str = '1080p',
    video_encoder: str = 'libx265',
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
    bg_video_path = os.path.abspath(bg_video_path)
    input_args_top = {"stream_loop": -1}
    if start_offset_top > 0.0:
        input_args_top["ss"] = f"{start_offset_top:.2f}"
    
    top_video_in = ffmpeg.input(bg_video_path, **input_args_top).video

    target_w = 1080 if render_resolution == '1080p' else 720
    target_h = 1920 if render_resolution == '1080p' else 1280

    if is_split:
        bg_video_bottom_path = os.path.abspath(bg_video_bottom_path)
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

    # Apply subtitles to the video stream (look for fonts in the fonts folder)
    fonts_dir = os.path.join(BASE_DIR, "fonts")
    os.makedirs(fonts_dir, exist_ok=True)
    v_stream = v_stream.filter('subtitles', filename=os.path.abspath(subs_path), fontsdir=fonts_dir)

    # Add smooth transitions: Video Fade-in / Fade-out (0.5s duration)
    v_stream = v_stream.filter('fade', type='in', start_time=0, duration=0.5)
    v_stream = v_stream.filter('fade', type='out', start_time=max(0, audio_duration - 0.5), duration=0.5)

    # 3. Audio Streams Setup
    audio_path = os.path.abspath(audio_path)
    voice_audio = ffmpeg.input(audio_path).audio.filter('volume', voice_volume)

    has_music = music_path and os.path.exists(music_path)
    if has_music:
        music_path = os.path.abspath(music_path)
        music_audio = ffmpeg.input(music_path, stream_loop=-1).audio.filter('volume', music_volume)
        
        # Mix voice and music
        a_stream = ffmpeg.filter([voice_audio, music_audio], 'amix', inputs=2, duration='first', dropout_transition=0)
    else:
        a_stream = voice_audio

    output_path = os.path.abspath(output_path)
    # 4. output node
    output_args = {
        'vcodec': video_encoder,
        'acodec': 'aac',
        'audio_bitrate': '192k',
        'pix_fmt': 'yuv420p',
        'r': 60,
        't': f"{audio_duration:.2f}"
    }
    
    if '265' in video_encoder or 'hevc' in video_encoder:
        output_args['profile:v'] = 'main'
        output_args['tag:v'] = 'hvc1'
    else:
        output_args['profile:v'] = 'high'
        output_args['level:v'] = '5.1'

    # Handle encoder-specific options
    is_hw_encoder = any(video_encoder.endswith(suffix) for suffix in ['_amf', '_nvenc', '_qsv', '_videotoolbox'])
    
    if is_hw_encoder:
        if 'amf' in video_encoder:
            # AMD AMF options (speed, balanced, quality)
            if render_preset in ['ultrafast', 'superfast', 'veryfast', 'faster']:
                output_args['preset'] = 'speed'
            elif render_preset in ['fast']:
                output_args['preset'] = 'balanced'
            else:
                output_args['preset'] = 'quality'
        elif 'nvenc' in video_encoder:
            # NVIDIA NVENC options
            if render_preset in ['ultrafast', 'superfast']:
                output_args['preset'] = 'p1'
            elif render_preset in ['veryfast', 'faster']:
                output_args['preset'] = 'p3'
            elif render_preset in ['fast']:
                output_args['preset'] = 'p4'
            else:
                output_args['preset'] = 'p7'
        else:
            # For other hardware encoders, let's pass a generic preset or none
            pass
        # Do not include crf for HW encoders (they don't support it)
    else:
        # Standard software encoder (e.g. libx264, libx265)
        output_args['preset'] = render_preset
        if video_encoder == 'libx265':
            output_args['crf'] = 28
        else:
            output_args['crf'] = 23

    # Allow FFmpeg to use optimal number of threads based on available cores
    output_args['threads'] = 0

    out = ffmpeg.output(
        v_stream,
        a_stream,
        output_path,
        **output_args
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

