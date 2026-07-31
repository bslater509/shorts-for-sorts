"""Video compilation and inspection using FFmpeg.

Provides functions to probe video metadata with ffprobe and to render
final vertical-format shorts videos with background looping, voiceover
audio, background music, subtitle burning, and split-screen support.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import random
import re
import select
import subprocess
import time
from typing import Any, Protocol

import ffmpeg

# --- Logger ---

logger: logging.Logger = logging.getLogger("shorts_creator.generator")
if not logger.handlers and not logging.getLogger("shorts_creator").handlers:
    logger.addHandler(logging.NullHandler())

# --- Paths ---

BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Aspect ratios ---

ASPECT_RATIO_9_16: float = 9.0 / 16.0
"""Standard vertical video aspect ratio for single-screen mode."""

ASPECT_RATIO_9_8: float = 1.125
"""Aspect ratio for each half of a split-screen layout (9:8)."""

# --- Video rendering constants ---

FADE_DURATION: float = 0.5
"""Duration in seconds for video fade-in and fade-out transitions."""

FRAME_RATE: int = 30
"""Output video frame rate."""

AUDIO_CODEC: str = "aac"
"""Audio codec used in the output."""

AUDIO_BITRATE: str = "192k"
"""Audio bitrate for the output."""

PIX_FMT: str = "yuv420p"
"""Pixel format for broad compatibility."""

# CRF (Constant Rate Factor) quality values
CRF_H264: int = 23
"""Default CRF for H.264 encoding (lower = better quality)."""
CRF_H265: int = 28
"""Default CRF for H.265/HEVC encoding."""

# Resolution presets: mapping from preset name to (width, height)
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "720p": (720, 1280),
    "1080p": (1080, 1920),
}

# FFmpeg timeout safety limits
TIMEOUT_MULTIPLIER: float = 3.0
"""Safety timeout = audio_duration × this multiplier (minimum
:data:`MIN_TIMEOUT_SECONDS`)."""

MIN_TIMEOUT_SECONDS: float = 1800.0
"""Minimum safety timeout in seconds (30 minutes)."""

# FFmpeg select polling interval
POLL_INTERVAL_SECONDS: float = 5.0
"""Maximum interval in seconds for polling FFmpeg stderr during render."""
MIN_POLL_INTERVAL_SECONDS: float = 0.1
"""Minimum poll interval."""

# Progress regex: matches "time=HH:MM:SS.cs" or "time=HH:MM:SS"
TIME_PROGRESS_RE: re.Pattern = re.compile(
    r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})"
)
TIME_PROGRESS_NO_CS_RE: re.Pattern = re.compile(
    r"time=(\d{2}):(\d{2}):(\d{2})"
)

# HW encoder suffixes
HW_ENCODER_SUFFIXES: tuple[str, ...] = ("_amf", "_nvenc", "_qsv", "_videotoolbox")

# Preset mappings for hardware encoders
AMF_PRESET_MAP: dict[str, str] = {
    "ultrafast": "speed",
    "superfast": "speed",
    "veryfast": "speed",
    "faster": "speed",
    "fast": "balanced",
}
AMF_PRESET_DEFAULT: str = "quality"

NVENC_PRESET_MAP: dict[str, str] = {
    "ultrafast": "p1",
    "superfast": "p1",
    "veryfast": "p3",
    "faster": "p3",
    "fast": "p4",
}
NVENC_PRESET_DEFAULT: str = "p7"

# Crop-dimension evenness constraint
CROP_EVEN_MASK: int = -2
"""Bitmask applied to crop dimensions to ensure they are even
(required by many video codecs)."""


# --- Protocol for progress callbacks ---


class ProgressCallback(Protocol):
    """Protocol for rendering progress callbacks.

    Implementations receive a float in the range ``[0.0, 100.0]``
    indicating the estimated percentage of video compilation completed.
    """

    def __call__(self, percent: float) -> Any:
        ...


# --- Public functions ---


def get_video_info(
    video_path: str, suppress_errors: bool = False
) -> dict[str, Any]:
    """Query video metadata (width, height, duration) using ffprobe.

    Args:
        video_path: Path to the video file.
        suppress_errors: If ``True``, return a zeroed info dict on any
            failure instead of raising.

    Returns:
        Dictionary with keys ``"width"`` (int), ``"height"`` (int), and
        ``"duration"`` (float).  All values default to ``0`` / ``0.0`` on
        failure when ``suppress_errors`` is set.

    Raises:
        FileNotFoundError: If the video file does not exist.
        RuntimeError: If ffprobe fails or returns unparseable data (unless
            ``suppress_errors`` is ``True``).
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found at: {video_path}")

    cmd: list[str] = [
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

    _error_result: dict[str, Any] = {"width": 0, "height": 0, "duration": 0.0}

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        err_msg: str = (
            f"FFprobe failed to analyze video '{os.path.basename(video_path)}'. "
            f"The video file may be corrupt or in an unsupported format.\n"
            f"Command run: {' '.join(cmd)}\n"
            f"Error details: {e.stderr.strip()}"
        )
        if not suppress_errors:
            logger.error(err_msg, exc_info=True)
        if suppress_errors:
            return _error_result
        raise RuntimeError(err_msg) from e
    except Exception as e:
        if not suppress_errors:
            logger.error(
                "An unexpected error occurred while running ffprobe on "
                "'%s': %s",
                video_path,
                e,
                exc_info=True,
            )
        if suppress_errors:
            return _error_result
        raise RuntimeError(
            f"An unexpected error occurred while running ffprobe on "
            f"'{video_path}': {e}"
        ) from e

    try:
        info: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        if suppress_errors:
            return _error_result
        raise RuntimeError(
            f"Failed to parse JSON output from ffprobe for "
            f"'{video_path}': {e}"
        ) from e

    if "streams" in info and len(info["streams"]) > 0:
        stream: dict[str, Any] = info["streams"][0]
        try:
            return {
                "width": int(stream.get("width", 0)),
                "height": int(stream.get("height", 0)),
                "duration": float(stream.get("duration") or 0.0),
            }
        except (ValueError, TypeError) as e:
            if suppress_errors:
                return _error_result
            raise RuntimeError(
                f"Invalid stream format metadata in video file "
                f"'{video_path}': {e}"
            ) from e

    return _error_result


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
    progress_callback: ProgressCallback | None = None,
) -> None:
    """Render the final vertical-format video using FFmpeg.

    The function composes an FFmpeg command that:

    * Loops one or two background videos, cropped to the target aspect ratio.
    * Burns ASS subtitles onto the video.
    * Adds a voiceover audio track (with optional background music blended in).
    * Applies fade-in / fade-out transitions.
    * Optionally stacks two background videos in a split-screen layout.

    Args:
        bg_video_path: Path to the primary (top) background video.
        audio_path: Path to the voiceover audio file.
        subs_path: Path to the ASS subtitle file.
        output_path: Destination path for the rendered video.
        audio_duration: Duration of the audio track in seconds (used as
            the output video length).
        music_path: Optional path to background music.
        voice_volume: Volume multiplier for the voiceover (1.0 = normal).
        music_volume: Volume multiplier for background music
            (default 0.15 ≈ quiet background level).
        bg_video_bottom_path: Optional path to a second background video
            for split-screen layout.  Both videos are cropped to 9:8
            and stacked vertically.
        render_preset: FFmpeg encoder preset (e.g. ``"fast"``,
            ``"medium"``, ``"slow"``).  For hardware encoders this value
            is mapped to the closest equivalent.
        render_resolution: Output resolution preset (``"720p"`` or
            ``"1080p"``).
        video_encoder: FFmpeg video encoder name (e.g. ``"libx264"``,
            ``"libx265"``, ``"h264_nvenc"``).
        progress_callback: Optional callable receiving a ``float``
            percentage ``[0.0, 100.0]`` as rendering progresses.

    Raises:
        ValueError: If video dimensions cannot be determined.
        RuntimeError: If FFmpeg execution fails or times out.
    """
    # ------------------------------------------------------------------
    # 1. Analyse top background video
    # ------------------------------------------------------------------
    info_top: dict[str, Any] = get_video_info(bg_video_path)
    w_top: int = info_top["width"]
    h_top: int = info_top["height"]
    bg_top_duration: float = info_top.get("duration", 0.0)

    if w_top == 0 or h_top == 0:
        raise ValueError(
            f"Could not retrieve video dimensions for {bg_video_path}"
        )

    start_offset_top: float = 0.0
    if bg_top_duration > audio_duration:
        start_offset_top = random.uniform(0.0, bg_top_duration - audio_duration)
        logger.info("Top bg offset: %.2f / %.2fs", start_offset_top, bg_top_duration)

    # ------------------------------------------------------------------
    # 2. Determine single vs. split-screen layout
    # ------------------------------------------------------------------
    is_split: bool = (
        bg_video_bottom_path is not None and os.path.exists(bg_video_bottom_path)
    )

    start_offset_bottom: float = 0.0

    # Pre-declare crop variables so the type checker knows they are always assigned
    crop_top: tuple[int, int, int, int] | None = None
    crop_bottom: tuple[int, int, int, int] | None = None
    crop_single: tuple[int, int, int, int] | None = None

    if is_split:
        assert bg_video_bottom_path is not None  # narrowed by is_split
        info_bottom: dict[str, Any] = get_video_info(bg_video_bottom_path)
        w_bottom: int = info_bottom["width"]
        h_bottom: int = info_bottom["height"]
        bg_bottom_duration: float = info_bottom.get("duration", 0.0)

        if w_bottom == 0 or h_bottom == 0:
            raise ValueError(
                f"Could not retrieve video dimensions for {bg_video_bottom_path}"
            )
        if bg_bottom_duration > audio_duration:
            start_offset_bottom = random.uniform(
                0.0, bg_bottom_duration - audio_duration
            )
            logger.info(
                "Bottom bg offset: %.2f / %.2fs",
                start_offset_bottom,
                bg_bottom_duration,
            )

        crop_top = _compute_crop_params(
            w_top, h_top, ASPECT_RATIO_9_8
        )
        crop_bottom = _compute_crop_params(
            w_bottom, h_bottom, ASPECT_RATIO_9_8
        )
    else:
        crop_single = _compute_crop_params(
            w_top, h_top, ASPECT_RATIO_9_16
        )

    # ------------------------------------------------------------------
    # 3. Build input streams
    # ------------------------------------------------------------------
    bg_video_path = os.path.abspath(bg_video_path)
    input_args_top: dict[str, object] = {"stream_loop": -1}
    if start_offset_top > 0.0:
        input_args_top["ss"] = f"{start_offset_top:.2f}"

    top_video_in = ffmpeg.input(bg_video_path, **input_args_top).video

    target_w, target_h = RESOLUTIONS.get(render_resolution, (720, 1280))

    if is_split:
        bg_video_bottom_path = os.path.abspath(bg_video_bottom_path)  # type: ignore[arg-type]
        input_args_bottom: dict[str, object] = {"stream_loop": -1}
        if start_offset_bottom > 0.0:
            input_args_bottom["ss"] = f"{start_offset_bottom:.2f}"
        bottom_video_in = ffmpeg.input(
            bg_video_bottom_path, **input_args_bottom
        ).video

        assert crop_top is not None and crop_bottom is not None
        crop_w_top, crop_h_top, offset_x_top, offset_y_top = crop_top
        crop_w_bottom, crop_h_bottom, offset_x_bottom, offset_y_bottom = crop_bottom

        top_v = (
            top_video_in.filter(
                "crop", crop_w_top, crop_h_top, offset_x_top, offset_y_top
            ).filter("scale", target_w, target_h // 2)
        )
        bottom_v = (
            bottom_video_in.filter(
                "crop",
                crop_w_bottom,
                crop_h_bottom,
                offset_x_bottom,
                offset_y_bottom,
            ).filter("scale", target_w, target_h // 2)
        )
        v_stream = ffmpeg.filter([top_v, bottom_v], "vstack")
    else:
        assert crop_single is not None
        crop_w, crop_h, offset_x, offset_y = crop_single
        v_stream = top_video_in.filter(
            "crop", crop_w, crop_h, offset_x, offset_y
        ).filter("scale", target_w, target_h)

    # ------------------------------------------------------------------
    # 4. Burn subtitles
    # ------------------------------------------------------------------
    subs_dir: str = os.path.dirname(subs_path)
    fonts_dir: str = os.path.join(BASE_DIR, "fonts")
    os.makedirs(fonts_dir, exist_ok=True)
    v_stream = v_stream.filter(
        "subtitles", filename=os.path.abspath(subs_path), fontsdir=fonts_dir
    )

    # ------------------------------------------------------------------
    # 5. Fade transitions
    # ------------------------------------------------------------------
    v_stream = v_stream.filter("fade", type="in", start_time=0, duration=FADE_DURATION)
    v_stream = v_stream.filter(
        "fade",
        type="out",
        start_time=max(0.0, audio_duration - FADE_DURATION),
        duration=FADE_DURATION,
    )

    # ------------------------------------------------------------------
    # 6. Audio streams
    # ------------------------------------------------------------------
    audio_path = os.path.abspath(audio_path)
    voice_audio = ffmpeg.input(audio_path).audio.filter("volume", voice_volume)

    has_music: bool = music_path is not None and os.path.exists(music_path)
    if has_music:
        assert music_path is not None
        music_path = os.path.abspath(music_path)
        music_audio = ffmpeg.input(music_path, stream_loop=-1).audio.filter(
            "volume", music_volume
        )
        a_stream = ffmpeg.filter(
            [voice_audio, music_audio],
            "amix",
            inputs=2,
            duration="first",
            dropout_transition=0,
        )
    else:
        a_stream = voice_audio

    # ------------------------------------------------------------------
    # 7. Build output arguments and run FFmpeg
    # ------------------------------------------------------------------
    output_path = os.path.abspath(output_path)
    output_args: dict[str, Any] = _build_ffmpeg_output_args(
        video_encoder=video_encoder,
        render_preset=render_preset,
        audio_duration=audio_duration,
    )

    out = ffmpeg.output(v_stream, a_stream, output_path, **output_args)
    cmd: list[str] = ffmpeg.compile(out, overwrite_output=True)

    _run_ffmpeg_with_progress(
        cmd=cmd,
        cwd=subs_dir or None,
        audio_duration=audio_duration,
        progress_callback=progress_callback,
    )


# --- Internal helpers ---


def _compute_crop_params(
    w: int, h: int, target_ratio: float
) -> tuple[int, int, int, int]:
    """Compute crop dimensions and offsets to achieve a target aspect ratio.

    The crop region is centred within the original frame, and both
    crop width and height are rounded down to the nearest even number
    (required by most video codecs).

    Args:
        w: Original video width in pixels.
        h: Original video height in pixels.
        target_ratio: Desired aspect ratio (width / height).

    Returns:
        Tuple ``(crop_w, crop_h, offset_x, offset_y)`` where:
            - ``crop_w``, ``crop_h`` are the cropped dimensions,
            - ``offset_x``, ``offset_y`` are the top-left corner of the
              crop region within the original frame.
    """
    current_ratio: float = float(w) / float(h)

    if current_ratio > target_ratio:
        # Wider than target: crop width
        crop_w: int = int(h * target_ratio) & CROP_EVEN_MASK
        crop_h: int = h
        offset_x: int = (w - crop_w) // 2
        offset_y: int = 0
    else:
        # Taller or equal: crop height
        crop_w = w
        crop_h = int(w / target_ratio) & CROP_EVEN_MASK
        offset_x = 0
        offset_y = (h - crop_h) // 2

    return (crop_w, crop_h, offset_x, offset_y)


def _build_ffmpeg_output_args(
    video_encoder: str,
    render_preset: str,
    audio_duration: float,
) -> dict[str, Any]:
    """Build the dictionary of FFmpeg output arguments for the compiled video.

    Handles encoder-specific settings (preset, profile, CRF, pixel format)
    for both software and hardware encoders.

    Args:
        video_encoder: FFmpeg video encoder name (e.g. ``"libx264"``,
            ``"h264_nvenc"``).
        render_preset: Encoder preset string (e.g. ``"fast"``).
        audio_duration: Duration of the output video in seconds (used for
            the ``t`` option).

    Returns:
        Dictionary suitable for ``**kwargs`` expansion into
        ``ffmpeg.output()``.
    """
    output_args: dict[str, Any] = {
        "vcodec": video_encoder,
        "acodec": AUDIO_CODEC,
        "audio_bitrate": AUDIO_BITRATE,
        "pix_fmt": PIX_FMT,
        "r": FRAME_RATE,
        "t": f"{audio_duration:.2f}",
    }

    # Profile: HEVC uses "main", others use "high"
    if "265" in video_encoder or "hevc" in video_encoder:
        output_args["profile:v"] = "main"
        output_args["tag:v"] = "hvc1"
    else:
        output_args["profile:v"] = "high"

    # Hardware encoder preset mapping
    is_hw_encoder: bool = any(
        video_encoder.endswith(suffix) for suffix in HW_ENCODER_SUFFIXES
    )

    if is_hw_encoder:
        if "amf" in video_encoder:
            output_args["preset"] = AMF_PRESET_MAP.get(
                render_preset, AMF_PRESET_DEFAULT
            )
        elif "nvenc" in video_encoder:
            output_args["preset"] = NVENC_PRESET_MAP.get(
                render_preset, NVENC_PRESET_DEFAULT
            )
        # Other HW encoders (qsv, videotoolbox) use their own default
    else:
        output_args["preset"] = render_preset
        output_args["crf"] = CRF_H265 if video_encoder == "libx265" else CRF_H264

    output_args["threads"] = os.cpu_count() or 2
    return output_args


def _run_ffmpeg_with_progress(
    cmd: list[str],
    cwd: str | None,
    audio_duration: float,
    progress_callback: ProgressCallback | None,
) -> None:
    """Execute an FFmpeg command with progress monitoring and timeout.

    Stderr is parsed for time progress lines; the optional callback is
    invoked with a percentage estimate.  A safety timeout of
    ``max(audio_duration × 3, 1800 s)`` is enforced.

    Args:
        cmd: FFmpeg command-line arguments list.
        cwd: Working directory for the subprocess (``None`` = inherit).
        audio_duration: Expected output duration in seconds.
        progress_callback: Optional callback for progress percentage.

    Raises:
        RuntimeError: If FFmpeg times out, crashes, or returns a non-zero
            exit code.
    """
    # Safety timeout: 3× audio duration or 30 minutes, whichever is larger
    ffmpeg_timeout: float = max(audio_duration * TIMEOUT_MULTIPLIER, MIN_TIMEOUT_SECONDS)
    ffmpeg_deadline: float = time.monotonic() + ffmpeg_timeout

    popen_kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
        "text": True,
        "cwd": cwd,
        "bufsize": 1,
        "encoding": "utf-8",
        "errors": "replace",
    }

    stderr_lines: list[str] = []
    return_code: int = -1

    try:
        with subprocess.Popen(cmd, **popen_kwargs) as process:
            while True:
                remaining: float = ffmpeg_deadline - time.monotonic()
                if remaining <= 0:
                    logger.error(
                        "FFmpeg timeout after %.0fs — killing process",
                        ffmpeg_timeout,
                    )
                    process.kill()
                    process.wait()
                    raise RuntimeError(
                        f"FFmpeg killed after {ffmpeg_timeout:.0f}s timeout "
                        f"(audio_duration={audio_duration:.1f}s)"
                    )

                rlist, _, _ = select.select(
                    [process.stderr],
                    [],
                    [],
                    max(MIN_POLL_INTERVAL_SECONDS, min(remaining, POLL_INTERVAL_SECONDS)),
                )
                if not rlist:
                    continue

                try:
                    line: str = process.stderr.readline()
                except Exception:
                    break
                if not line:
                    break
                stderr_lines.append(line)

                # Parse FFmpeg progress: "time=HH:MM:SS.cs"
                if "time=" in line:
                    _handle_ffmpeg_progress_line(
                        line, audio_duration, progress_callback
                    )

            process.wait()
            return_code = process.returncode

    except Exception as e:
        logger.error(
            "Failed to execute FFmpeg command compiled via ffmpeg-python: %s",
            e,
            exc_info=True,
        )
        raise RuntimeError(f"FFmpeg execution failed: {e}") from e

    if return_code != 0:
        full_stderr: str = "".join(stderr_lines)
        err_msg: str = (
            f"FFmpeg compilation failed with exit code {return_code}.\n"
            f"FFmpeg command: {' '.join(cmd)}\n"
            f"Error details: {full_stderr.strip()}"
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg)


def _handle_ffmpeg_progress_line(
    line: str,
    audio_duration: float,
    progress_callback: ProgressCallback | None,
) -> None:
    """Parse a single FFmpeg stderr log line for progress information.

    Looks for ``time=HH:MM:SS.cs`` or ``time=HH:MM:SS`` patterns and
    invokes the callback with an estimated completion percentage.

    Args:
        line: A line of FFmpeg stderr output.
        audio_duration: Expected output duration in seconds.
        progress_callback: Optional callback to invoke with the percentage.
    """
    match = TIME_PROGRESS_RE.search(line)
    if match:
        hours: int = int(match.group(1))
        minutes: int = int(match.group(2))
        seconds: int = int(match.group(3))
        centiseconds: int = int(match.group(4))
        elapsed: float = (
            hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
        )
    else:
        match_no_cs = TIME_PROGRESS_NO_CS_RE.search(line)
        if match_no_cs:
            hours = int(match_no_cs.group(1))
            minutes = int(match_no_cs.group(2))
            seconds = int(match_no_cs.group(3))
            elapsed = float(hours * 3600 + minutes * 60 + seconds)
        else:
            return  # No progress info in this line

    if audio_duration > 0 and progress_callback is not None:
        pct: float = min(100.0, (elapsed / audio_duration) * 100.0)
        with contextlib.suppress(Exception):
            progress_callback(pct)
