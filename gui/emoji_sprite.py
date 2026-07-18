import contextlib
import logging
import math
import os
import subprocess

import numpy as np
from PIL import Image

logger = logging.getLogger("shorts_creator.emoji_sprite")


def render_emoji_sprite(
    emoji_overlays: list[dict],
    emoji_png_cache: dict[str, str],
    output_w: int,
    output_h: int,
    fps: int,
    duration: float,
    sprite_path: str,
    progress_callback=None,
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
    if not emoji_overlays:
        logger.debug("Sprite: no emoji overlays to render")
        return ""
    if not emoji_png_cache:
        logger.warning(
            "Sprite: %d emoji overlays provided but no PNG cache — did Playwright emoji rendering fail?",
            len(emoji_overlays),
        )
        return ""

    total_frames = int(duration * fps)
    if total_frames <= 0:
        logger.warning(
            "Sprite: invalid duration %.2fs at %dfps = %d frames", duration, fps, total_frames
        )
        return ""

    unique_requested = len({o["emoji"] for o in emoji_overlays})
    logger.info(
        "Sprite: rendering %d overlays (%d unique emojis) across %d frames at %dx%d",
        len(emoji_overlays),
        unique_requested,
        total_frames,
        output_w,
        output_h,
    )

    # ------------------------------------------------------------------
    # 1. Pre-load and pre-scale emoji images
    # ------------------------------------------------------------------
    emoji_cache: dict[tuple[str, int], np.ndarray] = {}
    loaded = 0
    failed = 0

    for overlay in emoji_overlays:
        emoji_char = overlay["emoji"]
        size = int(overlay.get("size", 128))
        key = (emoji_char, size)

        if key in emoji_cache:
            continue

        png_path = emoji_png_cache.get(emoji_char)
        if not png_path:
            logger.warning("Sprite: no cache entry for emoji %r (size %d)", emoji_char, size)
            failed += 1
            continue
        if not os.path.exists(png_path):
            logger.warning("Sprite: cache file missing for emoji %r: %s", emoji_char, png_path)
            failed += 1
            continue

        try:
            img = Image.open(png_path).convert("RGBA")
            if img.size != (size, size):
                img = img.resize((size, size), Image.LANCZOS)
            emoji_cache[key] = np.asarray(img, dtype=np.uint8)
            loaded += 1
        except Exception:
            logger.warning(
                "Sprite: failed to load/process emoji PNG %r at %s",
                emoji_char,
                png_path,
                exc_info=True,
            )
            failed += 1
            continue

    logger.info("Sprite: loaded %d emoji PNGs, %d failed", loaded, failed)

    if not emoji_cache:
        logger.warning("Sprite: zero emoji PNGs could be loaded — color emoji overlay skipped")
        return ""

    # ------------------------------------------------------------------
    # 2. Build frame-indexed lookup
    # ------------------------------------------------------------------
    frame_lookup: list[list[tuple[np.ndarray, int, int, int, int, str, int, int, dict]]] = [
        [] for _ in range(total_frames)
    ]
    active_overlays_counted = 0

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

        anim = overlay.get("anim", "none")

        for frame_idx in range(start_frame, end_frame):
            frame_lookup[frame_idx].append((arr, x, y, w, h, anim, start_frame, end_frame, overlay))
            active_overlays_counted += 1

    frames_with_content = sum(1 for f in frame_lookup if f)
    logger.info(
        "Sprite: %d/%d frames have active overlays (%d total overlay-instances)",
        frames_with_content,
        total_frames,
        active_overlays_counted,
    )

    # ------------------------------------------------------------------
    # 3. Encode sprite video by piping raw RGBA frames into FFmpeg
    # ------------------------------------------------------------------
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-s",
        f"{output_w}x{output_h}",
        "-pix_fmt",
        "rgba",
        "-r",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "ffv1",
        "-pix_fmt",
        "yuva420p",
        "-level",
        "3",
        "-slicecrc",
        "1",
        sprite_path,
    ]
    logger.debug("Sprite: FFmpeg command: %s", " ".join(cmd))

    proc = None
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        # Reusable empty transparent frame
        empty_frame = np.zeros((output_h, output_w, 4), dtype=np.uint8)

        for frame_idx in range(total_frames):
            active = frame_lookup[frame_idx]

            if progress_callback and total_frames > 1:
                report_interval = max(1, total_frames // 20)
                if frame_idx % report_interval == 0:
                    pct = int((frame_idx / total_frames) * 100)
                    with contextlib.suppress(Exception):
                        progress_callback(f"Emoji Sprite ({pct}%)")

            if not active:
                proc.stdin.write(empty_frame.tobytes())
                continue

            # Start from a clean slate each frame
            frame = empty_frame.copy()

            for entry in active:
                src_arr, x, y, w, h, anim, start_frame, end_frame, overlay = entry

                # Compute elapsed time and progress for animation transforms
                elapsed = (frame_idx - start_frame) / fps
                anim_duration = (end_frame - start_frame) / fps
                progress = 0.0
                if anim_duration > 0:
                    progress = max(0.0, min(1.0, elapsed / anim_duration))

                # --- per-emoji animation transforms ---
                if anim == "pop_in":
                    pop_duration = float(overlay.get("pop_duration", 0.15))
                    if elapsed < pop_duration:
                        scale_factor = elapsed / pop_duration
                        scale_factor = max(0.01, scale_factor**0.5)
                    else:
                        scale_factor = 1.0
                    if scale_factor < 1.0:
                        new_w = max(1, int(w * scale_factor))
                        new_h = max(1, int(h * scale_factor))
                        scaled = np.array(
                            Image.fromarray(src_arr).resize((new_w, new_h), Image.LANCZOS)
                        )
                        src_arr = scaled
                        x = x + (w - new_w) // 2
                        y = y + (h - new_h) // 2
                        w, h = new_w, new_h

                elif anim == "bounce":
                    bounce_speed = float(overlay.get("bounce_speed", 8.0))
                    bounce_height = float(overlay.get("bounce_height", 15.0))
                    bounce_damping = float(overlay.get("bounce_damping", 0.5))
                    damping = max(0.0, 1.0 - progress * bounce_damping)
                    bounce_offset = int(math.sin(elapsed * bounce_speed) * bounce_height * damping)
                    y = y + bounce_offset

                elif anim == "float_up":
                    float_distance = float(overlay.get("float_distance", 40.0))
                    float_offset = int(progress * float_distance)
                    y = y - float_offset

                elif anim == "fade":
                    fade_in_end = float(overlay.get("fade_in", 0.15))
                    fade_out_start = float(overlay.get("fade_out", 0.75))
                    if progress < fade_in_end:
                        alpha_mult = progress / fade_in_end
                    elif progress > fade_out_start:
                        fade_range = 1.0 - fade_out_start
                        alpha_mult = (1.0 - progress) / fade_range
                    else:
                        alpha_mult = 1.0
                    if alpha_mult < 1.0:
                        src_arr = src_arr.copy().astype(np.float32)
                        src_arr[:, :, 3] *= alpha_mult
                        src_arr = src_arr.astype(np.uint8)

                elif anim == "shake":
                    shake_intensity = float(overlay.get("shake_intensity", 5.0))
                    seed = hash((frame_idx, x, y))
                    jitter_x = int((seed % 11) - 5)
                    jitter_y = int(((seed // 13) % 7) - 3)
                    x = x + int(jitter_x * shake_intensity / 5.0)
                    y = y + int(jitter_y * shake_intensity / 5.0 * 0.6)

                elif anim == "spin":
                    spin_speed = float(overlay.get("spin_speed", 360.0))
                    angle = (elapsed * spin_speed) % 360
                    if angle > 0.5:
                        rad = math.radians(angle)
                        cos_a, sin_a = abs(math.cos(rad)), abs(math.sin(rad))
                        new_w = max(1, int(w * cos_a + h * sin_a))
                        new_h = max(1, int(w * sin_a + h * cos_a))
                        rotated = np.array(
                            Image.fromarray(src_arr).rotate(
                                angle, expand=True, resample=Image.BICUBIC
                            )
                        )
                        rh, rw = rotated.shape[:2]
                        src_arr = rotated
                        x = x + (w - rw) // 2
                        y = y + (h - rh) // 2
                        w, h = rw, rh

                elif anim == "wobble":
                    wobble_speed = float(overlay.get("wobble_speed", 12.0))
                    wobble_amount = float(overlay.get("wobble_amount", 15.0))
                    tilt = int(math.sin(elapsed * wobble_speed) * wobble_amount)
                    rotated = np.array(
                        Image.fromarray(src_arr).rotate(tilt, expand=False, resample=Image.BICUBIC)
                    )
                    rh, rw = rotated.shape[:2]
                    src_arr = rotated
                    x = x + (w - rw) // 2
                    y = y + (h - rh) // 2
                    w, h = rw, rh

                elif anim == "pulse":
                    pulse_speed = float(overlay.get("pulse_speed", 6.0))
                    pulse_amount = float(overlay.get("pulse_amount", 0.3))
                    pulse_scale = 1.0 + math.sin(elapsed * pulse_speed) * pulse_amount
                    new_w = max(1, int(w * pulse_scale))
                    new_h = max(1, int(h * pulse_scale))
                    scaled = np.array(
                        Image.fromarray(src_arr).resize((new_w, new_h), Image.LANCZOS)
                    )
                    src_arr = scaled
                    x = x + (w - new_w) // 2
                    y = y + (h - new_h) // 2
                    w, h = new_w, new_h

                elif anim == "throw":
                    # "Thrown" animation: emoji flies in from the side on an arc,
                    # falls toward the bottom, and tumbles like a thrown object.
                    emoji_char = overlay.get("emoji", "")
                    # Deterministic random left/right per emoji instance
                    throw_from_right = (
                        hash(
                            (
                                emoji_char,
                                str(int(overlay.get("x", 0))),
                                str(int(overlay.get("y", 0))),
                            )
                        )
                        % 2
                        == 0
                    )
                    arc_height = float(overlay.get("throw_arc_height", 25.0))
                    fall_distance = float(overlay.get("throw_fall_distance", output_h * 0.08))
                    spin_speed_val = float(overlay.get("spin_speed", 45.0))
                    speed_mult = float(overlay.get("throw_speed_mult", 1.0))

                    p = min(1.0, progress * speed_mult)

                    # --- Horizontal: Hermite smoothstep ease-in-out (accelerates in from speed 0) ---
                    eased_h = p * p * (3 - 2 * p)
                    margin = w * 3
                    if throw_from_right:
                        start_x = output_w + margin
                        travel = -(output_w + margin * 2)
                    else:
                        start_x = -margin
                        travel = output_w + margin * 2
                    new_x = int(start_x + travel * eased_h)

                    # --- Vertical: descend from apex (cosine quarter-wave) + gravity fall toward bottom ---
                    arc_offset = -arc_height * math.cos(p * math.pi / 2)
                    gravity_offset = fall_distance * (p**2)
                    new_y = int(y + arc_offset + gravity_offset)

                    # --- Tumbling rotation ---
                    angle = (elapsed * spin_speed_val) % 360
                    if angle > 0.5:
                        rad_throw = math.radians(angle)
                        cos_a, sin_a = abs(math.cos(rad_throw)), abs(math.sin(rad_throw))
                        new_w = max(1, int(w * cos_a + h * sin_a))
                        new_h = max(1, int(w * sin_a + h * cos_a))
                        rotated = np.array(
                            Image.fromarray(src_arr).rotate(
                                angle, expand=True, resample=Image.BICUBIC
                            )
                        )
                        rh, rw = rotated.shape[:2]
                        src_arr = rotated
                        x = new_x + (w - rw) // 2
                        y = new_y + (h - rh) // 2
                        w, h = rw, rh
                    else:
                        x = new_x
                        y = new_y

                # Clip to output bounds
                x0 = max(0, x)
                y0 = max(0, y)
                x1 = min(output_w, x + w)
                y1 = min(output_h, y + h)

                if x0 >= x1 or y0 >= y1:
                    continue

                src_x0 = x0 - x
                src_y0 = y0 - y
                src_view = src_arr[src_y0 : src_y0 + y1 - y0, src_x0 : src_x0 + x1 - x0]

                dst_view = frame[y0:y1, x0:x1]

                # Alpha-blend with float accuracy
                fg = src_view.astype(np.float32) / 255.0
                bg = dst_view.astype(np.float32) / 255.0
                alpha = fg[:, :, 3:4]

                blended_rgb = fg[:, :, :3] * alpha + bg[:, :, :3] * (1.0 - alpha)
                out_alpha = alpha + bg[:, :, 3:4] * (1.0 - alpha)

                dst_view[:] = np.concatenate([blended_rgb, out_alpha], axis=2) * 255.0

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        proc.wait()

        if proc.returncode != 0:
            logger.warning("Sprite: FFmpeg encoding failed with code %d", proc.returncode)
            return ""

        file_size = os.path.getsize(sprite_path)
        logger.info(
            "Sprite: successfully created %s (%d bytes, %d frames, %.1fs at %dfps)",
            sprite_path,
            file_size,
            total_frames,
            duration,
            fps,
        )
        return os.path.abspath(sprite_path)

    except (BrokenPipeError, OSError):
        logger.warning("Sprite: FFmpeg pipe error during encoding", exc_info=True)
        return ""
    except Exception:
        logger.warning("Sprite: unexpected error during encoding", exc_info=True)
        return ""
    finally:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
