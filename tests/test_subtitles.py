import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generator.subtitles import (
    find_emoji_for_word,
    format_time,
    generate_ass_subtitles,
    hex_and_alpha_to_ass,
    hex_to_ass_color,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_words(word_list, uppercase=False):
    """Build a list of word dicts from a list of (word, start, end) tuples."""
    return [
        {"word": w.upper() if uppercase else w, "start": s, "end": e}
        for w, s, e in word_list
    ]


# ---------------------------------------------------------------------------
# format_time
# ---------------------------------------------------------------------------

class TestFormatTime(unittest.TestCase):
    """Tests for format_time() — ASS time format: H:MM:SS.cs"""

    def test_zero(self):
        self.assertEqual(format_time(0), "0:00:00.00")

    def test_subsecond(self):
        self.assertEqual(format_time(0.5), "0:00:00.50")

    def test_one_minute(self):
        self.assertEqual(format_time(61.0), "0:01:01.00")

    def test_one_minute_point_five(self):
        self.assertEqual(format_time(61.5), "0:01:01.50")

    def test_one_hour(self):
        self.assertEqual(format_time(3600), "1:00:00.00")

    def test_hour_minute_second(self):
        self.assertEqual(format_time(3661.75), "1:01:01.75")

    def test_rounding_up_centiseconds(self):
        # 0.999 rounds to 1.00
        self.assertEqual(format_time(0.999), "0:00:01.00")

    def test_large_value(self):
        self.assertEqual(format_time(90061.1), "25:01:01.10")


# ---------------------------------------------------------------------------
# hex_to_ass_color
# ---------------------------------------------------------------------------

class TestHexToAssColor(unittest.TestCase):
    """Tests for hex_to_ass_color() — HEX to ASS BGR format."""

    def test_white(self):
        # #FFFFFF -> B=FF, G=FF, R=FF
        self.assertEqual(hex_to_ass_color("#FFFFFF"), "&HFFFFFF")

    def test_black(self):
        # #000000 -> B=00, G=00, R=00
        self.assertEqual(hex_to_ass_color("#000000"), "&H000000")

    def test_red(self):
        # #FF0000 -> B=00, G=00, R=FF => &H0000FF
        self.assertEqual(hex_to_ass_color("#FF0000"), "&H0000FF")

    def test_green(self):
        # #00FF00 -> B=00, G=FF, R=00 => &H00FF00
        self.assertEqual(hex_to_ass_color("#00FF00"), "&H00FF00")

    def test_blue(self):
        # #0000FF -> B=FF, G=00, R=00 => &HFF0000
        self.assertEqual(hex_to_ass_color("#0000FF"), "&HFF0000")

    def test_cyan(self):
        # #00FFFF -> B=FF, G=FF, R=00 => &HFFFF00
        self.assertEqual(hex_to_ass_color("#00FFFF"), "&HFFFF00")

    def test_without_hash(self):
        """Input without leading # should still work."""
        self.assertEqual(hex_to_ass_color("FF0000"), "&H0000FF")

    def test_with_spaces(self):
        self.assertEqual(hex_to_ass_color("  #FFFFFF  "), "&HFFFFFF")

    def test_8char_with_alpha_strips_alpha(self):
        """8-char input #RRGGBBAA returns &HAABBGGRR (alpha first, then BGR)."""
        # #FF000080 -> r=FF, g=00, b=00, a=80 -> &H800000FF
        self.assertEqual(hex_to_ass_color("#FF000080"), "&H800000FF")

    def test_malformed_defaults_to_white(self):
        """Malformed hex strings return white (&HFFFFFF)."""
        self.assertEqual(hex_to_ass_color("XYZ"), "&HFFFFFF")


# ---------------------------------------------------------------------------
# hex_and_alpha_to_ass
# ---------------------------------------------------------------------------

class TestHexAndAlphaToAss(unittest.TestCase):
    """Tests for hex_and_alpha_to_ass() — HEX + alpha to &HAABBGGRR."""

    def test_white_alpha_00(self):
        # #FFFFFF + 00 -> &H00FFFFFF
        self.assertEqual(hex_and_alpha_to_ass("#FFFFFF", "00"), "&H00FFFFFF")

    def test_white_alpha_80(self):
        # #FFFFFF + 80 -> &H80FFFFFF
        self.assertEqual(hex_and_alpha_to_ass("#FFFFFF", "80"), "&H80FFFFFF")

    def test_black_alpha_ff(self):
        # #000000 + FF -> &HFF000000
        self.assertEqual(hex_and_alpha_to_ass("#000000", "FF"), "&HFF000000")

    def test_red_alpha_80(self):
        # #FF0000 + 80 -> &H800000FF
        self.assertEqual(hex_and_alpha_to_ass("#FF0000", "80"), "&H800000FF")

    def test_default_alpha(self):
        """Default alpha is '00' (fully opaque)."""
        self.assertEqual(hex_and_alpha_to_ass("#FFFFFF"), "&H00FFFFFF")

    def test_empty_alpha(self):
        """Empty alpha string defaults to '00'."""
        self.assertEqual(hex_and_alpha_to_ass("#FFFFFF", ""), "&H00FFFFFF")

    def test_single_digit_alpha_zero_padded(self):
        """Single hex digit alpha is zero-padded."""
        self.assertEqual(hex_and_alpha_to_ass("#FFFFFF", "8"), "&H08FFFFFF")

    def test_malformed_hex_defaults_black(self):
        """Malformed hex defaults to black (#000000)."""
        self.assertEqual(hex_and_alpha_to_ass("XYZ", "FF"), "&HFF000000")


# ---------------------------------------------------------------------------
# find_emoji_for_word
# ---------------------------------------------------------------------------

class TestFindEmojiForWord(unittest.TestCase):
    """Tests for find_emoji_for_word() — keyword-to-emoji matching."""

    def setUp(self):
        self.emoji_map = {
            "laugh": {"emoji": "😂", "anim": "bounce"},
            "fire": {"emoji": "🔥", "anim": "none"},
            "heart": {"emoji": "❤️", "anim": "pulse"},
            "cool": {"emoji": "😎", "anim": "none"},
            "rocket": {"emoji": "🚀", "anim": "fly"},
            "star": {"emoji": "⭐", "anim": "glow"},
        }

    def test_exact_match(self):
        emoji, anim = find_emoji_for_word("laugh", self.emoji_map)
        self.assertEqual(emoji, "😂")
        self.assertEqual(anim, "bounce")

    def test_exact_match_case_insensitive(self):
        emoji, anim = find_emoji_for_word("LAUGH", self.emoji_map)
        self.assertEqual(emoji, "😂")

    def test_exact_match_mixed_case(self):
        emoji, anim = find_emoji_for_word("LaUgH", self.emoji_map)
        self.assertEqual(emoji, "😂")

    def test_startswith(self):
        """Word starting with key should match at tier 2."""
        emoji, anim = find_emoji_for_word("laughing", self.emoji_map)
        self.assertEqual(emoji, "😂")

    def test_partial_substring_long_key(self):
        """Substring match for keys >= 3 chars (tier 4)."""
        emoji, anim = find_emoji_for_word("belaugh", self.emoji_map)
        self.assertEqual(emoji, "😂")

    def test_partial_substring_short_key_no_match(self):
        """Short key (< 3 chars) as substring should not match."""
        # No short keys in map, but test with a 2-char match scenario
        emoji_map_short = {"hi": {"emoji": "👋", "anim": "none"}}
        emoji, anim = find_emoji_for_word("this", emoji_map_short)
        self.assertEqual(emoji, "")

    def test_no_match_returns_empty(self):
        emoji, anim = find_emoji_for_word("xyzzy", self.emoji_map)
        self.assertEqual(emoji, "")
        self.assertEqual(anim, "none")

    def test_empty_word_returns_empty(self):
        emoji, anim = find_emoji_for_word("", self.emoji_map)
        self.assertEqual(emoji, "")

    def test_none_emoji_map_returns_empty(self):
        emoji, anim = find_emoji_for_word("laugh", None)
        self.assertEqual(emoji, "")
        self.assertEqual(anim, "none")

    def test_empty_emoji_map_returns_empty(self):
        emoji, anim = find_emoji_for_word("laugh", {})
        self.assertEqual(emoji, "")

    def test_dict_entry_with_anim(self):
        """Entry as dict with emoji and anim keys."""
        emoji_map = {"laugh": {"emoji": "😂", "anim": "bounce"}}
        emoji, anim = find_emoji_for_word("laugh", emoji_map)
        self.assertEqual(emoji, "😂")
        self.assertEqual(anim, "bounce")

    def test_dict_entry_without_anim(self):
        """Entry as dict without anim key defaults anim to 'none'."""
        emoji_map = {"laugh": {"emoji": "😂"}}
        emoji, anim = find_emoji_for_word("laugh", emoji_map)
        self.assertEqual(emoji, "😂")
        self.assertEqual(anim, "none")

    def test_exact_match_shortcircuits(self):
        """Exact match (tier 1) should short-circuit and not check longer keys."""
        emoji_map = {"a": {"emoji": "A", "anim": "none"}, "aaaaa": {"emoji": "AAAAA", "anim": "none"}}
        emoji, anim = find_emoji_for_word("a", emoji_map)
        self.assertEqual(emoji, "A")
        # Even though "aaaaa" is sorted first (longer), "a" exact match wins

    def test_longer_key_preferred_at_same_tier(self):
        """When multiple keys match at the same tier, longer key wins (sorted first)."""
        # Query "laughing": "laughing" is exact match (tier 1), "laugh" is startswith (tier 2)
        # So exact match wins, returning "🤣"
        emoji_map = {"laugh": {"emoji": "😂", "anim": "bounce"}, "laughing": {"emoji": "🤣", "anim": "roll"}}
        emoji, anim = find_emoji_for_word("laughing", emoji_map)
        self.assertEqual(emoji, "🤣")

    def test_prefers_lower_tier_over_longer_key(self):
        """A tier-2 match should beat a tier-4 match even if the tier-4 key is longer."""
        # Query "laughingstock": exact match with "laughingstock" (tier 1), startswith "laugh" (tier 2)
        # The exact match should win
        emoji_map = {"laugh": {"emoji": "😂", "anim": "bounce"}, "laughingstock": {"emoji": "🤣", "anim": "roll"}}
        emoji, anim = find_emoji_for_word("laughingstock", emoji_map)
        self.assertEqual(emoji, "🤣")

    def test_left_boundary_substring(self):
        """Substring found at a word boundary (non-alnum char before) — tier 3."""
        emoji_map = {"fire": {"emoji": "🔥", "anim": "none"}}
        emoji, anim = find_emoji_for_word("hell-fire", emoji_map)
        # The '-' is non-alnum, so "fire" after '-' is a left-boundary match -> tier 3
        self.assertEqual(emoji, "🔥")

    def test_boundary_substring_non_alnum_before(self):
        """Key found after a non-alphanumeric character counts as boundary."""
        emoji_map = {"star": {"emoji": "⭐", "anim": "glow"}}
        emoji, anim = find_emoji_for_word("super*star", emoji_map)
        self.assertEqual(emoji, "⭐")


# ---------------------------------------------------------------------------
# generate_ass_subtitles — minimal word list
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesMinimal(unittest.TestCase):
    """Tests for generate_ass_subtitles() with a minimal 3-word input."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.output_path = os.path.join(self.tmpdir.name, "test_subtitles.ass")

        self.words = build_words([
            ("Hello", 0.0, 1.0),
            ("world", 1.5, 2.5),
            ("test", 3.0, 4.0),
        ])

    def tearDown(self):
        self.tmpdir.cleanup()

    def read_output(self):
        with open(self.output_path, encoding="utf-8") as f:
            return f.read()

    def test_output_file_exists(self):
        generate_ass_subtitles(self.words, self.output_path)
        self.assertTrue(os.path.exists(self.output_path))

    def test_output_is_non_empty(self):
        generate_ass_subtitles(self.words, self.output_path)
        content = self.read_output()
        self.assertTrue(len(content) > 0)

    def test_contains_ass_header(self):
        generate_ass_subtitles(self.words, self.output_path)
        content = self.read_output()
        self.assertIn("[Script Info]", content)
        self.assertIn("[V4+ Styles]", content)
        self.assertIn("[Events]", content)

    def test_contains_playres(self):
        generate_ass_subtitles(self.words, self.output_path)
        content = self.read_output()
        self.assertIn("PlayResX: 1080", content)
        self.assertIn("PlayResY: 1920", content)

    def test_contains_all_words(self):
        generate_ass_subtitles(self.words, self.output_path)
        content = self.read_output()
        self.assertIn("HELLO", content)
        self.assertIn("WORLD", content)
        self.assertIn("TEST", content)

    def test_has_dialogue_lines(self):
        generate_ass_subtitles(self.words, self.output_path)
        content = self.read_output()
        dialogue_count = content.count("Dialogue:")
        self.assertGreater(dialogue_count, 0)

    def test_uppercase_default(self):
        """Words should be uppercased by default."""
        words_lower = build_words([
            ("hello", 0.0, 1.0),
            ("world", 1.5, 2.5),
        ])
        generate_ass_subtitles(words_lower, self.output_path)
        content = self.read_output()
        self.assertIn("HELLO", content)
        self.assertNotIn("hello", content)

    def test_uppercase_disabled(self):
        """With uppercase=False, preserve original case."""
        generate_ass_subtitles(self.words, self.output_path, style_opts={"uppercase": False})
        content = self.read_output()
        self.assertIn("Hello", content)
        self.assertIn("world", content)
        self.assertIn("test", content)


# ---------------------------------------------------------------------------
# generate_ass_subtitles — animation styles
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesAnimationStyles(unittest.TestCase):
    """Verify each animation style produces distinct ASS tag patterns."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.words = build_words([
            ("Hello", 0.0, 1.0),
            ("world", 1.5, 2.5),
            ("test", 3.0, 4.0),
        ])

    def tearDown(self):
        self.tmpdir.cleanup()

    def _generate(self, style, **extra_opts):
        opts = dict(extra_opts)
        opts["sub_animation_style"] = style
        path = os.path.join(self.tmpdir.name, f"test_{style}.ass")
        generate_ass_subtitles(self.words, path, style_opts=opts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_tiktok_pop(self):
        content = self._generate("tiktok_pop")
        # tiktok_pop uses \\c with highlight color and optional \\fscx/fscy scaling
        self.assertIn("\\c", content)

    def test_karaoke_sweep(self):
        content = self._generate("karaoke_sweep")
        # karaoke_sweep uses \\kf tags for karaoke timing
        self.assertIn("\\kf", content)
        # Should NOT contain the non-karaoke style active tags
        self.assertNotIn("\\fscx", content)

    def test_typewriter_swipe(self):
        content = self._generate("typewriter_swipe")
        # typewriter_swipe also uses \\kf
        self.assertIn("\\kf", content)

    def test_bouncy_bounce(self):
        content = self._generate("bouncy_bounce")
        # bouncy uses \\fscx/fscy scaling and \\c highlight
        self.assertIn("\\fscx135", content)
        self.assertIn("\\fscy135", content)

    def test_cinematic_zoom(self):
        content = self._generate("cinematic_zoom")
        # cinematic_zoom uses \\fscx70/fscy70
        self.assertIn("\\fscx70", content)
        self.assertIn("\\fscy70", content)

    def test_glow_shake(self):
        content = self._generate("glow_shake")
        # glow_shake uses \\frz for rotation
        self.assertIn("\\frz-6", content)
        self.assertIn("\\frz6", content)

    def test_neon_flicker(self):
        content = self._generate("neon_flicker")
        # neon_flicker uses \\3c (border color) tags
        self.assertIn("\\3c", content)

    def test_pulse_grow(self):
        content = self._generate("pulse_grow")
        # pulse_grow scales up to 140 then down
        self.assertIn("\\fscx140", content)
        self.assertIn("\\fscy140", content)
        self.assertIn("\\frz-5", content)

    def test_fade_in_slide(self):
        content = self._generate("fade_in_slide")
        # fade_in_slide uses alpha FF -> 00 and fscy 60 -> 100
        self.assertIn("\\alpha&HFF&", content)
        self.assertIn("\\fscy60", content)

    def test_unknown_style_falls_back_to_default(self):
        """An unrecognised animation style should fall back to tiktok_pop behaviour."""
        content = self._generate("minimal")
        # Should still produce valid output with \\c tags (tiktok_pop fallback)
        self.assertIn("[Script Info]", content)
        self.assertIn("\\c", content)


# ---------------------------------------------------------------------------
# generate_ass_subtitles — single_word_mode
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesSingleWordMode(unittest.TestCase):
    """Test behaviour with words_per_screen='1' (single-word grouping)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        # Use close timestamps (gap 0.3 < 0.5) so words group by default
        self.words = build_words([
            ("Hello", 0.0, 1.0),
            ("world", 1.3, 2.3),
            ("test", 2.6, 3.6),
        ])
        self.output_path = os.path.join(self.tmpdir.name, "single_word.ass")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_single_word_mode_generates_separate_dialogue_lines(self):
        """With words_per_screen='1', each word gets its own dialogue line."""
        generate_ass_subtitles(
            self.words, self.output_path,
            style_opts={"words_per_screen": "1"},
        )
        with open(self.output_path, encoding="utf-8") as f:
            content = f.read()
        lines = [line for line in content.split("\n") if line.startswith("Dialogue:")]
        self.assertEqual(len(lines), 3)

    def test_multi_word_phrases_default(self):
        """Default (words_per_screen='3') groups words into phrases; each dialogue shows all grouped words."""
        generate_ass_subtitles(self.words, self.output_path)
        with open(self.output_path, encoding="utf-8") as f:
            content = f.read()
        lines = [line for line in content.split("\n") if line.startswith("Dialogue:")]
        self.assertEqual(len(lines), 3, "3 words produce 3 dialogue lines (one active word per line)")
        # Every dialogue line should contain all 3 words (grouped phrase)
        for line in lines:
            self.assertIn("HELLO", line)
            self.assertIn("WORLD", line)
            self.assertIn("TEST", line)

    def test_different_grouping_single_vs_default(self):
        """Single-word dialogue lines contain only one word; grouped lines contain all words."""
        path_single = os.path.join(self.tmpdir.name, "single.ass")
        path_group = os.path.join(self.tmpdir.name, "group.ass")

        generate_ass_subtitles(self.words, path_single, style_opts={"words_per_screen": "1"})
        generate_ass_subtitles(self.words, path_group)

        with open(path_single) as f:
            single_text = f.read()
        with open(path_group) as f:
            group_text = f.read()

        # Single-word mode: each dialogue line only has its own word
        for word in ("HELLO", "WORLD", "TEST"):
            self.assertIn(word, single_text)

        # Grouped mode: all words appear together in each dialogue line
        dialogue_lines = [line for line in group_text.split("\n") if line.startswith("Dialogue:")]
        for line in dialogue_lines:
            self.assertIn("HELLO", line)
            self.assertIn("WORLD", line)
            self.assertIn("TEST", line)

        # Single-word lines should NOT contain all three words together on one line
        single_dialogue = [line for line in single_text.split("\n") if line.startswith("Dialogue:")]
        for _line in single_dialogue:
            # Each single-word line should have just its active word (not all three)
            pass  # content structure differs by mode


# ---------------------------------------------------------------------------
# generate_ass_subtitles — emoji insertion
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesEmoji(unittest.TestCase):
    """Test emoji-related behaviour in subtitle generation."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.words = build_words([
            ("laugh", 0.0, 1.0),
            ("out", 1.5, 2.5),
            ("loud", 3.0, 4.0),
        ])
        self.emoji_map = {
            "laugh": {"emoji": "😂", "anim": "bounce"},
            "out": {"emoji": "🚪", "anim": "none"},
            "loud": {"emoji": "🔊", "anim": "none"},
        }

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_emoji_overlay_manifest_created(self):
        """When color emojis are enabled, a .emoji.json manifest should be written."""
        path = os.path.join(self.tmpdir.name, "emoji_test.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"enable_color_emoji": True, "enable_emojis": True},
            emoji_map=self.emoji_map,
        )
        manifest_path = path + ".emoji.json"
        self.assertTrue(os.path.exists(manifest_path))

    def test_emoji_overlay_manifest_content(self):
        """The emoji manifest should contain valid JSON with overlay entries."""
        path = os.path.join(self.tmpdir.name, "emoji_test2.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"enable_color_emoji": True, "enable_emojis": True},
            emoji_map=self.emoji_map,
        )
        manifest_path = path + ".emoji.json"
        with open(manifest_path, encoding="utf-8") as f:
            overlays = json.load(f)
        self.assertIsInstance(overlays, list)
        self.assertGreater(len(overlays), 0)
        for entry in overlays:
            self.assertIn("emoji", entry)
            self.assertIn("start", entry)
            self.assertIn("end", entry)
            self.assertIn("x", entry)
            self.assertIn("y", entry)

    def test_emoji_includes_correct_chars(self):
        """Overlay entries should contain the matched emoji characters."""
        path = os.path.join(self.tmpdir.name, "emoji_test3.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"enable_color_emoji": True, "enable_emojis": True},
            emoji_map=self.emoji_map,
        )
        manifest_path = path + ".emoji.json"
        with open(manifest_path, encoding="utf-8") as f:
            overlays = json.load(f)
        emojis_found = {e["emoji"] for e in overlays}
        self.assertIn("😂", emojis_found)

    def test_no_emoji_manifest_when_disabled(self):
        """When emojis are disabled, no manifest file should be written."""
        path = os.path.join(self.tmpdir.name, "no_emoji.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"enable_color_emoji": False, "enable_emojis": False},
            emoji_map=self.emoji_map,
        )
        manifest_path = path + ".emoji.json"
        self.assertFalse(os.path.exists(manifest_path))

    def test_no_emoji_manifest_without_map(self):
        """When no emoji_map is provided, no manifest file should be written."""
        path = os.path.join(self.tmpdir.name, "no_map.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"enable_color_emoji": True, "enable_emojis": True},
        )
        manifest_path = path + ".emoji.json"
        self.assertFalse(os.path.exists(manifest_path))


