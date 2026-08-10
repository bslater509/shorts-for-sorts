"""Job-config building for batch runs.

Contains ``_build_job_configs`` plus the module-level randomness tables it
uses (colors, fonts, animations, settings, tones, inactive alpha values), the
``_resolve_music`` path helper, and the default LLM model constant.

``batch_state`` is imported lazily inside :func:`_build_job_configs` to avoid
a circular import with ``gui.batch_engine``.
"""

from __future__ import annotations

import datetime
import os
import random
from typing import Any

import gui.state as shared_state
from gui.assets_utils import list_music_files
from gui.config import (
    BASE_DIR,
    DEFAULT_SCRIPT_SYSTEM_PROMPT,
    MUSIC_DIR,
    load_prompt_templates,
)
from gui.utils import get_active_llm_profile

DEFAULT_LLM_MODEL: str = "gpt-4o-mini"
"""Default model for LLM script generation in batch mode."""

# ---------------------------------------------------------------------------
# Randomisation tables (module-level so they can be reused / overridden)
# ---------------------------------------------------------------------------

VIBRANT_COLORS: list[str] = [
    "#FFFF00", "#00FFFF", "#00FF00", "#FF00FF",
    "#FF3333", "#FF9900", "#0080FF", "#FF55BB", "#33FF33",
]
"""Subtitle highlight colors chosen at random per job."""

FONT_OPTIONS: list[str] = [
    "Arial", "Impact", "Georgia", "Courier New", "Times New Roman",
]
"""Subtitle font choices picked at random per job."""

ANIMATION_OPTIONS: list[str] = [
    "tiktok_pop", "karaoke_sweep", "bouncy_bounce",
    "cinematic_zoom", "glow_shake", "neon_flicker",
    "pulse_grow", "fade_in_slide", "typewriter_swipe",
]
"""Subtitle animation styles picked at random per job."""

SETTING_OPTIONS: list[str] = [
    "Set this story in a small coastal town.",
    "Set this story in a bustling metropolis.",
    "Set this story in a remote mountain village.",
    "Set this story in a decaying industrial city.",
    "Set this story in the desert southwest.",
    "Set this story in a small Midwestern farm town.",
    "Set this story on a humid tropical island.",
    "Set this story in a historic European city.",
    "Set this story in a quiet suburban neighborhood.",
    "Set this story in a frozen northern wilderness.",
]
"""Random story settings prepended to the prompt."""

TONE_OPTIONS: list[str] = [
    "Tell this with a melancholic, reflective tone.",
    "Tell this with a darkly humorous edge.",
    "Tell this with a tense, urgent feel.",
    "Tell this with a warm, hopeful tone.",
    "Tell this with a cynical, gritty tone.",
    "Tell this with a nostalgic, bittersweet feel.",
    "", "", "",
]
"""Random tone modifiers prepended to the prompt (empties allow no modifier)."""

INACTIVE_ALPHA_OPTIONS: list[str] = ["44", "66", "88", "AA"]
"""Hex alpha values for inactive subtitles when dimming is enabled."""


def _resolve_music(path: str | None) -> str | None:
    """Resolve a music path relative to ``BASE_DIR`` when needed.

    Args:
        path: The music path (absolute, ``BASE_DIR``-relative, or ``None``).

    Returns:
        The resolved path, or ``None`` when ``path`` is falsy.
    """
    if not path:
        return None
    if os.path.exists(path):
        return path
    if os.path.exists(os.path.join(BASE_DIR, path)):
        return os.path.join(BASE_DIR, path)
    return path


