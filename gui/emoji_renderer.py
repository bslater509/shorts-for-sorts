import os
import asyncio
import logging
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "fonts", "emoji_cache")
logger = logging.getLogger("shorts_creator.emoji")


def _emoji_cache_key(emoji_char: str, size: int) -> str:
    """Convert an emoji character to a cached PNG filename.

    Converts each Unicode codepoint in the emoji to its lowercase hex
    representation, joining multi-codepoint emojis with underscores.

    Examples:
        "🚀"          -> "1f680_128.png"
        "🏴‍☠️" -> "1f3f4_200d_2620_fe0f_128.png"
    """
    codepoints = [f"{ord(c):x}" for c in emoji_char]
    key = "_".join(codepoints)
    return f"{key}_{size}.png"


async def render_emoji_png(emoji_char: str, size: int = 128) -> str:
    """Render an emoji character as a PNG image, returning the cached file path.

    Uses Playwright + headless Chrome to render the emoji. If the PNG is
    already cached on disk the file path is returned immediately without
    launching a browser.

    Args:
        emoji_char: A single emoji character (possibly multiple Unicode
                    codepoints, e.g. a ZWJ sequence).
        size:       Font size in pixels (default 128).

    Returns:
        Absolute path to the cached PNG file, or an empty string on failure.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)

    cache_key = _emoji_cache_key(emoji_char, size)
    cache_path = os.path.join(CACHE_DIR, cache_key)

    # Return cached result immediately if available
    if os.path.exists(cache_path):
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

            # Set page background to transparent
            await page.evaluate(
                "() => { document.documentElement.style.background = 'transparent'; }"
            )

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
                raise RuntimeError("Could not find #emoji element")

            # Use page.screenshot with clip instead of element.screenshot for RGBA support
            bbox = await element.bounding_box()
            if bbox is None:
                raise RuntimeError("Could not get bounding box for #emoji element")

            screenshot_bytes = await page.screenshot(
                clip={"x": bbox["x"], "y": bbox["y"], "width": bbox["width"], "height": bbox["height"]},
                type="png",
                omit_background=True,
            )

            with open(cache_path, "wb") as f:
                f.write(screenshot_bytes)

            return cache_path

    except Exception:
        logger.warning("Failed to render emoji %r at size %d", emoji_char, size)
        return ""
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass


async def prerender_emojis(
    emoji_chars: set[str], size: int = 128
) -> dict[str, str]:
    """Render a set of emoji characters in parallel to warm the cache.

    Args:
        emoji_chars: Set of emoji character strings to render.
        size:        Font size in pixels (default 128).

    Returns:
        A dictionary mapping each emoji character to its cached PNG path
        (empty string for any that failed to render).
    """
    tasks = [render_emoji_png(emoji, size) for emoji in emoji_chars]
    results = await asyncio.gather(*tasks)
    return dict(zip(emoji_chars, results))
