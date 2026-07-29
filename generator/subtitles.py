"""ASS subtitle generation for shorts videos.

Provides functions to convert word-level timestamps into styled ASS
(Advanced SubStation Alpha) subtitle files with support for:

* Karaoke-style and word-level-highlight animations
* Emoji insertion above or inline with text
* Customisable fonts, colours, borders, shadows, and positioning
* Word grouping by sentence index or time-based heuristics
"""

from __future__ import annotations

import logging
from typing import Any

# --- Logger ---

logger: logging.Logger = logging.getLogger("shorts_creator.generator")
if not logger.handlers and not logging.getLogger("shorts_creator").handlers:
    logger.addHandler(logging.NullHandler())

# --- Named constants ---

# Colour / alpha defaults
TRANSPARENT_ALPHA: str = "00"
"""Fully opaque alpha value for ASS colour format."""
DEFAULT_PRIMARY_COLOR: str = "#FFFFFF"
"""Fallback primary (text) colour."""
DEFAULT_HIGHLIGHT_COLOR: str = "#00FFFF"
"""Fallback highlight (active word) colour."""
DEFAULT_OUTLINE_COLOR: str = "#000000"
"""Fallback outline / shadow colour."""
DEFAULT_BACK_COLOR: str = "#000000"
"""Fallback background / box colour."""
DEFAULT_INACTIVE_ALPHA: str = "88"
"""Alpha value for dimmed inactive words."""
FALLBACK_HEX_COLOR: str = "&HFFFFFF"
"""White ASS colour returned when hex parsing fails."""
FALLBACK_RGB: str = "000000"
"""Black hex value used when malformed colour is provided."""
DEFAULT_SECONDARY_COLOR: str = "&H00FFFF"
"""Fallback secondary colour for non-karaoke styles."""

# Matching constants
MATCH_TIER_EXACT: int = 1
MATCH_TIER_STARTSWITH: int = 2
MATCH_TIER_BOUNDARY_SUBSTRING: int = 3
MATCH_TIER_SUBSTRING: int = 4
MATCH_TIER_NONE: int = 999
"""Initial / sentinel value for the best-tier tracker in emoji matching."""

# Phrasing defaults
WORD_GAP_THRESHOLD: float = 0.5
"""Maximum silence gap (seconds) between words to keep them in the same phrase."""
TIME_SPAN_THRESHOLD: float = 10.0
"""Maximum total phrase duration (seconds) when sentence_idx is unavailable."""
WORDS_PER_SCREEN_DEFAULT: str = "3"
"""Default grouping mode (number of words, ``"sentence"``, or ``"1"``)."""

# ASS layout defaults
ASS_DEFAULT_MARGIN_L: int = 60
ASS_DEFAULT_MARGIN_R: int = 60
ASS_DEFAULT_MARGIN_V: int = 10

# Style defaults
DEFAULT_FONT_SIZE: int = 72
DEFAULT_OUTLINE_WIDTH: int = 5
DEFAULT_BORDER_STYLE: int = 1  # 1 = outline+shadow, 3 = opaque box
DEFAULT_SHADOW_WIDTH: int = 0
DEFAULT_ALIGNMENT: int = 5  # 5 = centred, middle of frame
DEFAULT_WORD_POP_SCALE: float = 1.15

# Animation style identifiers
STYLE_TIKTOK_POP: str = "tiktok_pop"
STYLE_BOUNCY_BOUNCE: str = "bouncy_bounce"
STYLE_CINEMATIC_ZOOM: str = "cinematic_zoom"
STYLE_GLOW_SHAKE: str = "glow_shake"
STYLE_NEON_FLICKER: str = "neon_flicker"
STYLE_PULSE_GROW: str = "pulse_grow"
STYLE_FADE_IN_SLIDE: str = "fade_in_slide"
STYLE_KARAOKE_SWEEP: str = "karaoke_sweep"
STYLE_TYPEWRITER_SWIPE: str = "typewriter_swipe"
KARAOKE_STYLES: frozenset = frozenset({STYLE_KARAOKE_SWEEP, STYLE_TYPEWRITER_SWIPE})
"""Set of animation styles that use karaoke (``\\kf``) timing."""

ASS_TRUE_BOLD: int = -1
ASS_FALSE_BOLD: int = 0

