import asyncio
import os
import subprocess
import uuid

from gui.config import TEMP_DIR, logger
from gui.emoji_renderer import render_emoji_pngs_batch
from gui.emoji_sprite import render_emoji_sprite
from generator.subtitles import generate_ass_subtitles


async def create_animation_preview(settings: dict, test_word: str, emoji_char: str) -> str:
    """
    Generate a short 3-second WebM preview of the subtitle and emoji animation.
    Returns the absolute path to the generated WebM file.
    """
    os.makedirs(TEMP_DIR, exist_ok=True)
    uid = uuid.uuid4().hex[:8]
    output_webm = os.path.join(TEMP_DIR, f"preview_{uid}.webm")
    output_ass = os.path.join(TEMP_DIR, f"preview_{uid}.ass")
    output_mkv = os.path.join(TEMP_DIR, f"preview_{uid}.mkv")

    # 1. Prepare word timing data
    words = [
        {"word": test_word, "start": 0.5, "end": 2.0}
    ]
    emoji_map = {test_word: emoji_char} if emoji_char else {}

    # 2. Generate ASS subtitles
    generate_ass_subtitles(words, output_ass, style_opts=settings, emoji_map=emoji_map)

    # 3. Handle emojis if enabled
    enable_emojis = settings.get("enable_emojis", True)
    emoji_position = settings.get("emoji_position", "above")
    
    emoji_sprite_path = ""
    if enable_emojis and emoji_position != "none" and emoji_char:
        # We need to extract the emoji overlays generated inside generate_ass_subtitles
        # But wait! generate_ass_subtitles only generates the .ass file and DOES NOT return the overlays.
        # However, generate_ass_subtitles is just for the ASS.
        # To get the emoji overlays, we need to manually call _make_emoji_overlay or reimplement it?
        # Let's mock it for the preview.
        
        emoji_style = settings.get("emoji_style", "Symbola")
        emoji_png_cache = await render_emoji_pngs_batch({emoji_char}, 128, style=emoji_style)
        
        # We just place a single emoji overlay for the preview
        font_size = int(settings.get("sub_size", 72))
        scale_factor = float(settings.get("emoji_scale_factor", 1.5))
        size = max(1, int(font_size * scale_factor))
        target_h = 1920
        target_w = 1080
        margin_v = 350
        
        if emoji_position == "above":
            base_y = margin_v + 50
        else:
            base_y = max(size // 2, (target_h // 2) - margin_v)
            
        pos_x = target_w // 2

        throw_speed_mult = float(settings.get("emoji_throw_speed_multiplier", 1.0))
        throw_arc_height = float(settings.get("emoji_throw_arc_height", 25.0))
        throw_fall_distance = float(settings.get("emoji_throw_fall_distance", 153.6))
        spin_speed = float(settings.get("emoji_spin_speed", 45.0))
        
        emoji_overlays = [{
            "emoji": emoji_char,
            "x": pos_x,
            "y": base_y,
            "size": size,
            "start": 0.5,
            "end": 2.5,
            "anim": "throw" if settings.get("enable_emoji_animation", True) else "none",
            "throw_speed_mult": throw_speed_mult,
            "throw_arc_height": throw_arc_height,
            "throw_fall_distance": throw_fall_distance,
            "spin_speed": spin_speed,
        }]
        
        sprite_path = os.path.join(TEMP_DIR, f"emoji_sprite_{uid}.mkv")
        render_emoji_sprite(emoji_overlays, emoji_png_cache, target_w, target_h, 30, 3.0, sprite_path)
        emoji_sprite_path = sprite_path

    # 4. Use FFmpeg to composite the ASS subtitles (and optional emoji sprite) onto a transparent WebM
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black@0.0:s=1080x1920:d=3.0,format=rgba",
    ]
    
    if emoji_sprite_path and os.path.exists(emoji_sprite_path):
        cmd.extend(["-i", emoji_sprite_path])
        filter_complex = f"[0:v][1:v]overlay=format=auto[v1];[v1]ass='{output_ass}':alpha=1[v_out]"
    else:
        filter_complex = f"[0:v]ass='{output_ass}':alpha=1[v_out]"

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[v_out]",
        "-c:v", "libvpx-vp9",
        "-pix_fmt", "yuva420p",
        "-auto-alt-ref", "0",
        "-b:v", "1M",
        output_webm
    ])
    
    logger.info(f"Rendering preview: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, capture_output=True)
    
    if emoji_sprite_path and os.path.exists(emoji_sprite_path):
        os.remove(emoji_sprite_path)
        
    return output_webm
