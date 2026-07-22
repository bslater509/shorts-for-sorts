"""Tests for Pydantic models in gui.models."""

import os
import sys
import unittest

from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gui.models import (
    BatchStartRequest,
    PexelsSearchRequest,
    PresetModel,
    SettingsModel,
)


class TestSettingsModel(unittest.TestCase):
    """Tests for SettingsModel — application settings."""

    def test_valid_typical(self):
        """Construct with a typical subset of fields."""
        settings = SettingsModel(
            llm_profiles=[{"id": "prof1", "name": "Profile 1"}],
            active_llm_profile_id="prof1",
            pexels_api_key="abc123",
            max_workers=4,
            voice_speed=1.25,
            render_resolution="1080p",
        )
        self.assertEqual(settings.llm_profiles, [{"id": "prof1", "name": "Profile 1"}])
        self.assertEqual(settings.active_llm_profile_id, "prof1")
        self.assertEqual(settings.pexels_api_key, "abc123")
        self.assertEqual(settings.max_workers, 4)
        self.assertEqual(settings.voice_speed, 1.25)
        self.assertEqual(settings.render_resolution, "1080p")

    def test_defaults(self):
        """All fields should have correct defaults when none are provided."""
        settings = SettingsModel()
        self.assertEqual(settings.llm_profiles, [])
        self.assertEqual(settings.active_llm_profile_id, "")
        self.assertEqual(settings.pexels_api_key, "")
        self.assertEqual(settings.voice_speed, 1.0)
        self.assertEqual(settings.voice_volume, 1.0)
        self.assertEqual(settings.music_volume, 0.15)
        self.assertTrue(settings.local_whisper)
        self.assertEqual(settings.local_whisper_model, "tiny")
        self.assertEqual(settings.whisper_api_key, "")
        self.assertEqual(settings.whisper_base_url, "")
        self.assertEqual(settings.render_resolution, "720p")
        self.assertEqual(settings.render_preset, "fast")
        self.assertEqual(settings.video_encoder, "libx264")
        self.assertEqual(settings.llm_max_workers, 5)
        self.assertEqual(settings.words_per_screen, "3")
        self.assertEqual(settings.sub_font, "Arial")
        self.assertEqual(settings.sub_size, 72)
        self.assertEqual(settings.sub_color, "#FFFFFF")
        self.assertEqual(settings.sub_highlight, "#00FFFF")
        self.assertEqual(settings.sub_outline, "#000000")
        self.assertEqual(settings.sub_outline_width, 5)
        self.assertTrue(settings.sub_bold)
        self.assertTrue(settings.word_pop)
        self.assertEqual(settings.word_pop_scale, 1.15)
        self.assertTrue(settings.inactive_dim)
        self.assertEqual(settings.inactive_alpha, "88")
        self.assertTrue(settings.enable_emojis)
        self.assertTrue(settings.sub_uppercase)
        self.assertEqual(settings.sub_border_style, 1)
        self.assertEqual(settings.sub_shadow_width, 0)
        self.assertEqual(settings.sub_bg_color, "#000000")
        self.assertEqual(settings.sub_bg_alpha, "80")
        self.assertFalse(settings.single_word_mode)
        self.assertEqual(settings.emoji_position, "above")
        self.assertEqual(settings.emoji_style, "Symbola")
        self.assertEqual(settings.sub_animation_style, "tiktok_pop")
        self.assertTrue(settings.enable_emoji_animation)
        self.assertEqual(settings.emoji_scale_factor, 1.5)
        self.assertEqual(settings.emoji_hold_duration, 0.5)
        self.assertEqual(settings.sentry_dsn, "")
        self.assertEqual(settings.tiktok_sessionid, "")

    def test_missing_optional_fields_use_defaults(self):
        """Omitting all optional fields should produce the default values."""
        settings = SettingsModel()
        # Spot-check a representative sample of defaults
        self.assertEqual(settings.llm_profiles, [])
        self.assertEqual(settings.active_llm_profile_id, "")
        self.assertEqual(settings.sub_font, "Arial")
        self.assertEqual(settings.sub_size, 72)


