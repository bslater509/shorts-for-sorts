import logging

logger = logging.getLogger("shorts_creator.generator")
if not logger.handlers and not logging.getLogger("shorts_creator").handlers:
    logger.addHandler(logging.NullHandler())


def format_time(seconds: float) -> str:
    """Re-exported from generator.utils for convenience."""
    from generator.utils import format_time as _fmt

    return _fmt(seconds)


def hex_to_ass_color(hex_str: str) -> str:
    """
    Converts standard HEX color string (#RRGGBB or RRGGBB) to ASS color format (&HBBGGRR).
    """
    hex_str = hex_str.strip().lstrip("#")
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


def hex_and_alpha_to_ass(hex_str: str, alpha_str: str = "00") -> str:
    """
    Converts a HEX color (e.g. #000000) and alpha transparency (e.g. 00-FF)
    to ASS color format with alpha (&HAABBGGRR).
    """
    hex_str = hex_str.strip().lstrip("#")
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


def find_emoji_for_word(word: str, emoji_map: dict) -> tuple:
    """Returns (emoji_char, anim_style) or ("", "none") if no match.

    Uses tiered matching (lowest tier wins):
      1. Exact match (word == key)
      2. Startswith (word starts with key)
      3. Left-boundary substring (key found at word boundary within word)
      4. Substring for keys with len >= 3
    """
    if not emoji_map:
        return ("", "none")
    clean_w = "".join(c for c in word.lower() if c.isalnum())
    if not clean_w:
        return ("", "none")
    sorted_keys = sorted(emoji_map.keys(), key=len, reverse=True)
    best_tier = 999
    best_key = None

    for key in sorted_keys:
        clean_key = key.lower()
        tier = None

        if clean_w == clean_key:
            tier = 1
        elif clean_w.startswith(clean_key):
            tier = 2
        else:
            idx = clean_w.find(clean_key)
            if idx > 0 and not clean_w[idx - 1].isalnum():
                tier = 3
            elif idx >= 0 and len(clean_key) >= 3:
                tier = 4

        if tier is not None and tier < best_tier:
            best_tier = tier
            best_key = key
            if tier == 1:
                break  # can't beat exact match

    if best_key is not None:
        entry = emoji_map[best_key]
        if isinstance(entry, dict):
            emoji_char = entry.get("emoji", "")
            anim = entry.get("anim", "none")
        else:
            emoji_char = entry
            anim = "none"
        logger.debug(
            "Emoji match: word=%r -> key=%r -> emoji=%s anim=%s", word, best_key, emoji_char, anim
        )
        return (emoji_char, anim)
    return ("", "none")


def generate_ass_subtitles(
    words: list,
    output_path: str,
    style_opts: dict | None = None,
    emoji_map: dict | None = None,
):
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
    emoji_style = style_opts.get("emoji_style", "Symbola")

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
        secondary_style_color = "&H00FFFF"  # default secondary

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
                same_sentence = word_info["sentence_idx"] == current_phrase[0]["sentence_idx"]

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

    target_w = style_opts.get("target_w", 1080)
    target_h = style_opts.get("target_h", 1920)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {target_w}",
        f"PlayResY: {target_h}",
        "WrapStyle: 1",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{font_size},{primary_style_color},{secondary_style_color},{ass_outline},{ass_back},{bold_val},0,0,0,100,100,0,0,{border_style},{outline_width},{shadow_width},{alignment},60,60,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
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
            phrase_anims = []
            first_emoji = ""
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
                    wrapped_emoji = f"{{\\fn{emoji_style}}}{phrase_emojis[idx]}{{\\fn}}"
                    w_text = f"{wrapped_emoji} {w_text}"

                if idx < len(phrase) - 1:
                    text_parts.append(f"{{\\kf{word_cs}}}{w_text} ")
                else:
                    text_parts.append(f"{{\\kf{word_cs}}}{w_text}")
                last_end = end

            phrase_text = "".join(text_parts)

            if emoji_position == "above" and first_emoji:
                emoji_top = f"{{\\fn{emoji_style}}}{first_emoji}{{\\fn}}"
                dialogue_text = f"{emoji_top}\\N{phrase_text}"
            else:
                dialogue_text = phrase_text

            lines.append(
                f"Dialogue: 0,{phrase_start_str},{phrase_end_str},Default,,0,0,0,,{dialogue_text}"
            )
    else:
        for phrase in phrases:
            phrase_words = [p["word"] for p in phrase]

            # Determine if any word in the phrase has an emoji
            phrase_emojis = []
            phrase_anims = []
            for word_info in phrase:
                w_emoji, w_anim = (
                    find_emoji_for_word(word_info["word"], emoji_map)
                    if emoji_position != "none" and emoji_map
                    else ("", "none")
                )
                phrase_emojis.append(w_emoji)
                phrase_anims.append(w_anim)

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
                            active_tags = (
                                f"\\alpha&H00&\\c{ass_highlight}&"
                                f"\\fscx100\\fscy100\\t(0,80,\\fscx135\\fscy135)\\t(80,180,\\fscx100\\fscy100)"
                            )
                        elif animation_style == "cinematic_zoom":
                            active_tags = (
                                f"\\c{ass_highlight}&\\fscx70\\fscy70\\alpha&HAA&"
                                f"\\t(0,120,\\fscx100\\fscy100\\alpha&H00&)"
                            )
                        elif animation_style == "glow_shake":
                            active_tags = (
                                f"\\alpha&H00&\\c{ass_highlight}&"
                                f"\\frz-6\\t(0,100,\\frz6)\\t(100,200,\\frz0)"
                            )
                        elif animation_style == "neon_flicker":
                            active_tags = (
                                f"\\alpha&H00&\\c{ass_highlight}&"
                                f"\\t(0,50,\\3c{ass_highlight}&\\3a&H33&)"
                                f"\\t(50,150,\\3c{ass_outline}&\\3a&H00&)"
                                f"\\t(150,200,\\3c{ass_highlight}&\\3a&H33&)"
                            )
                        elif animation_style == "pulse_grow":
                            active_tags = (
                                f"\\alpha&H00&\\c{ass_highlight}&"
                                f"\\fscx100\\fscy100\\frz0"
                                f"\\t(0,70,\\fscx140\\fscy140\\frz-5)"
                                f"\\t(70,140,\\fscx95\\fscy95\\frz5)"
                                f"\\t(140,200,\\fscx105\\fscy105\\frz0)"
                            )
                        elif animation_style == "fade_in_slide":
                            active_tags = "\\alpha&HFF&\\fscy60\\t(0,120,\\alpha&H00&\\fscy100)"
                        else:  # tiktok_pop
                            active_tags = "\\alpha&H00&"
                            if word_pop:
                                active_tags += f"\\fscx{scale_pct}\\fscy{scale_pct}"
                            active_tags += f"\\c{ass_highlight}&"

                        w_text = w
                        if emoji_position == "same_line" and phrase_emojis[idx]:
                            wrapped_emoji = f"{{\\fn{emoji_style}}}{phrase_emojis[idx]}{{\\fn}}"
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
                    emoji_top = f"{{\\fn{emoji_style}}}{phrase_emojis[idx]}{{\\fn}}"
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
