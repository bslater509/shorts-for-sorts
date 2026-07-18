"""Pydantic request/response models for the Shorts for Sorts API."""


from pydantic import BaseModel, Field


class SettingsModel(BaseModel):
    llm_profiles: list | None = []
    active_llm_profile_id: str | None = ""
    pexels_api_key: str | None = ""
    voice_speed: float | None = 1.0
    voice_volume: float | None = 1.0
    music_volume: float | None = 0.15
    local_whisper: bool | None = True
    local_whisper_model: str | None = "tiny"
    whisper_api_key: str | None = ""
    whisper_base_url: str | None = ""
    render_resolution: str | None = "720p"
    render_preset: str | None = "fast"
    video_encoder: str | None = "libx264"
    max_words: int | None = 400
    max_workers: int | None = 1
    llm_max_workers: int | None = 5
    words_per_screen: str | None = "3"
    sub_font: str | None = "Arial"
    sub_size: int | None = 72
    sub_color: str | None = "#FFFFFF"
    sub_highlight: str | None = "#00FFFF"
    sub_outline: str | None = "#000000"
    llm_temp_script: float | None = 0.7
    llm_temp_metadata: float | None = 0.7
    llm_temp_keywords: float | None = 0.7
    sub_outline_width: int | None = 5
    sub_bold: bool | None = True
    word_pop: bool | None = True
    word_pop_scale: float | None = 1.15
    inactive_dim: bool | None = True
    inactive_alpha: str | None = "88"
    enable_emojis: bool | None = True
    enable_color_emoji: bool | None = None
    sub_uppercase: bool | None = True
    sub_border_style: int | None = 1
    sub_shadow_width: int | None = 0
    sub_bg_color: str | None = "#000000"
    sub_bg_alpha: str | None = "80"
    single_word_mode: bool | None = False
    emoji_position: str | None = "above"
    emoji_style: str | None = "Symbola"
    sub_animation_style: str | None = "tiktok_pop"
    enable_emoji_animation: bool | None = True
    emoji_scale_factor: float | None = 1.5
    emoji_hold_duration: float | None = 0.5
    emoji_throw_speed_multiplier: float | None = 1.0
    emoji_throw_arc_height: float | None = 25.0
    emoji_throw_fall_distance: float | None = 153.6
    emoji_spin_speed: float | None = 45.0
    sentry_dsn: str | None = ""
    tiktok_sessionid: str | None = ""


class PresetModel(BaseModel):
    name: str
    selected_voice: str
    voice_speed: float
    bg_video_path: str | None = "random"
    bg_video_bottom_path: str | None = None
    bg_music_path: str | None = "music/default_music.mp3"
    music_volume: float
    voice_volume: float
    sub_font: str
    sub_size: int
    sub_color: str
    sub_highlight: str
    sub_outline: str
    sub_outline_width: int
    sub_bold: bool
    word_pop: bool
    word_pop_scale: float
    inactive_dim: bool
    inactive_alpha: str
    enable_emojis: bool
    enable_color_emoji: bool = True
    sub_animation_style: str
    single_word_mode: bool | None = False
    emoji_position: str | None = "above"
    sub_uppercase: bool | None = True
    sub_border_style: int | None = 1
    emoji_throw_speed_multiplier: float | None = 1.0
    emoji_throw_arc_height: float | None = 25.0
    emoji_throw_fall_distance: float | None = 153.6
    emoji_spin_speed: float | None = 45.0


class StateModel(BaseModel):
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
    enable_color_emoji: bool | None = None
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
    loaded_preset_name: str | None = None


class ScriptGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    selected_voice: str | None = None
    model_override: str | None = None


class PreviewAnimationRequest(BaseModel):
    settings: SettingsModel
    test_word: str | None = "Awesome"
    emoji_char: str | None = "🚀"


class PexelsSearchRequest(BaseModel):
    query: str = Field(min_length=1)


class LogMessageRequest(BaseModel):
    level: str
    message: str


class PexelsDownloadRequest(BaseModel):
    download_url: str
    video_id: int
    keyword: str
    position: str  # "top" or "bottom"


class YoutubeDownloadRequest(BaseModel):
    url: str
    downscale: bool = False


class YoutubeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = 10


class FetchModelsRequest(BaseModel):
    api_key: str | None = ""
    base_url: str | None = ""


class TiktokUploadRequest(BaseModel):
    filename: str
    description: str
    visibility: str = "Public"


class BatchStartRequest(BaseModel):
    num_shorts: int = Field(default=5, ge=1, le=100)
    prompts: list[str] = []
    enable_emojis: bool | None = None
    enable_emoji_animation: bool | None = None
    emoji_scale_factor: float | None = None
    emoji_hold_duration: float | None = None
    emoji_throw_max_count: int | None = None
    emoji_styles: list[str] | None = None
