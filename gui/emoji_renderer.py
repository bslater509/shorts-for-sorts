import os
import asyncio
import logging
import traceback
import time
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "fonts", "emoji_cache")
CACHE_MAX_AGE_DAYS = 30
logger = logging.getLogger("shorts_creator.emoji")


def _emoji_cache_key(emoji_char: str, size: int) -> str:
    """Convert an emoji character to a cached PNG filename."""
    codepoints = [f"{ord(c):x}" for c in emoji_char]
    key = "_".join(codepoints)
    return f"{key}_{size}.png"


async def _render_single_on_page(
    page, emoji_char: str, size: int, cache_path: str
) -> str:
    """Render one emoji on an already-open Playwright page and save to cache_path."""
    try:
        html_content = (
            '<div id="emoji" style="'
            "font-family: 'Noto Color Emoji', 'Apple Color Emoji', "
            "'Segoe UI Emoji', sans-serif; "
            f"font-size: {size}px; line-height: 1; "
            'display: inline-block; background: transparent;">'
            f"{emoji_char}</div>"
        )
        await page.set_content(html_content)
        await page.wait_for_selector("#emoji")

        element = await page.query_selector("#emoji")
        if element is None:
            logger.warning("Emoji render: #emoji element not found in DOM for %r", emoji_char)
            return ""

        bbox = await element.bounding_box()
        if bbox is None:
            logger.warning("Emoji render: bounding box is None for %r", emoji_char)
            return ""

        screenshot_bytes = await page.screenshot(
            clip={"x": bbox["x"], "y": bbox["y"], "width": bbox["width"], "height": bbox["height"]},
            type="png",
            omit_background=True,
        )

        if not screenshot_bytes:
            logger.warning("Emoji render: screenshot returned empty for %r", emoji_char)
            return ""

        with open(cache_path, "wb") as f:
            f.write(screenshot_bytes)
        file_size = os.path.getsize(cache_path)
        logger.info("Emoji rendered and cached: %r -> %s (%d bytes)", emoji_char, os.path.basename(cache_path), file_size)
        return cache_path

    except Exception:
        logger.warning("Emoji render: error rendering %r at size %d:\n%s",
                       emoji_char, size, traceback.format_exc())
        return ""


async def render_emoji_png(emoji_char: str, size: int = 128) -> str:
    """Render a single emoji via Playwright (launches its own browser).

    Returns the cached PNG path, or empty string on failure.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_key = _emoji_cache_key(emoji_char, size)
    cache_path = os.path.join(CACHE_DIR, cache_key)

    if os.path.exists(cache_path):
        logger.debug("Emoji PNG cache hit: %r -> %s", emoji_char, os.path.basename(cache_path))
        return cache_path

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu"],
            )
            page = await browser.new_page()
            await page.set_viewport_size({"width": size * 2, "height": size * 2})
            await page.evaluate(
                "() => { document.documentElement.style.background = 'transparent'; }"
            )
            return await _render_single_on_page(page, emoji_char, size, cache_path)

    except Exception:
        logger.warning("Emoji render: unexpected error for %r at size %d:\n%s",
                       emoji_char, size, traceback.format_exc())
        return ""
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception as e:
                logger.warning("Emoji render: failed to close browser for %r: %s", emoji_char, e)


async def render_emoji_pngs_batch(
    emoji_chars: set[str], size: int = 128,
    progress_callback=None,
) -> dict[str, str]:
    """Render multiple emojis in a single Playwright browser session.

    Launches ONE browser, renders all uncached emojis sequentially on the
    same page, then closes the browser. Much faster than calling
    ``render_emoji_png`` for each unique emoji.

    Args:
        emoji_chars: Set of emoji characters to render.
        size:        Font size in pixels (default 128).

    Returns:
        Dict mapping each emoji character to its cached PNG path
        (empty string for any that failed).
    """
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Check cache first
    results: dict[str, str] = {}
    uncached: list[str] = []

    for ch in emoji_chars:
        cache_key = _emoji_cache_key(ch, size)
        cache_path = os.path.join(CACHE_DIR, cache_key)
        if os.path.exists(cache_path):
            results[ch] = cache_path
        else:
            uncached.append(ch)

    if not uncached:
        logger.debug("Emoji batch: all %d emojis already cached", len(emoji_chars))
        return results

    logger.info("Emoji batch: %d cached, %d to render in one browser session",
                len(results), len(uncached))

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page()
            await page.set_viewport_size({"width": size * 2, "height": size * 2})
            await page.evaluate(
                "() => { document.documentElement.style.background = 'transparent'; }"
            )

            total = len(uncached)
            for i, ch in enumerate(uncached):
                cache_key = _emoji_cache_key(ch, size)
                cache_path = os.path.join(CACHE_DIR, cache_key)
                path = await _render_single_on_page(page, ch, size, cache_path)
                results[ch] = path
                if progress_callback:
                    try:
                        progress_callback(f"Emoji Render ({i + 1}/{total})")
                    except Exception:
                        pass

        return results

    except Exception:
        logger.warning("Emoji batch: unexpected error rendering %d emojis:\n%s",
                       len(uncached), traceback.format_exc())
        return results
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass


async def prerender_emojis(
    emoji_chars: set[str], size: int = 128
) -> dict[str, str]:
    """Render a set of emoji characters in parallel (legacy, uses batch under the hood)."""
    return await render_emoji_pngs_batch(emoji_chars, size)


def evict_stale_emoji_cache(max_age_days: int = CACHE_MAX_AGE_DAYS) -> int:
    """Remove cached emoji PNGs older than ``max_age_days``.

    Returns the number of evicted files.
    """
    if not os.path.isdir(CACHE_DIR):
        return 0
    now = time.time()
    cutoff = now - max_age_days * 86400
    evicted = 0
    for fname in os.listdir(CACHE_DIR):
        if not fname.endswith(".png"):
            continue
        fpath = os.path.join(CACHE_DIR, fname)
        try:
            mtime = os.path.getmtime(fpath)
            if mtime < cutoff:
                os.remove(fpath)
                evicted += 1
        except OSError:
            pass
    if evicted:
        logger.info("Emoji cache eviction: removed %d stale PNG(s) older than %d days", evicted, max_age_days)
    return evicted
