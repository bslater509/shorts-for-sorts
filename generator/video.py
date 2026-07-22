import contextlib
import json
import logging
import os
import random
import re
import subprocess
import time
import uuid

import ffmpeg

logger = logging.getLogger("shorts_creator.generator")
if not logger.handlers and not logging.getLogger("shorts_creator").handlers:
    logger.addHandler(logging.NullHandler())

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_video_info(video_path: str, suppress_errors: bool = False) -> dict:
    """
    Queries ffprobe for video width, height, and duration.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found at: {video_path}")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration",
        "-of",
        "json",
        video_path,
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
        if suppress_errors:
            return {"width": 0, "height": 0, "duration": 0.0}
        raise RuntimeError(err_msg) from e
    except Exception as e:
        if not suppress_errors:
            logger.error(
                f"An unexpected error occurred while running ffprobe on '{video_path}': {e}",
                exc_info=True,
            )
        if suppress_errors:
            return {"width": 0, "height": 0, "duration": 0.0}
        raise RuntimeError(
            f"An unexpected error occurred while running ffprobe on '{video_path}': {e}"
        ) from e

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        if suppress_errors:
            return {"width": 0, "height": 0, "duration": 0.0}
        raise RuntimeError(
            f"Failed to parse JSON output from ffprobe for '{video_path}': {e}"
        ) from e

    if "streams" in info and len(info["streams"]) > 0:
        stream = info["streams"][0]
        try:
            return {
                "width": int(stream.get("width", 0)),
                "height": int(stream.get("height", 0)),
                "duration": float(stream.get("duration") or 0.0),
            }
        except (ValueError, TypeError) as e:
            if suppress_errors:
                return {"width": 0, "height": 0, "duration": 0.0}
            raise RuntimeError(f"Invalid stream format metadata in video file '{video_path}': {e}") from e
    return {"width": 0, "height": 0, "duration": 0.0}


def compile_video(
    bg_video_path: str,
    audio_path: str,
    subs_path: str,
    output_path: str,
    audio_duration: float,
    music_path: str | None = None,
    voice_volume: float = 1.0,
    music_volume: float = 0.15,
    bg_video_bottom_path: str | None = None,
    render_preset: str = "fast",
    render_resolution: str = "720p",
    video_encoder: str = "libx264",
    progress_callback=None,
    emoji_overlay_path: str | None = None,
    emoji_style: str = "apple",
):
    """
    Renders the final vertical video using FFmpeg.
    If bg_video_bottom_path is provided, crops both top and bottom videos to 9:8
    and stacks them (split screen).
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
        logger.info("Top bg offset: %.2f / %.2fs", start_offset_top, bg_top_duration)

    is_split = bg_video_bottom_path is not None and os.path.exists(bg_video_bottom_path)

    start_offset_bottom = 0.0
    if is_split:
        assert bg_video_bottom_path is not None
        # Get bottom video details
        info_bottom = get_video_info(bg_video_bottom_path)
        w_bottom = info_bottom["width"]
        h_bottom = info_bottom["height"]
        bg_bottom_duration = info_bottom.get("duration", 0.0)

        if w_bottom == 0 or h_bottom == 0:
            raise ValueError(f"Could not retrieve video dimensions for {bg_video_bottom_path}")
        if bg_bottom_duration > audio_duration:
            start_offset_bottom = random.uniform(0.0, bg_bottom_duration - audio_duration)
            logger.info("Bottom bg offset: %.2f / %.2fs", start_offset_bottom, bg_bottom_duration)

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
    subs_dir = os.path.dirname(subs_path)

    # 2. Build input streams
    bg_video_path = os.path.abspath(bg_video_path)
    input_args_top: dict[str, object] = {"stream_loop": -1}
    if start_offset_top > 0.0:
        input_args_top["ss"] = f"{start_offset_top:.2f}"

    top_video_in = ffmpeg.input(bg_video_path, **input_args_top).video

    target_w = 1080 if render_resolution == "1080p" else 720
    target_h = 1920 if render_resolution == "1080p" else 1280

    if is_split:
        bg_video_bottom_path = os.path.abspath(bg_video_bottom_path)  # type: ignore[arg-type]
        input_args_bottom: dict[str, object] = {"stream_loop": -1}
        if start_offset_bottom > 0.0:
            input_args_bottom["ss"] = f"{start_offset_bottom:.2f}"
        bottom_video_in = ffmpeg.input(bg_video_bottom_path, **input_args_bottom).video

        top_v = top_video_in.filter(
            "crop", crop_w_top, crop_h_top, offset_x_top, offset_y_top
        ).filter("scale", target_w, target_h // 2)
        bottom_v = bottom_video_in.filter(
            "crop", crop_w_bottom, crop_h_bottom, offset_x_bottom, offset_y_bottom
        ).filter("scale", target_w, target_h // 2)
        v_stream = ffmpeg.filter([top_v, bottom_v], "vstack")
    else:
        v_stream = top_video_in.filter("crop", crop_w, crop_h, offset_x, offset_y).filter(
            "scale", target_w, target_h
        )

    # Apply subtitles to the video stream (look for fonts in the fonts folder)
    fonts_dir = os.path.join(BASE_DIR, "fonts")
    os.makedirs(fonts_dir, exist_ok=True)
    v_stream = v_stream.filter("subtitles", filename=os.path.abspath(subs_path), fontsdir=fonts_dir)

    # Apply color emoji overlays if manifest provided
    _temp_cleanup = []
    if emoji_overlay_path and not os.path.exists(emoji_overlay_path):
        logger.warning(
            "Emoji overlay manifest not found at %s — skipping color emoji", emoji_overlay_path
        )
        emoji_overlay_path = None
    if emoji_overlay_path:
        try:
            with open(emoji_overlay_path) as ef:
                emoji_overlays = json.load(ef)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read emoji overlay manifest %s: %s", emoji_overlay_path, e)
            emoji_overlays = []
        if emoji_overlays:
            logger.info(
                "Processing %d emoji overlays from manifest: %s",
                len(emoji_overlays),
                os.path.basename(emoji_overlay_path),
            )
            if progress_callback:
                progress_callback("Rendering emoji sprites...")

            # Render unique emojis in a single Playwright browser session
            import asyncio as _asyncio

            from gui.emoji_renderer import evict_stale_emoji_cache, render_emoji_pngs_batch

            evict_stale_emoji_cache()
            unique_emojis = {e["emoji"] for e in emoji_overlays}
            logger.info(
                "Rendering %d unique emojis to PNG via batch Playwright", len(unique_emojis)
            )
            emoji_png_cache = _asyncio.run(
                render_emoji_pngs_batch(unique_emojis, 128, style=emoji_style, progress_callback=progress_callback)
            )

            cache_hits = sum(1 for v in emoji_png_cache.values() if v)
            cache_misses = len(unique_emojis) - cache_hits
            if cache_misses > 0:
                logger.warning(
                    "Emoji PNG rendering: %d/%d cached, %d failed",
                    cache_hits,
                    len(unique_emojis),
                    cache_misses,
                )
            else:
                logger.info("Emoji PNG rendering: all %d emojis cached successfully", cache_hits)

            # Render a single composited sprite video instead of per-instance overlays
            from gui.emoji_sprite import render_emoji_sprite

            sprite_path = os.path.join(BASE_DIR, "temp", f"emoji_sprite_{uuid.uuid4().hex[:8]}.mkv")
            os.makedirs(os.path.join(BASE_DIR, "temp"), exist_ok=True)
            _temp_cleanup.append(sprite_path)
            sprite_result = render_emoji_sprite(
                emoji_overlays,
                emoji_png_cache,
                target_w,
                target_h,
                30,
                audio_duration,
                sprite_path,
                progress_callback=progress_callback,
            )
            if sprite_result:
                sprite_input = ffmpeg.input(sprite_result)
                v_stream = v_stream.overlay(sprite_input, x="0", y="0")
                logger.info(
                    "Color emoji sprite applied to video stream: %s",
                    os.path.basename(sprite_result),
                )
                if progress_callback:
                    progress_callback("Emoji overlay applied")
            else:
                logger.warning(
                    "Color emoji overlay failed — falling back to text emoji in subtitles"
                )
                if progress_callback:
                    progress_callback("⚠ Emoji overlay failed — using text fallback")

    # Add smooth transitions: Video Fade-in / Fade-out (0.5s duration)
    v_stream = v_stream.filter("fade", type="in", start_time=0, duration=0.5)
    v_stream = v_stream.filter(
        "fade", type="out", start_time=max(0, audio_duration - 0.5), duration=0.5
    )

    # 3. Audio Streams Setup
    audio_path = os.path.abspath(audio_path)
    voice_audio = ffmpeg.input(audio_path).audio.filter("volume", voice_volume)

    has_music = music_path is not None and os.path.exists(music_path)
    if has_music:
        music_path = os.path.abspath(music_path)  # type: ignore[arg-type]
        music_audio = ffmpeg.input(music_path, stream_loop=-1).audio.filter("volume", music_volume)

        # Mix voice and music
        a_stream = ffmpeg.filter(
            [voice_audio, music_audio], "amix", inputs=2, duration="first", dropout_transition=0
        )
    else:
        a_stream = voice_audio

    output_path = os.path.abspath(output_path)
    # 4. output node
    output_args = {
        "vcodec": video_encoder,
        "acodec": "aac",
        "audio_bitrate": "192k",
        "pix_fmt": "yuv420p",
        "r": 30,
        "t": f"{audio_duration:.2f}",
    }

    if "265" in video_encoder or "hevc" in video_encoder:
        output_args["profile:v"] = "main"
        output_args["tag:v"] = "hvc1"
    else:
        output_args["profile:v"] = "high"

    # Handle encoder-specific options
    is_hw_encoder = any(
        video_encoder.endswith(suffix) for suffix in ["_amf", "_nvenc", "_qsv", "_videotoolbox"]
    )

    if is_hw_encoder:
        if "amf" in video_encoder:
            if render_preset in ["ultrafast", "superfast", "veryfast", "faster"]:
                output_args["preset"] = "speed"
            elif render_preset in ["fast"]:
                output_args["preset"] = "balanced"
            else:
                output_args["preset"] = "quality"
        elif "nvenc" in video_encoder:
            if render_preset in ["ultrafast", "superfast"]:
                output_args["preset"] = "p1"
            elif render_preset in ["veryfast", "faster"]:
                output_args["preset"] = "p3"
            elif render_preset in ["fast"]:
                output_args["preset"] = "p4"
            else:
                output_args["preset"] = "p7"
        # Do not include crf for HW encoders (they don't support it)
    else:
        output_args["preset"] = render_preset
        if video_encoder == "libx265":
            output_args["crf"] = 28
        else:
            output_args["crf"] = 23

    output_args["threads"] = os.cpu_count() or 2

    out = ffmpeg.output(v_stream, a_stream, output_path, **output_args)

    # Compile ffmpeg-python stream spec to command line arguments list
    cmd = ffmpeg.compile(out, overwrite_output=True)

    # Run FFmpeg inside the folder where subtitles are stored so that relative path works flawlessly
    cwd = subs_dir if subs_dir else None

    stderr_lines = []
    return_code = -1
    try:
        import select

        # Safety timeout: 3x audio duration or 30 minutes, whichever is larger
        _ffmpeg_timeout = max(audio_duration * 3.0, 1800.0)
        _ffmpeg_deadline = time.monotonic() + _ffmpeg_timeout

        _popen_kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.PIPE,
            "text": True,
            "cwd": cwd,
            "bufsize": 1,
            "encoding": "utf-8",
            "errors": "replace",
        }

        with subprocess.Popen(cmd, **_popen_kwargs) as process:
            while True:
                remaining = _ffmpeg_deadline - time.monotonic()
                if remaining <= 0:
                    logger.error(f"FFmpeg timeout after {_ffmpeg_timeout:.0f}s — killing process")
                    process.kill()
                    process.wait()
                    raise RuntimeError(
                        f"FFmpeg killed after {_ffmpeg_timeout:.0f}s timeout "
                        f"(audio_duration={audio_duration:.1f}s)"
                    )
                r, _, _ = select.select([process.stderr], [], [], max(0.1, min(remaining, 5.0)))
                if not r:
                    continue
                try:
                    line = process.stderr.readline()
                except Exception:
                    break
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
                                with contextlib.suppress(Exception):
                                    progress_callback(pct)
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
                                    with contextlib.suppress(Exception):
                                        progress_callback(pct)
            process.wait()
            return_code = process.returncode
    except Exception as e:
        logger.error(
            f"Failed to execute FFmpeg command compiled via ffmpeg-python: {e}", exc_info=True
        )
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

    # Clean up temp sprite files after successful or failed compilation
    for cleanup_path in _temp_cleanup:
        with contextlib.suppress(OSError):
            if os.path.exists(cleanup_path):
                os.remove(cleanup_path)
