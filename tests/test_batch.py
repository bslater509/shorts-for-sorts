import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gui.batch import (
    BatchJobConfig,
    get_progress_percentage,
    format_elapsed,
    make_progress_bar,
    ProgressConsole,
)


class TestBatchJobConfig(unittest.TestCase):
    """Tests for BatchJobConfig.from_dict()"""

    def test_from_dict_all_fields(self):
        """Create a dict with ALL fields (required + optional), verify every field maps correctly."""
        data = {
            "index": 3,
            "prompt": "Write a short about cats",
            "voice_id": "en-US-Wavenet-D",
            "bg_video_path": "/videos/bg.mp4",
            "bg_video_bottom_path": "/videos/bg_bottom.mp4",
            "bg_music_path": "/music/track.mp3",
            "music_volume": 0.5,
            "voice_volume": 0.8,
            "sub_font": "Comic Sans",
            "sub_size": 48,
            "sub_color": "#FF0000",
            "sub_highlight": "#00FF00",
            "sub_outline": "#0000FF",
            "sub_outline_width": 3,
            "sub_bold": True,
            "enable_emojis": True,
            "word_pop": True,
            "word_pop_scale": 1.2,
            "inactive_dim": True,
            "inactive_alpha": "CC",
            "voice_speed": 1.1,
            "sub_uppercase": False,
            "sub_border_style": 2,
            "sub_shadow_width": 1,
            "sub_bg_color": "#111111",
            "sub_bg_alpha": "60",
            "single_word_mode": True,
            "emoji_position": "below",
            "emoji_font": "NotoEmoji",
            "sub_animation_style": "typewriter",
            "script_temp": 0.9,
            "meta_temp": 0.5,
            "model": "gpt-4",
            "system_prompt": "You are a helpful assistant.",
            "generated_title": "Cats Are Cool",
            "generated_hashtags": "#cats #funny",
            "script_text": "Once upon a time...",
            "output_filename": "cats_3.mp4",
            "settings": {"active_llm_profile_id": "prof1", "llm_profiles": []},
        }

        cfg = BatchJobConfig.from_dict(data)

        # Required fields
        self.assertEqual(cfg.index, 3)
        self.assertEqual(cfg.prompt, "Write a short about cats")
        self.assertEqual(cfg.voice_id, "en-US-Wavenet-D")
        self.assertEqual(cfg.bg_video_path, "/videos/bg.mp4")
        self.assertEqual(cfg.output_filename, "cats_3.mp4")
        self.assertEqual(cfg.settings, {"active_llm_profile_id": "prof1", "llm_profiles": []})

        # Optional fields — all explicitly provided
        self.assertEqual(cfg.bg_video_bottom_path, "/videos/bg_bottom.mp4")
        self.assertEqual(cfg.bg_music_path, "/music/track.mp3")
        self.assertEqual(cfg.music_volume, 0.5)
        self.assertEqual(cfg.voice_volume, 0.8)
        self.assertEqual(cfg.sub_font, "Comic Sans")
        self.assertEqual(cfg.sub_size, 48)
        self.assertEqual(cfg.sub_color, "#FF0000")
        self.assertEqual(cfg.sub_highlight, "#00FF00")
        self.assertEqual(cfg.sub_outline, "#0000FF")
        self.assertEqual(cfg.sub_outline_width, 3)
        self.assertTrue(cfg.sub_bold)
        self.assertTrue(cfg.enable_emojis)
        self.assertTrue(cfg.word_pop)
        self.assertEqual(cfg.word_pop_scale, 1.2)
        self.assertTrue(cfg.inactive_dim)
        self.assertEqual(cfg.inactive_alpha, "CC")
        self.assertEqual(cfg.voice_speed, 1.1)
        self.assertFalse(cfg.sub_uppercase)
        self.assertEqual(cfg.sub_border_style, 2)
        self.assertEqual(cfg.sub_shadow_width, 1)
        self.assertEqual(cfg.sub_bg_color, "#111111")
        self.assertEqual(cfg.sub_bg_alpha, "60")
        self.assertTrue(cfg.single_word_mode)
        self.assertEqual(cfg.emoji_position, "below")
        self.assertEqual(cfg.emoji_font, "NotoEmoji")
        self.assertEqual(cfg.sub_animation_style, "typewriter")
        self.assertEqual(cfg.script_temp, 0.9)
        self.assertEqual(cfg.meta_temp, 0.5)
        self.assertEqual(cfg.model, "gpt-4")
        self.assertEqual(cfg.system_prompt, "You are a helpful assistant.")
        self.assertEqual(cfg.generated_title, "Cats Are Cool")
        self.assertEqual(cfg.generated_hashtags, "#cats #funny")
        self.assertEqual(cfg.script_text, "Once upon a time...")

    def test_from_dict_minimal(self):
        """Create a dict with ONLY required fields, verify optional fields get dataclass defaults."""
        data = {
            "index": 1,
            "prompt": "Hello world",
            "voice_id": "voice_abc",
            "bg_video_path": "bg.mp4",
            "output_filename": "out.mp4",
            "settings": {},
        }

        cfg = BatchJobConfig.from_dict(data)

        # Required fields
        self.assertEqual(cfg.index, 1)
        self.assertEqual(cfg.prompt, "Hello world")
        self.assertEqual(cfg.voice_id, "voice_abc")
        self.assertEqual(cfg.bg_video_path, "bg.mp4")
        self.assertEqual(cfg.output_filename, "out.mp4")
        self.assertEqual(cfg.settings, {})

        # Optional fields — should have defaults from the dataclass
        self.assertIsNone(cfg.bg_video_bottom_path)
        self.assertIsNone(cfg.bg_music_path)
        self.assertEqual(cfg.music_volume, 0.15)
        self.assertEqual(cfg.voice_volume, 1.0)
        self.assertEqual(cfg.sub_font, "Arial")
        self.assertEqual(cfg.sub_size, 72)
        self.assertEqual(cfg.sub_color, "#FFFFFF")
        self.assertEqual(cfg.sub_highlight, "#00FFFF")
        self.assertEqual(cfg.sub_outline, "#000000")
        self.assertEqual(cfg.sub_outline_width, 5)
        self.assertFalse(cfg.sub_bold)
        self.assertFalse(cfg.enable_emojis)
        self.assertFalse(cfg.word_pop)
        self.assertEqual(cfg.word_pop_scale, 1.0)
        self.assertFalse(cfg.inactive_dim)
        self.assertEqual(cfg.inactive_alpha, "FF")
        self.assertIsNone(cfg.voice_speed)
        self.assertTrue(cfg.sub_uppercase)
        self.assertEqual(cfg.sub_border_style, 1)
        self.assertEqual(cfg.sub_shadow_width, 0)
        self.assertEqual(cfg.sub_bg_color, "#000000")
        self.assertEqual(cfg.sub_bg_alpha, "80")
        self.assertFalse(cfg.single_word_mode)
        self.assertEqual(cfg.emoji_position, "above")
        self.assertEqual(cfg.emoji_font, "Symbola")
        self.assertEqual(cfg.sub_animation_style, "tiktok_pop")
        self.assertEqual(cfg.script_temp, 0.7)
        self.assertEqual(cfg.meta_temp, 0.7)
        self.assertEqual(cfg.model, "gpt-4o-mini")
        self.assertEqual(cfg.system_prompt, "")
        self.assertIsNone(cfg.generated_title)
        self.assertIsNone(cfg.generated_hashtags)
        self.assertIsNone(cfg.script_text)

    def test_from_dict_missing_required(self):
        """Omit a required field — verify TypeError is raised.

        The updated from_dict builds a kwargs dict from valid dataclass
        fields and passes it to the constructor, which raises TypeError
        when a required positional argument is missing.
        """
        data = {
            "index": 1,
            # "prompt" is intentionally omitted
            "voice_id": "voice_abc",
            "bg_video_path": "bg.mp4",
            "output_filename": "out.mp4",
            "settings": {},
        }

        with self.assertRaises(TypeError):
            BatchJobConfig.from_dict(data)

    def test_from_dict_unknown_field(self):
        """Include extra fields not in the dataclass — verify they are ignored (no error)."""
        data = {
            "index": 1,
            "prompt": "Hello",
            "voice_id": "v",
            "bg_video_path": "bg.mp4",
            "output_filename": "out.mp4",
            "settings": {},
            "extra_spam": "should be ignored",
            "another_unknown": 42,
        }

        # Should not raise any error
        cfg = BatchJobConfig.from_dict(data)

        # Verify known fields are still correct
        self.assertEqual(cfg.index, 1)
        self.assertEqual(cfg.prompt, "Hello")
        # Confirm the unknown fields are simply absent on the dataclass
        with self.assertRaises(AttributeError):
            _ = cfg.extra_spam