# --- Re-exports ---


def format_time(seconds: float) -> str:
    """Re-exported from :mod:`generator.utils` for convenience.

    Args:
        seconds: Time value in seconds.

    Returns:
        ASS-formatted timestamp string (``H:MM:SS.cs``).
    """
    from generator.utils import format_time as _fmt

    return _fmt(seconds)


# --- Colour conversion helpers ---


def hex_to_ass_color(hex_str: str) -> str:
    """Convert a standard hex colour string to ASS colour format.

    ASS stores colours in ``&HBBGGRR`` order (blue-green-red).  An optional
    8-character hex string (``#RRGGBBAA``) is also supported and returns
    ``&HAABBGGRR``.

    Args:
        hex_str: Hex colour string, optionally prefixed with ``#``.
            May be 6 characters (``RRGGBB``) or 8 (``RRGGBBAA``).

    Returns:
        ASS colour string (e.g. ``"&HFFFFFF"`` for white,
        ``"&H800000FF"`` for red with alpha 0x80).

    .. note::
        Malformed inputs log a warning and return white (``&HFFFFFF``).
    """
    hex_str = hex_str.strip().lstrip("#")

    if len(hex_str) == 6:
        r: str = hex_str[0:2]
        g: str = hex_str[2:4]
        b: str = hex_str[4:6]
        return f"&H{b}{g}{r}"
    elif len(hex_str) == 8:
        r = hex_str[0:2]
        g = hex_str[2:4]
        b = hex_str[4:6]
        a: str = hex_str[6:8]
        return f"&H{a}{b}{g}{r}"

    logger.warning(
        "hex_to_ass_color: malformed hex input '%s' — defaulting to white", hex_str
    )
    return FALLBACK_HEX_COLOR


def hex_and_alpha_to_ass(hex_str: str, alpha_str: str = TRANSPARENT_ALPHA) -> str:
    """Convert a hex colour and an alpha transparency value to ASS format.

    ASS colour format with alpha is ``&HAABBGGRR`` where ``AA``
    is the alpha channel (``00`` = fully opaque, ``FF`` = fully transparent).

    Args:
        hex_str: Hex colour string (``#RRGGBB``), optionally prefixed with ``#``.
        alpha_str: Alpha value as a hex string (``"00"``–``"FF"``).
            A single-digit value is zero-padded.

    Returns:
        ASS colour string with alpha (e.g. ``"&H80FFFFFF"``).

    .. note::
        Malformed hex colours default to black (``&HAA000000``).
    """
    hex_str = hex_str.strip().lstrip("#")

    if len(hex_str) == 6:
        r: str = hex_str[0:2]
        g: str = hex_str[2:4]
        b: str = hex_str[4:6]
    else:
        r, g, b = FALLBACK_RGB[:2], FALLBACK_RGB[2:4], FALLBACK_RGB[4:6]

    alpha: str = alpha_str.strip()
    if not alpha:
        alpha = TRANSPARENT_ALPHA
    elif len(alpha) == 1:
        alpha = "0" + alpha

    return f"&H{alpha}{b}{g}{r}"


# --- Emoji matching ---


