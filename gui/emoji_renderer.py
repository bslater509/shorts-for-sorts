import logging
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "fonts", "emoji_cache")
logger = logging.getLogger("shorts_creator.emoji")

def _emoji_to_codepoints(emoji_char: str) -> str:
    """Convert an emoji character to its codepoint representation (e.g. '1f602' or '0023-fe0f-20e3')."""
    return "-".join(f"{ord(c):x}" for c in emoji_char)

def _get_emoji_path(emoji_char: str, style: str) -> str:
    """Finds the PNG path for an emoji in the given style."""
    codepoints = _emoji_to_codepoints(emoji_char)
    style_dir = os.path.join(CACHE_DIR, style)
    
    # Try exact match
    exact_path = os.path.join(style_dir, f"{codepoints}.png")
    if os.path.exists(exact_path):
        return exact_path
    
    # Try removing fe0f (Variation Selector-16) if present, as some fonts omit it
    if "-fe0f" in codepoints:
        fallback_codepoints = codepoints.replace("-fe0f", "")
        fallback_path = os.path.join(style_dir, f"{fallback_codepoints}.png")
        if os.path.exists(fallback_path):
            return fallback_path
            
    # Try adding fe0f to single chars if not present, because some fonts mandate it
    if len(emoji_char) == 1:
        added_fe0f = f"{codepoints}-fe0f"
        fallback_path2 = os.path.join(style_dir, f"{added_fe0f}.png")
        if os.path.exists(fallback_path2):
            return fallback_path2

    # Still didn't find, try using 'apple' style as fallback if not already apple
    if style != "apple":
        return _get_emoji_path(emoji_char, "apple")
        
    return ""

async def render_emoji_png(emoji_char: str, size: int = 64, style: str = "apple") -> str:
    """Finds the cached PNG path for a single emoji character."""
    path = _get_emoji_path(emoji_char, style)
    if path:
        return path
    logger.warning(f"Emoji PNG not found for {emoji_char} ({_emoji_to_codepoints(emoji_char)}) in style {style}")
    return ""

async def render_emoji_pngs_batch(
    emoji_chars: set[str],
    size: int = 64,
    style: str = "apple",
    progress_callback=None,
) -> dict[str, str]:
    """Returns a dict mapping each emoji character to its cached PNG path."""
    results = {}
    for i, ch in enumerate(emoji_chars):
        results[ch] = _get_emoji_path(ch, style)
        if progress_callback:
            try:
                progress_callback(f"Resolving emoji {i+1}/{len(emoji_chars)}")
            except Exception:
                pass
    return results

async def prerender_emojis(emoji_chars: set[str], size: int = 64, style: str = "apple") -> dict[str, str]:
    return await render_emoji_pngs_batch(emoji_chars, size, style)

def evict_stale_emoji_cache(max_age_days: int = 30) -> int:
    """No-op for the new static cache, but kept for compatibility."""
    return 0
