import os
import subprocess
import numpy as np
from PIL import Image


def render_emoji_sprite(
    emoji_overlays: list[dict],
    emoji_png_cache: dict[str, str],
    output_w: int,
    output_h: int,
    fps: int,
    duration: float,
    sprite_path: str,
) -> str:
    """Render all emoji instances into a single composited sprite video with alpha channel.

    Pre-loads and pre-scales emoji PNGs from cache, then pipes raw RGBA frames
    into FFmpeg to produce a video that can be overlaid onto the main composite
    as a single input. This replaces the old approach of adding 8+ separate
    FFmpeg overlay filters (which caused OOM on low-RAM systems).

    Args:
        emoji_overlays:  List of dicts with keys ``emoji``, ``x``, ``y``,
                         ``size``, ``start``, ``end``.
        emoji_png_cache: Dict mapping emoji character strings to their cached
                         PNG file paths (from ``gui.emoji_renderer``).
        output_w:        Width of the sprite video (e.g. 1080).
        output_h:        Height of the sprite video (e.g. 1920).
        fps:             Frame rate (should match the main composite).
        duration:        Total duration of the sprite video in seconds.
        sprite_path:     Output path for the generated sprite video file
                         (e.g. a temporary ``.mkv`` file).

    Returns:
        Absolute path to the generated sprite video, or an empty string on
        failure.
    """
    if not emoji_overlays or not emoji_png_cache:
        return ""

    total_frames = int(duration * fps)
    if total_frames <= 0:
        return ""

    # ------------------------------------------------------------------
    # 1. Pre-load and pre-scale emoji images
    # ------------------------------------------------------------------
    emoji_cache: dict[tuple[str, int], np.ndarray] = {}

    for overlay in emoji_overlays:
        emoji_char = overlay["emoji"]
        size = int(overlay.get("size", 128))
        key = (emoji_char, size)

        if key in emoji_cache:
            continue

        png_path = emoji_png_cache.get(emoji_char)
        if not png_path or not os.path.exists(png_path):
            continue

        try:
            img = Image.open(png_path).convert("RGBA")
            if img.size != (size, size):
                img = img.resize((size, size), Image.LANCZOS)
            emoji_cache[key] = np.asarray(img, dtype=np.uint8)
        except Exception:
            continue

    if not emoji_cache:
        return ""

    # ------------------------------------------------------------------
    # 2. Build frame-indexed lookup
    # ------------------------------------------------------------------
    # Pre-compute (emoji_array, x, y, w, h) for every overlay and attach it
    # to every frame in which it is active.
    frame_lookup: list[list[tuple[np.ndarray, int, int, int, int]]] = [
        [] for _ in range(total_frames)
    ]

    for overlay in emoji_overlays:
        emoji_char = overlay["emoji"]
        size = int(overlay.get("size", 128))
        key = (emoji_char, size)

        arr = emoji_cache.get(key)
        if arr is None:
            continue

        start_frame = int(overlay["start"] * fps)
        end_frame = min(int(overlay["end"] * fps) + 1, total_frames)

        x = overlay["x"] - size // 2
        y = overlay["y"] - size // 2
        h, w = arr.shape[:2]

        for frame_idx in range(start_frame, end_frame):
            frame_lookup[frame_idx].append((arr, x, y, w, h))

    # ------------------------------------------------------------------
    # 3. Encode sprite video by piping raw RGBA frames into FFmpeg
    # ------------------------------------------------------------------
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{output_w}x{output_h}",
        "-pix_fmt", "rgba",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx265",
        "-pix_fmt", "yuva420p",
        "-crf", "18",
        "-preset", "fast",
        "-tag:v", "hvc1",
        sprite_path,
    ]

    proc = None
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        # Reusable empty transparent frame
        empty_frame = np.zeros((output_h, output_w, 4), dtype=np.uint8)

        for frame_idx in range(total_frames):
            active = frame_lookup[frame_idx]

            if not active:
                proc.stdin.write(empty_frame.tobytes())
                continue

            # Start from a clean slate each frame
            frame = empty_frame.copy()

            for src_arr, x, y, w, h in active:
                # Clip to output bounds
                x0 = max(0, x)
                y0 = max(0, y)
                x1 = min(output_w, x + w)
                y1 = min(output_h, y + h)

                if x0 >= x1 or y0 >= y1:
                    continue

                src_x0 = x0 - x
                src_y0 = y0 - y
                src_view = src_arr[src_y0:src_y0 + y1 - y0,
                                   src_x0:src_x0 + x1 - x0]

                dst_view = frame[y0:y1, x0:x1]

                # Alpha-blend with float accuracy
                fg = src_view.astype(np.float32) / 255.0
                bg = dst_view.astype(np.float32) / 255.0
                alpha = fg[:, :, 3:4]

                blended_rgb = fg[:, :, :3] * alpha + bg[:, :, :3] * (1.0 - alpha)
                out_alpha = alpha + bg[:, :, 3:4] * (1.0 - alpha)

                dst_view[:] = np.concatenate(
                    [blended_rgb, out_alpha], axis=2
                ) * 255.0

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        proc.wait()

        if proc.returncode != 0:
            return ""

        return os.path.abspath(sprite_path)

    except (BrokenPipeError, OSError):
        return ""
    except Exception:
        return ""
    finally:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                proc.wait()
            except Exception:
                pass