def find_emoji_for_word(word: str, emoji_map: dict[str, Any] | None) -> tuple[str, str]:
    """Find the best-matching emoji for a word using tiered matching.

    The matching tiers, from best to worst, are:

    1.  **Exact match** — ``word == key`` (case-insensitive after stripping
        non-alphanumeric characters).
    2.  **Starts-with** — ``word.startswith(key)``.
    3.  **Left-boundary substring** — ``key`` appears in ``word`` at a position
        preceded by a non-alphanumeric character.
    4.  **Substring** — ``key`` appears anywhere in ``word`` (only for keys
        with length ≥ 3).

    Within each tier, longer keys are preferred.  Tier 1 short-circuits
    immediately.

    Args:
        word: The word to look up.
        emoji_map: Dictionary mapping keyword → entry.
            Each entry may be either a plain emoji string or a dict with
            ``"emoji"`` (str) and optional ``"anim"`` (str) keys.  When
            ``None`` or empty, returns ``("", "none")``.

    Returns:
        Tuple of ``(emoji_character, animation_style)``.
        Returns ``("", "none")`` when no match is found.
    """
    if not emoji_map:
        return ("", "none")

    clean_w: str = "".join(c for c in word.lower() if c.isalnum())
    if not clean_w:
        return ("", "none")

    sorted_keys: list[str] = sorted(emoji_map.keys(), key=len, reverse=True)
    best_tier: int = MATCH_TIER_NONE
    best_key: str | None = None

    for key in sorted_keys:
        clean_key: str = key.lower()
        tier: int | None = None

        if clean_w == clean_key:
            tier = MATCH_TIER_EXACT
        elif clean_w.startswith(clean_key):
            tier = MATCH_TIER_STARTSWITH
        else:
            idx: int = clean_w.find(clean_key)
            if idx > 0 and not clean_w[idx - 1].isalnum():
                tier = MATCH_TIER_BOUNDARY_SUBSTRING
            elif idx >= 0 and len(clean_key) >= 3:
                tier = MATCH_TIER_SUBSTRING

        if tier is not None and tier < best_tier:
            best_tier = tier
            best_key = key
            if tier == MATCH_TIER_EXACT:
                break  # Cannot beat an exact match

    if best_key is not None:
        entry: Any = emoji_map[best_key]
        if isinstance(entry, dict):
            emoji_char: str = entry.get("emoji", "")
            anim: str = entry.get("anim", "none")
        else:
            emoji_char = entry
            anim = "none"
        logger.debug(
            "Emoji match: word=%r -> key=%r -> emoji=%s anim=%s",
            word,
            best_key,
            emoji_char,
            anim,
        )
        return (emoji_char, anim)

    return ("", "none")


# --- Word phrasing ---


def _group_words_into_phrases(
    words: list[dict[str, Any]],
    uppercase: bool,
    words_per_screen: str,
) -> list[list[dict[str, Any]]]:
    """Group word dicts into phrases based on timing and sentence boundaries.

    Phrasing logic:

    * ``"1"`` — each word forms its own phrase.
    * ``"3"`` — phrases hold up to 3 words with gaps < 0.5 s.
    * ``"sentence"`` — words with the same ``sentence_idx`` are grouped.
    * Otherwise — fallback heuristic (max span 10 s, gap < 0.5 s).

    Args:
        words: List of word dicts.  Each dict must contain ``word`` (str),
            ``start`` (float), ``end`` (float), and optionally
            ``sentence_idx`` (int).
        uppercase: If ``True``, convert all words to uppercase.
        words_per_screen: Phrasing mode (see description above).

    Returns:
        List of phrases, where each phrase is a list of word dicts.
    """
    phrases: list[list[dict[str, Any]]] = []
    current_phrase: list[dict[str, Any]] = []

    for word_info in words:
        word: str = word_info["word"].strip()
        if uppercase:
            word = word.upper()
        start: float = word_info["start"]
        end: float = word_info["end"]

        word_dict: dict[str, Any] = {"word": word, "start": start, "end": end}
        if "sentence_idx" in word_info:
            word_dict["sentence_idx"] = word_info["sentence_idx"]

        if not current_phrase:
            current_phrase.append(word_dict)
        else:
            prev = current_phrase[-1]
            time_span: float = end - current_phrase[0]["start"]
            gap: float = start - prev["end"]

            same_sentence: bool = False
            if "sentence_idx" in word_info and "sentence_idx" in current_phrase[0]:
                same_sentence = (
                    word_info["sentence_idx"] == current_phrase[0]["sentence_idx"]
                )

            if words_per_screen == "1":
                should_group: bool = False
            elif words_per_screen == "3":
                should_group = len(current_phrase) < 3 and gap < WORD_GAP_THRESHOLD
            else:
                # "sentence" mode or fallback
                if "sentence_idx" in word_info:
                    should_group = same_sentence
                else:
                    should_group = time_span < TIME_SPAN_THRESHOLD and gap < WORD_GAP_THRESHOLD

            if should_group:
                current_phrase.append(word_dict)
            else:
                phrases.append(current_phrase)
                current_phrase = [word_dict]

    if current_phrase:
        phrases.append(current_phrase)

    return phrases


# --- Animation tag helpers ---