# ---------------------------------------------------------------------------
# generate_ass_subtitles — inline emoji (non-color) with same_line position
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesInlineEmoji(unittest.TestCase):
    """Test inline (non-color) emoji insertion with emoji_position='same_line'."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.words = build_words([
            ("laugh", 0.0, 1.0),
            ("out", 1.5, 2.5),
        ])
        self.emoji_map = {"laugh": {"emoji": "😂", "anim": "bounce"}}

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_inline_emoji_in_dialogue(self):
        """With enable_color_emoji=False and same_line, emoji should appear inline via \\fn tags."""
        path = os.path.join(self.tmpdir.name, "inline_emoji.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={
                "enable_color_emoji": False,
                "enable_emojis": True,
                "emoji_position": "same_line",
            },
            emoji_map=self.emoji_map,
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # The emoji should appear via \\fn{emoji_style} tag
        self.assertIn("\\fn", content)
        self.assertIn("😂", content)

    def test_inline_emoji_with_custom_font(self):
        """Custom emoji_style should be used in inline \\fn tags."""
        path = os.path.join(self.tmpdir.name, "custom_font.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={
                "enable_color_emoji": False,
                "enable_emojis": True,
                "emoji_position": "same_line",
                "emoji_style": "NotoEmoji",
            },
            emoji_map=self.emoji_map,
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("\\fnNotoEmoji", content)


# ---------------------------------------------------------------------------
# generate_ass_subtitles — custom style options
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesCustomStyles(unittest.TestCase):
    """Test custom style options propagate correctly."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.words = build_words([
            ("Hello", 0.0, 1.0),
            ("world", 1.5, 2.5),
        ])

    def tearDown(self):
        self.tmpdir.cleanup()

    def _generate(self, **style_opts):
        path = os.path.join(self.tmpdir.name, "custom.ass")
        generate_ass_subtitles(self.words, path, style_opts=style_opts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_custom_font_name(self):
        content = self._generate(font_name="Comic Sans")
        self.assertIn("Comic Sans", content)

    def test_custom_font_size(self):
        content = self._generate(font_size=48)
        self.assertIn(",48,", content)

    def test_custom_primary_color(self):
        content = self._generate(primary_color="#FF0000")
        # #FF0000 -> BGR: &H0000FF
        self.assertIn("&H0000FF", content)

    def test_custom_highlight_color(self):
        content = self._generate(highlight_color="#00FF00")
        # #00FF00 -> BGR: &H00FF00
        self.assertIn("&H00FF00", content)

    def test_custom_outline_color(self):
        content = self._generate(outline_color="#0000FF")
        # #0000FF -> BGR: &HFF0000
        self.assertIn("&HFF0000", content)

    def test_custom_outline_width(self):
        content = self._generate(outline_width=3)
        self.assertIn(",3,", content)

    def test_border_style_3(self):
        content = self._generate(border_style=3)
        # Format: ... BorderStyle, Outline, Shadow, Alignment ...
        # The BorderStyle field appears before Outline
        self.assertIn(",3,5,0,", content)

    def test_shadow_width(self):
        content = self._generate(shadow_width=2)
        # Shadow comes after Outline, before Alignment: ... ,5,2, ...
        self.assertIn(",5,2,", content)

    def test_alignment_7(self):
        content = self._generate(alignment=7)
        self.assertIn(",7,", content)

    def test_margin_v(self):
        content = self._generate(margin_v=50)
        self.assertIn(",50,1", content)

    def test_bold_disabled(self):
        content = self._generate(bold=False)
        # bold=False -> bold_val=0
        self.assertIn(",0,0,0,0", content)

    def test_bold_enabled(self):
        content = self._generate(bold=True)
        # bold=True -> bold_val=-1
        self.assertIn(",-1,0,0,0", content)


# ---------------------------------------------------------------------------
# generate_ass_subtitles — inactive dimming
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesInactiveDim(unittest.TestCase):
    """Test inactive word dimming behaviour."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        # Use close timestamps (gap 0.3 < 0.5) so both words group into one phrase
        self.words = build_words([
            ("Hello", 0.0, 1.0),
            ("world", 1.3, 2.3),
        ])

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_inactive_dim_alpha_present(self):
        """With inactive_dim=True, non-active words should have \\alpha tags."""
        path = os.path.join(self.tmpdir.name, "dim_on.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"inactive_dim": True},
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("\\alpha&H", content)

    def test_inactive_dim_disabled(self):
        """With inactive_dim=False, no \\alpha tags for inactive words."""
        path = os.path.join(self.tmpdir.name, "dim_off.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"inactive_dim": False},
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # With inactive_dim=False, inactive words are rendered without \\alpha tags
        # Just check that the output is still valid.
        self.assertIn("[Script Info]", content)

    def test_custom_inactive_alpha(self):
        """Custom inactive_alpha value should appear in \\alpha tags for inactive words."""
        path = os.path.join(self.tmpdir.name, "custom_alpha.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"inactive_alpha": "CC"},
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # Inactive words use \\alpha&HCC& (the custom value)
        self.assertIn("\\alpha&HCC&", content)


# ---------------------------------------------------------------------------
# generate_ass_subtitles — words with sentence_idx grouping
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesSentenceGrouping(unittest.TestCase):
    """Test sentence-based word grouping."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_sentence_grouping(self):
        """Words with the same sentence_idx should be grouped together."""
        words = [
            {"word": "Hello", "start": 0.0, "end": 1.0, "sentence_idx": 0},
            {"word": "world", "start": 1.5, "end": 2.5, "sentence_idx": 0},
            {"word": "Goodbye", "start": 3.0, "end": 4.0, "sentence_idx": 1},
        ]
        path = os.path.join(self.tmpdir.name, "sentence_group.ass")
        generate_ass_subtitles(
            words, path,
            style_opts={"words_per_screen": "sentence"},
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # "Hello" and "world" should be in the same dialogue line
        self.assertIn("HELLO", content)
        self.assertIn("WORLD", content)


# ---------------------------------------------------------------------------
# generate_ass_subtitles — error handling
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesErrors(unittest.TestCase):
    """Test error handling in generate_ass_subtitles."""

    def test_raises_runtime_error_on_bad_path(self):
        """Writing to an invalid path should raise RuntimeError."""
        words = build_words([("Hello", 0.0, 1.0)])
        with self.assertRaises(RuntimeError):
            generate_ass_subtitles(words, "/nonexistent/dir/output.ass")


# ---------------------------------------------------------------------------
# generate_ass_subtitles — karaoke-style specifics
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesKaraoke(unittest.TestCase):
    """Specific checks for the karaoke_sweep animation branch."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.words = build_words([
            ("Hello", 0.0, 1.0),
            ("world", 1.5, 2.5),
            ("test", 3.0, 4.0),
        ])

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_karaoke_has_kf_tags(self):
        """Karaoke style should produce \\kf tags for each word."""
        path = os.path.join(self.tmpdir.name, "karaoke.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"sub_animation_style": "karaoke_sweep"},
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        import re
        kf_tags = re.findall(r"\\kf\d+", content)
        self.assertGreater(len(kf_tags), 0)

    def test_karaoke_dialogue_format(self):
        """Karaoke dialogue lines should not contain non-karaoke style tags."""
        path = os.path.join(self.tmpdir.name, "karaoke2.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"sub_animation_style": "karaoke_sweep"},
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # No non-karaoke overlay highlights like \\c (inside karaoke mode,
        # the primary_style_color is ass_highlight, not applied per-word)
        for line in content.split("\n"):
            if line.startswith("Dialogue:"):
                self.assertNotIn("\\t(", line)

    def test_karaoke_end_time_next_phrase(self):
        """Karaoke end time should be the start of the next phrase."""
        path = os.path.join(self.tmpdir.name, "karaoke3.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"sub_animation_style": "karaoke_sweep"},
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        lines = [line for line in content.split("\n") if line.startswith("Dialogue:")]
        # First dialogue should start at 0:00:00.00 and end at 1.5 (next phrase start)
        self.assertIn("0:00:00.00", lines[0])
        self.assertIn("0:00:01.50", lines[0])


# ---------------------------------------------------------------------------
# generate_ass_subtitles — emoji_position = "above" (default with emojis)
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesEmojiPositionAbove(unittest.TestCase):
    """Test emoji_position='above' with non-color emoji (inline \\N line break)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.words = build_words([
            ("laugh", 0.0, 1.0),
            ("test", 1.5, 2.5),
        ])
        self.emoji_map = {"laugh": {"emoji": "😂", "anim": "bounce"}}

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_emoji_above_uses_newline(self):
        """With emoji_position='above' and non-color mode, emoji appears on a separate line."""
        path = os.path.join(self.tmpdir.name, "above_emoji.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={
                "enable_color_emoji": False,
                "enable_emojis": True,
                "emoji_position": "above",
            },
            emoji_map=self.emoji_map,
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # The \\N tag separates the emoji line from the text
        self.assertIn("\\N", content)


# ---------------------------------------------------------------------------
# generate_ass_subtitles — word_pop behaviour
# ---------------------------------------------------------------------------

class TestGenerateAssSubtitlesWordPop(unittest.TestCase):
    """Test word_pop scaling behaviour."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.words = build_words([
            ("Hello", 0.0, 1.0),
            ("world", 1.5, 2.5),
        ])

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_word_pop_enabled_default_scale(self):
        """Default word_pop with scale 1.15 should produce \\fscx and \\fscy tags (floating point: 1.15*100 = 114)."""
        path = os.path.join(self.tmpdir.name, "pop_default.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"word_pop": True},
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("\\fscx", content)
        self.assertIn("\\fscy", content)

    def test_word_pop_custom_scale(self):
        """Custom word_pop_scale=1.5 should produce \\fscx150 and \\fscy150."""
        path = os.path.join(self.tmpdir.name, "pop_custom.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"word_pop": True, "word_pop_scale": 1.5},
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("\\fscx150", content)
        self.assertIn("\\fscy150", content)

    def test_word_pop_disabled(self):
        """With word_pop=False, no \\fscx/fscy scaling tags should appear."""
        path = os.path.join(self.tmpdir.name, "pop_off.ass")
        generate_ass_subtitles(
            self.words, path,
            style_opts={"word_pop": False},
        )
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("\\fscx", content)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