class TestGetProgressPercentage(unittest.TestCase):
    """Tests for get_progress_percentage()"""

    def test_queued_returns_zero(self):
        self.assertEqual(get_progress_percentage("Queued"), 0)

    def test_done_returns_100(self):
        self.assertEqual(get_progress_percentage("Done"), 100)

    def test_failed_returns_none(self):
        self.assertIsNone(get_progress_percentage("Failed: some reason"))

    def test_unknown_returns_zero(self):
        self.assertEqual(get_progress_percentage("SomeRandomStatus"), 0)

    def test_llm_script_returns_10(self):
        self.assertEqual(get_progress_percentage("LLM Script"), 10)
        self.assertEqual(get_progress_percentage("LLM Script (42 words)"), 5)
        self.assertEqual(get_progress_percentage("LLM Script (400 words)"), 14)

    def test_voice_generation_percentage(self):
        # 3/6 → 20 + int(3/6 * 25) = 20 + int(12.5) = 32
        result = get_progress_percentage("Voice Generation (3/6)")
        self.assertEqual(result, 32)

    def test_ffmpeg_rendering_percentage(self):
        # 50.0% → 55 + int(50/100 * 45) = 55 + int(22.5) = 77
        result = get_progress_percentage("FFmpeg Rendering (50.0%)")
        self.assertEqual(result, 77)