def _get_animation_active_tags(
    animation_style: str,
    ass_highlight: str,
    ass_outline: str,
    word_pop: bool,
    scale_pct: int,
) -> str:
    """Return ASS override tags for the active (highlighted) word.

    These tags are used by the non-karaoke word-level style formatter.

    Args:
        animation_style: Name of the animation style (e.g. ``"tiktok_pop"``,
            ``"bouncy_bounce"``, …).
        ass_highlight: Highlight colour in ASS ``&HBBGGRR`` format.
        ass_outline: Outline colour in ASS ``&HBBGGRR`` format.
        word_pop: Whether to apply scale-up (pop) effect.
        scale_pct: Scale percentage for word-pop (e.g. 115 for 1.15×).

    Returns:
        ASS override tag string (may be empty for no overrides).
    """
    if animation_style == STYLE_BOUNCY_BOUNCE:
        return (
            f"\\alpha&H00&\\c{ass_highlight}&"
            f"\\fscx100\\fscy100"
            f"\\t(0,80,\\fscx135\\fscy135)"
            f"\\t(80,180,\\fscx100\\fscy100)"
        )
    elif animation_style == STYLE_CINEMATIC_ZOOM:
        return (
            f"\\c{ass_highlight}&\\fscx70\\fscy70\\alpha&HAA&"
            f"\\t(0,120,\\fscx100\\fscy100\\alpha&H00&)"
        )
    elif animation_style == STYLE_GLOW_SHAKE:
        return (
            f"\\alpha&H00&\\c{ass_highlight}&"
            f"\\frz-6\\t(0,100,\\frz6)\\t(100,200,\\frz0)"
        )
    elif animation_style == STYLE_NEON_FLICKER:
        return (
            f"\\alpha&H00&\\c{ass_highlight}&"
            f"\\t(0,50,\\3c{ass_highlight}&\\3a&H33&)"
            f"\\t(50,150,\\3c{ass_outline}&\\3a&H00&)"
            f"\\t(150,200,\\3c{ass_highlight}&\\3a&H33&)"
        )
    elif animation_style == STYLE_PULSE_GROW:
        return (
            f"\\alpha&H00&\\c{ass_highlight}&"
            f"\\fscx100\\fscy100\\frz0"
            f"\\t(0,70,\\fscx140\\fscy140\\frz-5)"
            f"\\t(70,140,\\fscx95\\fscy95\\frz5)"
            f"\\t(140,200,\\fscx105\\fscy105\\frz0)"
        )
    elif animation_style == STYLE_FADE_IN_SLIDE:
        return "\\alpha&HFF&\\fscy60\\t(0,120,\\alpha&H00&\\fscy100)"
    else:
        # tiktok_pop (default)
        tags: str = "\\alpha&H00&"
        if word_pop:
            tags += f"\\fscx{scale_pct}\\fscy{scale_pct}"
        tags += f"\\c{ass_highlight}&"
        return tags


# --- Dialogue line formatters ---


