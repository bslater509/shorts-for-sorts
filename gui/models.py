"""Pydantic request/response models for the Shorts for Sorts API.

These models define the schema for all REST endpoint request bodies and
responses, providing automatic validation and documentation via FastAPI.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SettingsModel(BaseModel):
    """Application settings schema.

    All fields are optional with sensible defaults.  Used by the
    ``POST /api/settings`` endpoint.
    """

    llm_profiles: list[dict[str, Any]] | None = []
    active_llm_profile_id: str | None = ""
    pexels_api_key: str | None = ""
    tiktok_sessionid: str | None = ""
    voice_speed: float | None = 1.0
    voice_volume: float | None = 1.0
    music_volume: float | None = 0.15
    local_whisper: bool | None = True
    local_whisper_model: str | None = "tiny"
    whisper_api_key: str | None = ""
    whisper_base_url: str | None = ""
    render_resolution: str | None = "720p"
    render_preset: str | None = "ultrafast"
    video_encoder: str | None = "libx264"
    max_workers: int | None = 1
    llm_max_workers: int | None = 5
    words_per_screen: str | None = "3"
    sub_font: str | None = "Arial"
    sub_size: int | None = 72
    sub_color: str | None = "#FFFFFF"
    sub_highlight: str | None = "#00FFFF"
    sub_outline: str | None = "#000000"
    llm_temp_metadata: float | None = 0.7
    llm_temp_keywords: float | None = 0.7
    sub_outline_width: int | None = 5
    sub_bold: bool | None = True
    word_pop: bool | None = True
    word_pop_scale: float | None = 1.15
    inactive_dim: bool | None = True
    inactive_alpha: str | None = "88"
    enable_emojis: bool | None = True
    sub_uppercase: bool | None = True
    sub_border_style: int | None = 1
    sub_shadow_width: int | None = 0
    sub_bg_color: str | None = "#000000"
    sub_bg_alpha: str | None = "80"
    single_word_mode: bool | None = False
    emoji_position: str | None = "above"
    emoji_style: str | None = "Noto Color Emoji"
    sub_animation_style: str | None = "tiktok_pop"
    enable_emoji_animation: bool | None = True
    emoji_scale_factor: float | None = 1.5
    emoji_hold_duration: float | None = 0.5
    emoji_throw_speed_multiplier: float | None = 1.0
    emoji_throw_arc_height: float | None = 25.0
    emoji_throw_fall_distance: float | None = 153.6
    emoji_spin_speed: float | None = 45.0
    default_batch_size: int | None = 1
    batch_failure_mode: str | None = "stop_all"
    max_words: int | None = 400
    system_prompt: str | None = ""
    llm_temp_script: float | None = 0.7
    sentry_dsn: str | None = ""


class StateModel(BaseModel):
    """Active session state schema for the ``POST /api/state`` endpoint."""

    script_text: str
    bg_video_path: str | None = None
    bg_video_bottom_path: str | None = None
    selected_voice: str
    bg_music_path: str | None = None
    music_volume: float | None = None
    voice_volume: float | None = None
    sub_font: str | None = None
    sub_size: int | None = None
    sub_color: str | None = None
    sub_highlight: str | None = None
    sub_outline: str | None = None
    sub_outline_width: int | None = None
    sub_bold: bool | None = None
    word_pop: bool | None = None
    word_pop_scale: float | None = None
    inactive_dim: bool | None = None
    words_per_screen: str | None = None
    inactive_alpha: str | None = None
    enable_emojis: bool | None = None
    sub_uppercase: bool | None = None
    sub_border_style: int | None = None
    sub_shadow_width: int | None = None
    sub_bg_color: str | None = None
    sub_bg_alpha: str | None = None
    single_word_mode: bool | None = None
    emoji_position: str | None = None
    emoji_style: str | None = None
    enable_emoji_animation: bool | None = None
    emoji_scale_factor: float | None = None
    emoji_hold_duration: float | None = None
    emoji_throw_max_count: int | None = None
    voice_speed: float | None = None
    batch_num_shorts: int | None = None
    sub_animation_style: str | None = None
    # Advanced batch generation overrides (bound to the batch UI, persisted
    # alongside the rest of the session state).
    batch_layout: str | None = None
    batch_voice_id: str | None = None
    batch_sub_animation_style: str | None = None
    batch_words_per_screen: str | None = None
    batch_single_word_mode: bool | None = None
    batch_bg_music_path: str | None = None
    batch_script_temp: float | None = None
    batch_meta_temp: float | None = None
    batch_max_workers: int | None = None
    batch_llm_max_workers: int | None = None
    batch_post_to_tiktok: bool | None = None


class PexelsSearchRequest(BaseModel):
    """Request body for ``POST /api/pexels/search``."""

    query: str = Field(min_length=1)


class PexelsDownloadRequest(BaseModel):
    """Request body for ``POST /api/pexels/download``."""

    download_url: str
    video_id: int
    keyword: str
    position: str  # "top" or "bottom"


class YoutubeDownloadRequest(BaseModel):
    """Request body for ``POST /api/youtube/download``."""

    url: str
    downscale: bool = False


class YoutubeSearchRequest(BaseModel):
    """Request body for ``POST /api/youtube/search``."""

    query: str = Field(min_length=1)
    limit: int = 10


class FetchModelsRequest(BaseModel):
    """Request body for ``POST /api/llm/models``."""

    api_key: str | None = ""
    base_url: str | None = ""


class BatchStartRequest(BaseModel):
    """Request body for ``POST /api/batch/start``."""

    num_shorts: int = Field(default=5, ge=1, le=100)
    prompts: list[str] = []
    enable_emojis: bool | None = None
    enable_emoji_animation: bool | None = None
    emoji_scale_factor: float | None = None
    emoji_hold_duration: float | None = None
    emoji_throw_max_count: int | None = None
    emoji_styles: list[str] | None = None
    layout: str | None = None
    voice_id: str | None = None
    sub_animation_style: str | None = None
    words_per_screen: str | None = None
    single_word_mode: bool | None = None
    bg_music_path: str | None = None
    script_temp: float | None = None
    meta_temp: float | None = None
    max_workers: int | None = None
    llm_max_workers: int | None = None
    post_to_tiktok: bool | None = None
    tiktok_delays: dict[int, float] | None = None


class ScheduleModel(BaseModel):
    """Schedule for automated batch generation and TikTok posting.

    Defines a recurring batch job with configurable cadence (daily / weekly
    / every-N-hours), randomised timing via jitter and per-video stagger
    delays, and full batch-generation overrides.
    """

    id: str | None = None
    name: str = ""
    enabled: bool = True
    cadence: str = "daily"  # "daily" | "weekly" | "interval"
    times: list[str] = []  # HH:MM base times
    days: list[int] = []  # 1=Mon .. 7=Sun (weekly only)
    interval_hours: int = 3  # every N hours (interval cadence)
    interval_start: str = "08:00"  # HH:MM
    interval_end: str = "23:00"  # HH:MM
    jitter_minutes: int = 45
    stagger_enabled: bool = False
    stagger_min_minutes: int = 60
    stagger_max_minutes: int = 240
    post_to_tiktok: bool = True
    num_shorts: int = Field(default=5, ge=1, le=100)
    prompts: list[str] = []
    enable_emojis: bool = True
    enable_emoji_animation: bool = True
    emoji_scale_factor: float = 1.5
    emoji_hold_duration: float = 0.5
    emoji_throw_max_count: int = 3
    emoji_styles: list[str] | None = None
    layout: str | None = None
    voice_id: str | None = None
    sub_animation_style: str | None = None
    words_per_screen: str | None = None
    single_word_mode: bool | None = None
    bg_music_path: str | None = None
    script_temp: float | None = None
    meta_temp: float | None = None
    max_workers: int | None = None
    llm_max_workers: int | None = None