class TestProgressConsole(unittest.TestCase):
    """Tests for ProgressConsole.print()"""

    def setUp(self):
        self.p_dict = {}
        self.console = ProgressConsole(idx=1, p_dict=self.p_dict)

    def test_progress_console_voice_gen(self):
        self.console.print("Generating voice for sentence 3/8")
        self.assertEqual(self.p_dict[1], "Voice Generation (3/8)")

    def test_progress_console_transcription(self):
        self.console.print("Transcribing full audio file...")
        self.assertEqual(self.p_dict[1], "Transcription")

    def test_progress_console_subtitles(self):
        self.console.print("[3/4] Building subtitles...")
        self.assertEqual(self.p_dict[1], "Subtitles")

    def test_progress_console_ffmpeg(self):
        self.console.print("FFmpeg Rendering 73.5%")
        self.assertEqual(self.p_dict[1], "FFmpeg Rendering (73.5%)")

    def test_progress_console_cache_reuse(self):
        self.console.print("\u2139\ufe0f Found cached audio")
        self.assertEqual(self.p_dict[1], "Reusing Cache (Voice)")

    def test_progress_console_unrecognized_message(self):
        # p_dict starts empty; unrecognized messages should not create an entry
        self.console.print("Some random output")
        self.assertNotIn(1, self.p_dict)

    def test_progress_console_exception_safety(self):
        """If the Manager dict is broken/readonly, .print() should not crash."""
        # Simulate a broken dict-like object that raises on __setitem__
        class BrokenDict:
            def __setitem__(self, key, value):
                raise RuntimeError("Cannot write to readonly dict")
            def __getitem__(self, key):
                raise KeyError(key)
            def __contains__(self, key):
                return False

        broken = BrokenDict()
        console = ProgressConsole(idx=1, p_dict=broken)
        # Should not raise any exception
        console.print("Generating voice for sentence 1/5")
        console.print("Transcribing full audio file...")
        console.print("[3/4] Building subtitles...")
        console.print("FFmpeg Rendering 50.0%")
        console.print("\u2139\ufe0f Found cached audio")
        console.print("Some random garbage")

        # If we get here without exception, the test passes
        self.assertTrue(True)


class TestFormatElapsed(unittest.TestCase):
    """Tests for format_elapsed()"""

    def test_format_seconds(self):
        self.assertEqual(format_elapsed(30), "30s")

    def test_format_exactly_one_minute(self):
        self.assertEqual(format_elapsed(60), "1m 00s")

    def test_format_minutes_and_seconds(self):
        self.assertEqual(format_elapsed(95), "1m 35s")

    def test_format_zero(self):
        self.assertEqual(format_elapsed(0), "0s")


class TestMakeProgressBar(unittest.TestCase):
    """Tests for make_progress_bar()"""

    def test_make_progress_bar_done(self):
        result = make_progress_bar(100, "Done")
        self.assertIn("\u2713 Done", result)
        self.assertIn("100%", result)

    def test_make_progress_bar_queued(self):
        result = make_progress_bar(0, "Queued")
        self.assertIn("Queued...", result)
        self.assertIn("0%", result)

    def test_make_progress_bar_running(self):
        result = make_progress_bar(50, "Compiling")
        self.assertIn("50%", result)
        self.assertIn("Compiling...", result)


if __name__ == '__main__':
    unittest.main()