def _format_karaoke_sweep(
    phrases: list[list[dict[str, Any]]],
    emoji_map: dict[str, Any] | None,
    emoji_position: str,
    emoji_style: str,
) -> list[str]:
    """Format phrases as ASS dialogue lines using karaoke (``\\kf``) timing.

    Each word is assigned a ``\\kf`` duration tag based on its spoken length.
    The karaoke highlight colour is set at the style level so the player
    sweeps across each word automatically.

    Args:
        phrases: List of phrases (each phrase is a list of word dicts).
        emoji_map: Keyword-to-emoji mapping (may be ``None``).
        emoji_position: Placement of emoji (``"above"``, ``"same_line"``,
            or ``"none"``).
        emoji_style: Font name for rendering emoji characters.

    Returns:
        List of ``Dialogue:`` ASS lines.
    """
    lines: list[str] = []
    for p_idx, phrase in enumerate(phrases):
        phrase_start_str: str = format_time(phrase[0]["start"])
        if p_idx < len(phrases) - 1:
            phrase_end_str: str = format_time(phrases[p_idx + 1][0]["start"])
        else:
            phrase_end_str = format_time(phrase[-1]["end"])

        # Determine emojis for each word in the phrase
        phrase_emojis: list[str] = []
        phrase_anims: list[str] = []
        first_emoji: str = ""
        for word_info in phrase:
            w_emoji, w_anim = (
                find_emoji_for_word(word_info["word"], emoji_map)
                if emoji_position != "none" and emoji_map
                else ("", "none")
            )
            phrase_emojis.append(w_emoji)
            phrase_anims.append(w_anim)
            if w_emoji and not first_emoji:
                first_emoji = w_emoji

        text_parts: list[str] = []
        last_end: float = phrase[0]["start"]
        for idx, w_info in enumerate(phrase):
            w: str = w_info["word"]
            start: float = w_info["start"]
            end: float = w_info["end"]

            # Insert gap timing between words
            if start > last_end:
                gap_cs: int = int(round((start - last_end) * 100))
                if gap_cs > 0:
                    text_parts.append(f"{{\\kf{gap_cs}}}")

            word_dur: float = end - start
            word_cs: int = int(round(word_dur * 100))
            if word_cs <= 0:
                word_cs = 1

            w_text: str = w
            if emoji_position == "same_line" and phrase_emojis[idx]:
                wrapped_emoji: str = (
                    f"{{\\fn{emoji_style}}}{phrase_emojis[idx]}{{\\fn}}"
                )
                w_text = f"{wrapped_emoji} {w_text}"

            if idx < len(phrase) - 1:
                text_parts.append(f"{{\\kf{word_cs}}}{w_text} ")
            else:
                text_parts.append(f"{{\\kf{word_cs}}}{w_text}")
            last_end = end

        phrase_text: str = "".join(text_parts)

        if emoji_position == "above" and first_emoji:
            emoji_top: str = f"{{\\fn{emoji_style}}}{first_emoji}{{\\fn}}"
            dialogue_text: str = f"{emoji_top}\\N{phrase_text}"
        else:
            dialogue_text = phrase_text

        lines.append(
            f"Dialogue: 0,{phrase_start_str},{phrase_end_str},"
            f"Default,,0,0,0,,{dialogue_text}"
        )
    return lines


def _format_word_level_style(
    phrases: list[list[dict[str, Any]]],
    emoji_map: dict[str, Any] | None,
    emoji_position: str,
    emoji_style: str,
    animation_style: str,
    ass_highlight: str,
    ass_outline: str,
    word_pop: bool,
    scale_pct: int,
    inactive_dim: bool,
    inactive_alpha: str,
) -> list[str]:
    """Format phrases as ASS dialogue lines with word-level active highlighting.

    Each word in a phrase gets its own dialogue line timed to its spoken
    duration, with the active word rendered using animation tags and
    inactive words optionally dimmed.

    Args:
        phrases: List of phrases (each phrase is a list of word dicts).
        emoji_map: Keyword-to-emoji mapping (may be ``None``).
        emoji_position: Placement of emoji (``"above"``, ``"same_line"``,
            or ``"none"``).
        emoji_style: Font name for rendering emoji characters.
        animation_style: Active-word animation style identifier.
        ass_highlight: Highlight colour in ASS ``&HBBGGRR`` format.
        ass_outline: Outline colour in ASS ``&HBBGGRR`` format.
        word_pop: Whether to apply scale-up effect on the active word.
        scale_pct: Scale percentage for word pop.
        inactive_dim: If ``True``, dim non-active words with alpha.
        inactive_alpha: Alpha value for dimmed inactive words.

    Returns:
        List of ``Dialogue:`` ASS lines.
    """
    lines: list[str] = []
    for phrase in phrases:
        phrase_words: list[str] = [p["word"] for p in phrase]

        # Determine emojis for each word in the phrase
        phrase_emojis: list[str] = []
        phrase_anims: list[str] = []
        for word_info in phrase:
            w_emoji, w_anim = (
                find_emoji_for_word(word_info["word"], emoji_map)
                if emoji_position != "none" and emoji_map
                else ("", "none")
            )
            phrase_emojis.append(w_emoji)
            phrase_anims.append(w_anim)

        for idx, active_word_info in enumerate(phrase):
            start_str: str = format_time(active_word_info["start"])

            # Stretch the end time to the next word's start to prevent blinking
            if idx < len(phrase) - 1:
                end_str: str = format_time(phrase[idx + 1]["start"])
            else:
                end_str = format_time(active_word_info["end"])

            active_tags: str = _get_animation_active_tags(
                animation_style, ass_highlight, ass_outline, word_pop, scale_pct
            )

            text_parts: list[str] = []
            for w_idx, w in enumerate(phrase_words):
                if w_idx == idx:
                    w_text: str = w
                    if emoji_position == "same_line" and phrase_emojis[idx]:
                        wrapped_emoji_inline: str = (
                            f"{{\\fn{emoji_style}}}{phrase_emojis[idx]}{{\\fn}}"
                        )
                        w_text = f"{wrapped_emoji_inline} {w_text}"

                    text_parts.append(f"{{{active_tags}}}{w_text}{{\\r}}")
                else:
                    if inactive_dim:
                        text_parts.append(
                            f"{{\\alpha&H{inactive_alpha}&}}{w}{{\\r}}"
                        )
                    else:
                        text_parts.append(w)

            phrase_text: str = " ".join(text_parts)

            if emoji_position == "above" and phrase_emojis[idx]:
                emoji_top: str = f"{{\\fn{emoji_style}}}{phrase_emojis[idx]}{{\\fn}}"
                dialogue_text: str = f"{emoji_top}\\N{phrase_text}"
            else:
                dialogue_text = phrase_text

            lines.append(
                f"Dialogue: 0,{start_str},{end_str},"
                f"Default,,0,0,0,,{dialogue_text}"
            )

    return lines