class TestPresetModel(unittest.TestCase):
    """Tests for PresetModel — preset configuration."""

    def test_valid_with_overrides(self):
        """Construct a valid PresetModel with all fields including overrides."""
        preset = PresetModel(
            name="My Preset",
            selected_voice="en-US-Wavenet-D",
            voice_speed=1.1,
            bg_video_path="/custom/bg.mp4",
            bg_video_bottom_path="/custom/bottom.mp4",
            bg_music_path="/custom/music.mp3",
            music_volume=0.3,
            voice_volume=0.9,
            sub_font="Comic Sans",
            sub_size=48,
            sub_color="#FF0000",
            sub_highlight="#00FF00",
            sub_outline="#0000FF",
            sub_outline_width=3,
            sub_bold=False,
            word_pop=False,
            word_pop_scale=1.0,
            inactive_dim=False,
            inactive_alpha="FF",
            enable_emojis=False,
            sub_animation_style="typewriter",
            single_word_mode=True,
            emoji_position="below",
            sub_uppercase=False,
            sub_border_style=2,
        )
        self.assertEqual(preset.name, "My Preset")
        self.assertEqual(preset.selected_voice, "en-US-Wavenet-D")
        self.assertEqual(preset.voice_speed, 1.1)
        self.assertEqual(preset.bg_video_path, "/custom/bg.mp4")
        self.assertEqual(preset.bg_video_bottom_path, "/custom/bottom.mp4")
        self.assertEqual(preset.bg_music_path, "/custom/music.mp3")
        self.assertEqual(preset.music_volume, 0.3)
        self.assertEqual(preset.voice_volume, 0.9)
        self.assertEqual(preset.sub_font, "Comic Sans")
        self.assertEqual(preset.sub_size, 48)
        self.assertEqual(preset.sub_color, "#FF0000")
        self.assertEqual(preset.sub_highlight, "#00FF00")
        self.assertEqual(preset.sub_outline, "#0000FF")
        self.assertEqual(preset.sub_outline_width, 3)
        self.assertFalse(preset.sub_bold)
        self.assertFalse(preset.word_pop)
        self.assertEqual(preset.word_pop_scale, 1.0)
        self.assertFalse(preset.inactive_dim)
        self.assertEqual(preset.inactive_alpha, "FF")
        self.assertFalse(preset.enable_emojis)
        self.assertEqual(preset.sub_animation_style, "typewriter")
        self.assertTrue(preset.single_word_mode)
        self.assertEqual(preset.emoji_position, "below")
        self.assertFalse(preset.sub_uppercase)
        self.assertEqual(preset.sub_border_style, 2)

    def test_missing_name_fails(self):
        """Omitting the required 'name' field should raise ValidationError."""
        with self.assertRaises(ValidationError):
            PresetModel(
                selected_voice="en-US-Wavenet-D",
                voice_speed=1.0,
                music_volume=0.15,
                voice_volume=1.0,
                sub_font="Arial",
                sub_size=72,
                sub_color="#FFFFFF",
                sub_highlight="#00FFFF",
                sub_outline="#000000",
                sub_outline_width=5,
                sub_bold=True,
                word_pop=True,
                word_pop_scale=1.15,
                inactive_dim=True,
                inactive_alpha="88",
                enable_emojis=True,
                sub_animation_style="tiktok_pop",
            )


class TestBatchStartRequest(unittest.TestCase):
    """Tests for BatchStartRequest — batch job start request."""

    def test_valid_default(self):
        """Construct with only defaults."""
        req = BatchStartRequest()
        self.assertEqual(req.num_shorts, 5)
        self.assertEqual(req.prompts, [])
        self.assertIsNone(req.enable_emojis)
        self.assertIsNone(req.enable_emoji_animation)
        self.assertIsNone(req.emoji_scale_factor)
        self.assertIsNone(req.emoji_hold_duration)
        self.assertIsNone(req.emoji_throw_max_count)

    def test_valid_explicit_fields(self):
        """Construct with all fields explicitly provided."""
        req = BatchStartRequest(
            num_shorts=10,
            prompts=["prompt1", "prompt2"],
            enable_emojis=True,
            enable_emoji_animation=False,
            emoji_scale_factor=2.0,
            emoji_hold_duration=1.0,
            emoji_throw_max_count=5,
        )
        self.assertEqual(req.num_shorts, 10)
        self.assertEqual(req.prompts, ["prompt1", "prompt2"])
        self.assertTrue(req.enable_emojis)
        self.assertFalse(req.enable_emoji_animation)
        self.assertEqual(req.emoji_scale_factor, 2.0)
        self.assertEqual(req.emoji_hold_duration, 1.0)
        self.assertEqual(req.emoji_throw_max_count, 5)

    def test_num_shorts_below_min_fails(self):
        """num_shorts < 1 should raise ValidationError (ge=1)."""
        with self.assertRaises(ValidationError):
            BatchStartRequest(num_shorts=0)
        with self.assertRaises(ValidationError):
            BatchStartRequest(num_shorts=-5)

    def test_num_shorts_above_max_fails(self):
        """num_shorts > 100 should raise ValidationError (le=100)."""
        with self.assertRaises(ValidationError):
            BatchStartRequest(num_shorts=101)

    def test_num_shorts_at_boundaries(self):
        """Boundary values (1 and 100) should be accepted."""
        req_low = BatchStartRequest(num_shorts=1)
        self.assertEqual(req_low.num_shorts, 1)
        req_high = BatchStartRequest(num_shorts=100)
        self.assertEqual(req_high.num_shorts, 100)


class TestPexelsSearchRequest(unittest.TestCase):
    """Tests for PexelsSearchRequest — Pexels video search."""

    def test_valid(self):
        """Construct with a non-empty query."""
        req = PexelsSearchRequest(query="cats")
        self.assertEqual(req.query, "cats")

    def test_empty_query_fails(self):
        """An empty string for query should raise ValidationError (min_length=1)."""
        with self.assertRaises(ValidationError):
            PexelsSearchRequest(query="")

    def test_whitespace_query_accepted(self):
        """A whitespace-only string is technically non-empty and should pass."""
        req = PexelsSearchRequest(query="  ")
        self.assertEqual(req.query, "  ")


if __name__ == "__main__":
    unittest.main()