def _build_job_configs(
    num_shorts: int,
    selected_prompts: list[str] | None = None,
    enable_emojis: bool | None = None,
    enable_emoji_animation: bool | None = None,
    emoji_scale_factor: float | None = None,
    emoji_hold_duration: float | None = None,
    emoji_throw_max_count: int | None = None,
    emoji_styles: list[str] | None = None,
    layout: str | None = None,
    voice_id: str | None = None,
    sub_animation_style: str | None = None,
    words_per_screen: str | None = None,
    single_word_mode: bool | None = None,
    bg_music_path: str | None = None,
    script_temp: float | None = None,
    meta_temp: float | None = None,
    post_to_tiktok: bool = False,
) -> tuple[dict[int, dict[str, Any]], str]:
    """Build job configuration dicts for a batch run.

    Handles retry configs (from ``batch_state["_retry_configs"]``) and fresh
    configs built from templates, shuffled prompts, and randomised settings.

    Args:
        num_shorts: Number of shorts to generate.
        selected_prompts: Optional list of prompt titles to restrict to.
        enable_emojis: Override for emoji enablement.
        enable_emoji_animation: Override for emoji animation.
        emoji_scale_factor: Override for emoji scale.
        emoji_hold_duration: Override for emoji hold duration.
        emoji_throw_max_count: Override for emoji throw count.
        emoji_styles: Override list of emoji font styles.
        layout: Optional layout override ("Split-Screen", "Full Screen",
            or ``None`` for random).
        voice_id: Optional voice ID override; ``None`` for random.
        sub_animation_style: Optional subtitle animation override.
        words_per_screen: Optional words-per-screen override.
        single_word_mode: Optional single-word-mode override.
        bg_music_path: Optional music file override ("random" or ``None``
            falls back to the normal random selection).
        script_temp: Optional LLM script temperature override.
        meta_temp: Optional LLM metadata temperature override.

    Returns:
        Tuple of ``(job_configs_dict, timestamp_str)``.
    """
    from gui.batch_engine import batch_state

    templates: dict[str, str] = load_prompt_templates()
    timestamp: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    active_profile: dict[str, Any] = get_active_llm_profile()
    model: str = active_profile.get("model", DEFAULT_LLM_MODEL)

    default_system_prompt: str = DEFAULT_SCRIPT_SYSTEM_PROMPT
    max_words: int = shared_state.settings.get("max_words", 400)
    raw_system_prompt: str = shared_state.settings.get(
        "system_prompt", default_system_prompt
    )
    try:
        system_prompt: str = raw_system_prompt.format(
            max_words=max_words,
            max_words_seconds=int(max_words / 2.3),
        )
    except (KeyError, ValueError):
        system_prompt = raw_system_prompt

    # Append title/hashtag instructions
    system_prompt += (
        "\n\n9. After the script ends, include exactly one line "
        "'TITLE: <short catchy title under 5 words>' "
        "followed by one line 'HASHTAGS: <5 trending hashtags>' "
        "based on your script. "
        "Do not include these lines within the script body."
    )

    job_configs: dict[int, dict[str, Any]] = {}
    batch_state["job_details"] = {}

    # Check if we have retry configs
    retry_configs: list[dict[str, Any]] | None = batch_state.get("_retry_configs")
    if retry_configs:
        job_configs = {i + 1: cfg for i, cfg in enumerate(retry_configs)}
        for idx, cfg in job_configs.items():
            cfg["index"] = idx
        batch_state["_retry_configs"] = None
        batch_state["job_details"] = {}
        for idx, cfg in job_configs.items():
            batch_state["job_details"][idx] = {
                "topic": (
                    cfg.get("prompt", "Retry")[:40]
                    if isinstance(cfg.get("prompt"), str)
                    else "Retry"
                ),
                "voice": (
                    cfg.get("voice_id", "unknown")
                    if isinstance(cfg.get("voice_id"), str)
                    else "unknown"
                ),
                "layout": "Split-Screen"
                if cfg.get("bg_video_bottom_path")
                else "Full Screen",
            }
        return job_configs, timestamp

    # Build fresh configs
    pool: dict[str, str] = templates
    if selected_prompts and templates:
        pool = {k: v for k, v in templates.items() if k in selected_prompts}
        if not pool:
            pool = templates
    prompt_items: list[tuple[str, str]] = (
        list(pool.items()) if pool else [("Random", "A surprising fact about space.")]
    )
    random.shuffle(prompt_items)

    for i in range(1, num_shorts + 1):
        template_title, prompt = prompt_items[(i - 1) % len(prompt_items)]
        voice_id_override: str | None = voice_id
        voice_name, voice_id = random.choice(shared_state.VOICES)
        if voice_id_override is not None:
            matched: tuple[str, str] | None = next(
                (
                    (name, vid)
                    for name, vid in shared_state.VOICES
                    if vid == voice_id_override
                ),
                None,
            )
            if matched is not None:
                voice_name, voice_id = matched
        is_split: bool = (
            True
            if layout == "Split-Screen"
            else (False if layout == "Full Screen" else random.choice([True, False]))
        )
        top_video: str = "random"
        bottom_video: str = "random" if is_split else ""

        os.makedirs(MUSIC_DIR, exist_ok=True)
        music_files: list[str] = [
            os.path.basename(f) for f in list_music_files(MUSIC_DIR)
        ]
        if bg_music_path and bg_music_path != "random":
            chosen_music: str | None = _resolve_music(bg_music_path)
        else:
            chosen_music = (
                os.path.join(MUSIC_DIR, random.choice(music_files))
                if music_files
                else _resolve_music("music/default_music.mp3")
            )

        sub_font: str = random.choice(FONT_OPTIONS)
        sub_size: int = random.randint(64, 84)
        sub_highlight: str = random.choice(VIBRANT_COLORS)
        sub_outline_width: int = random.randint(4, 7)
        sub_bold: bool = random.choice([True, False])

        _enable_emojis: bool = (
            enable_emojis
            if enable_emojis is not None
            else shared_state.settings.get("enable_emojis", True)
        )
        word_pop: bool = random.choice([True, False])
        word_pop_scale: float = (
            round(random.uniform(1.10, 1.25), 2) if word_pop else 1.0
        )
        inactive_dim: bool = random.choice([True, False])
        inactive_alpha: str = (
            random.choice(INACTIVE_ALPHA_OPTIONS) if inactive_dim else "FF"
        )
        _sub_animation_style: str = (
            sub_animation_style
            if sub_animation_style is not None
            else random.choice(ANIMATION_OPTIONS)
        )

        _script_temp: float = (
            script_temp
            if script_temp is not None
            else shared_state.settings.get("llm_temp_script", 0.7)
        )
        _meta_temp: float = (
            meta_temp
            if meta_temp is not None
            else shared_state.settings.get("llm_temp_metadata", 0.7)
        )
        output_filename: str = f"rendered_batch_{timestamp}_{i}.mp4"

        global_wps: str = shared_state.settings.get("words_per_screen", "3")
        if words_per_screen is not None:
            words_per_screen_choice: str = words_per_screen
        else:
            words_per_screen_choice = (
                random.choice(["1", "3", "sentence"])
                if global_wps == "random"
                else global_wps
            )

        random_setting: str = random.choice(SETTING_OPTIONS)
        random_tone: str = random.choice(TONE_OPTIONS)
        prompt_modifier: str = " ".join(
            filter(None, [random_setting, random_tone])
        ).strip()

        job_configs[i] = {
            "index": i,
            "prompt": (
                f"[{template_title}] {prompt} {prompt_modifier}"
                if prompt_modifier
                else f"[{template_title}] {prompt}"
            ),
            "voice_id": voice_id,
            "bg_video_path": top_video,
            "bg_video_bottom_path": bottom_video,
            "bg_music_path": chosen_music,
            "music_volume": shared_state.settings.get("music_volume", 0.15),
            "voice_volume": shared_state.settings.get("voice_volume", 1.0),
            "sub_font": sub_font,
            "sub_size": sub_size,
            "sub_color": "#FFFFFF",
            "sub_highlight": sub_highlight,
            "sub_outline": "#000000",
            "sub_outline_width": sub_outline_width,
            "sub_bold": sub_bold,
            "enable_emojis": _enable_emojis,
            "emoji_scale_factor": (
                emoji_scale_factor
                if emoji_scale_factor is not None
                else shared_state.settings.get("emoji_scale_factor", 1.5)
            ),
            "emoji_hold_duration": (
                emoji_hold_duration
                if emoji_hold_duration is not None
                else shared_state.settings.get("emoji_hold_duration", 0.5)
            ),
            "enable_emoji_animation": (
                enable_emoji_animation
                if enable_emoji_animation is not None
                else shared_state.settings.get("enable_emoji_animation", True)
            ),
            "emoji_throw_max_count": (
                emoji_throw_max_count
                if emoji_throw_max_count is not None
                else shared_state.settings.get("emoji_throw_max_count", 3)
            ),
            "word_pop": word_pop,
            "word_pop_scale": word_pop_scale,
            "inactive_dim": inactive_dim,
            "inactive_alpha": inactive_alpha,
            "sub_uppercase": shared_state.settings.get("sub_uppercase", True),
            "voice_speed": shared_state.settings.get("voice_speed", 1.0),
            "sub_border_style": shared_state.settings.get("sub_border_style", 1),
            "sub_shadow_width": shared_state.settings.get("sub_shadow_width", 0),
            "sub_bg_color": shared_state.settings.get("sub_bg_color", "#000000"),
            "sub_bg_alpha": shared_state.settings.get("sub_bg_alpha", "80"),
            "single_word_mode": (
                single_word_mode
                if single_word_mode is not None
                else shared_state.settings.get("single_word_mode", False)
            ),
            "words_per_screen": words_per_screen_choice,
            "emoji_position": shared_state.settings.get("emoji_position", "above"),
            "emoji_style": (
                random.choice(emoji_styles)
                if emoji_styles
                else shared_state.settings.get("emoji_style", "Noto Color Emoji")
            ),
            "sub_animation_style": _sub_animation_style,
            "script_temp": _script_temp,
            "meta_temp": _meta_temp,
            "output_filename": output_filename,
            "model": model,
            "system_prompt": system_prompt,
            "post_to_tiktok": post_to_tiktok,
            "settings": shared_state.settings.copy(),
        }

        batch_state["job_details"][i] = {
            "topic": f"[{template_title}] {prompt[:35]}...",
            "voice": voice_name,
            "layout": "Split-Screen" if is_split else "Full Screen",
            "enable_emojis": _enable_emojis,
            "emoji_style": job_configs[i]["emoji_style"],
        }

    return job_configs, timestamp