# --- Main entry point ---


def generate_ass_subtitles(
    words: list[dict[str, Any]],
    output_path: str,
    style_opts: dict[str, Any] | None = None,
    emoji_map: dict[str, Any] | None = None,
) -> None:
    """Generate a styled ASS subtitle file from word-level timestamps.

    Words are grouped into phrases (see :func:`_group_words_into_phrases`),
    then formatted as ASS dialogue lines with configurable animation, colours,
    fonts, and emoji support.

    Args:
        words: List of word dicts.  Each dict must contain at least
            ``word`` (str), ``start`` (float seconds), and ``end`` (float
            seconds).  May optionally include ``sentence_idx`` for
            sentence-aware grouping.
        output_path: Destination path for the ``.ass`` file.
        style_opts: Optional dictionary of style overrides.  Supported keys:

            * ``font_name`` (str, default ``"Arial"``)
            * ``font_size`` (int, default ``72``)
            * ``primary_color`` (str hex, default ``"#FFFFFF"``)
            * ``highlight_color`` (str hex, default ``"#00FFFF"``)
            * ``outline_color`` (str hex, default ``"#000000"``)
            * ``outline_width`` (int, default ``5``)
            * ``bold`` (bool, default ``True``)
            * ``alignment`` (int 1–9, default ``5``)
            * ``margin_v`` (int, default ``10``)
            * ``word_pop`` (bool, default ``True``)
            * ``word_pop_scale`` (float, default ``1.15``)
            * ``inactive_dim`` (bool, default ``True``)
            * ``inactive_alpha`` (str hex, default ``"88"``)
            * ``enable_emojis`` (bool, default ``True``)
            * ``uppercase`` (bool, default ``True``)
            * ``border_style`` (int, default ``1``)
            * ``shadow_width`` (int, default ``0``)
            * ``back_color`` (str hex, default ``"#000000"``)
            * ``back_alpha`` (str hex, default ``"00"``)
            * ``words_per_screen`` (str, default ``"3"``)
            * ``emoji_position`` (str, default ``"above"``)
            * ``emoji_style`` (str, default ``"Symbola"``)
            * ``sub_animation_style`` (str, default ``"tiktok_pop"``)
            * ``target_w`` (int, default ``1080``)
            * ``target_h`` (int, default ``1920``)

        emoji_map: Keyword-to-emoji dictionary for contextual emoji
            insertion.  Passed to :func:`find_emoji_for_word`.

    Raises:
        RuntimeError: If the subtitle file cannot be written.
    """
    if style_opts is None:
        style_opts = {}

    # --- Extract style options with defaults ---
    font_name: str = style_opts.get("font_name", "Arial")
    font_size: int = style_opts.get("font_size", DEFAULT_FONT_SIZE)
    primary_color: str = style_opts.get("primary_color", DEFAULT_PRIMARY_COLOR)
    highlight_color: str = style_opts.get("highlight_color", DEFAULT_HIGHLIGHT_COLOR)
    outline_color: str = style_opts.get("outline_color", DEFAULT_OUTLINE_COLOR)
    outline_width: int = style_opts.get("outline_width", DEFAULT_OUTLINE_WIDTH)
    bold_val: int = (
        ASS_TRUE_BOLD if style_opts.get("bold", True) else ASS_FALSE_BOLD
    )
    alignment: int = style_opts.get("alignment", DEFAULT_ALIGNMENT)
    margin_v: int = style_opts.get("margin_v", ASS_DEFAULT_MARGIN_V)

    # Subtitle animation options
    word_pop: bool = style_opts.get("word_pop", True)
    word_pop_scale: float = style_opts.get("word_pop_scale", DEFAULT_WORD_POP_SCALE)
    inactive_dim: bool = style_opts.get("inactive_dim", True)
    inactive_alpha: str = style_opts.get("inactive_alpha", DEFAULT_INACTIVE_ALPHA)
    enable_emojis: bool = style_opts.get("enable_emojis", True)

    # Newer styling options
    uppercase: bool = style_opts.get("uppercase", True)
    border_style: int = style_opts.get("border_style", DEFAULT_BORDER_STYLE)
    shadow_width: int = style_opts.get("shadow_width", DEFAULT_SHADOW_WIDTH)
    back_color: str = style_opts.get("back_color", DEFAULT_BACK_COLOR)
    back_alpha: str = style_opts.get("back_alpha", TRANSPARENT_ALPHA)
    words_per_screen: str = str(
        style_opts.get("words_per_screen", WORDS_PER_SCREEN_DEFAULT)
    )
    emoji_position: str = (
        style_opts.get("emoji_position", "above") if enable_emojis else "none"
    )
    emoji_style: str = style_opts.get("emoji_style", "Symbola")

    animation_style: str = style_opts.get("sub_animation_style", STYLE_TIKTOK_POP)

    scale_pct: int = int(word_pop_scale * 100)

    # Convert colours to ASS format
    ass_primary: str = hex_to_ass_color(primary_color)
    ass_highlight: str = hex_to_ass_color(highlight_color)
    ass_outline: str = hex_to_ass_color(outline_color)
    ass_back: str = hex_and_alpha_to_ass(back_color, back_alpha)

    # Animation-aware style colour setup
    if animation_style in KARAOKE_STYLES:
        primary_style_color: str = ass_highlight
        if animation_style == STYLE_TYPEWRITER_SWIPE:
            secondary_style_color: str = "&HFF000000"  # Fully transparent
        elif inactive_dim:
            secondary_style_color = hex_and_alpha_to_ass(
                primary_color, inactive_alpha
            )
        else:
            secondary_style_color = ass_primary
    else:
        primary_style_color = ass_primary
        secondary_style_color = DEFAULT_SECONDARY_COLOR

    # --- Group words into phrases ---
    phrases: list[list[dict[str, Any]]] = _group_words_into_phrases(
        words, uppercase, words_per_screen
    )

    # --- Build ASS header ---
    target_w: int = style_opts.get("target_w", 1080)
    target_h: int = style_opts.get("target_h", 1920)

    lines: list[str] = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {target_w}",
        f"PlayResY: {target_h}",
        "WrapStyle: 1",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding"
        ),
        (
            f"Style: Default,{font_name},{font_size},"
            f"{primary_style_color},{secondary_style_color},"
            f"{ass_outline},{ass_back},"
            f"{bold_val},0,0,0,100,100,0,0,"
            f"{border_style},{outline_width},{shadow_width},"
            f"{alignment},{ASS_DEFAULT_MARGIN_L},{ASS_DEFAULT_MARGIN_R},"
            f"{margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text",
    ]

    # --- Build dialogue lines ---
    if animation_style in KARAOKE_STYLES:
        dialogue_lines: list[str] = _format_karaoke_sweep(
            phrases, emoji_map, emoji_position, emoji_style
        )
    else:
        dialogue_lines = _format_word_level_style(
            phrases,
            emoji_map,
            emoji_position,
            emoji_style,
            animation_style,
            ass_highlight,
            ass_outline,
            word_pop,
            scale_pct,
            inactive_dim,
            inactive_alpha,
        )

    lines.extend(dialogue_lines)

    # --- Write output file ---
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        logger.error(
            "Failed to write ASS subtitles to '%s': %s", output_path, e, exc_info=True
        )
        raise RuntimeError(f"Failed to write ASS subtitles: {e}") from e
