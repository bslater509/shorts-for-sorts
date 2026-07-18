import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generator.subtitles import (
    find_emoji_for_word,
    hex_and_alpha_to_ass,
    hex_to_ass_color,
)
from gui.config import load_emoji_map

# ---------------------------------------------------------------------------
# A small predictable emoji map used by find_emoji_for_word tests
# ---------------------------------------------------------------------------
SAMPLE_EMOJI_MAP = {
    "laugh": {"emoji": "😂", "anim": "bounce"},
    "laughing": {"emoji": "😆", "anim": "bounce"},
    "fire": {"emoji": "🔥", "anim": "bounce"},
    "science": {"emoji": "🧪", "anim": "fade"},
    "scientist": {"emoji": "🧪", "anim": "fade"},
    "star": {"emoji": "⭐", "anim": "pop_in"},
    "earth": {"emoji": "🌍", "anim": "fade"},
    "moon": {"emoji": "🌙", "anim": "float_up"},
}


# ===================================================================
# load_emoji_map
# ===================================================================
class TestLoadEmojiMap(unittest.TestCase):
    """Tests for gui.config.load_emoji_map()."""

    def test_returns_dict(self):
        """load_emoji_map() should return a dict."""
        result = load_emoji_map()
        self.assertIsInstance(result, dict)

    def test_map_not_empty(self):
        """The loaded emoji map should contain at least one entry."""
        result = load_emoji_map()
        self.assertGreater(len(result), 0)

    def test_known_keyword_has_emoji_entry(self):
        """A known keyword like 'science' should map to a dict with 'emoji'."""
        result = load_emoji_map()
        self.assertIn("science", result)
        entry = result["science"]
        self.assertIsInstance(entry, dict)
        self.assertIn("emoji", entry)
        self.assertIsInstance(entry["emoji"], str)
        self.assertGreater(len(entry["emoji"]), 0)

    def test_known_keyword_has_anim_entry(self):
        """Every entry should also have an 'anim' key."""
        result = load_emoji_map()
        for keyword, entry in result.items():
            with self.subTest(keyword=keyword):
                self.assertIn("anim", entry)
                self.assertIsInstance(entry["anim"], str)

    def test_emoji_file_missing_uses_default(self):
        """When the emojis.json file does not exist, load_emoji_map
        should fall back to the built-in DEFAULT_EMOJI_MAP."""
        with patch("gui.config.EMOJIS_FILE", "/tmp/nonexistent_emojis_test.json"):
            result = load_emoji_map()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)
        # The default map should include "laugh"
        self.assertIn("laugh", result)


# ===================================================================
# find_emoji_for_word
# ===================================================================
class TestFindEmojiForWord(unittest.TestCase):
    """Tests for generator.subtitles.find_emoji_for_word()."""

    def test_exact_match(self):
        """Exact keyword match should return the corresponding emoji."""
        emoji_char, anim = find_emoji_for_word("fire", SAMPLE_EMOJI_MAP)
        self.assertEqual(emoji_char, "🔥")
        self.assertEqual(anim, "bounce")

    def test_exact_match_case_insensitive(self):
        """Uppercase word should still match the lower-case key."""
        emoji_char, anim = find_emoji_for_word("LAUGH", SAMPLE_EMOJI_MAP)
        self.assertEqual(emoji_char, "😂")
        self.assertEqual(anim, "bounce")

    def test_partial_match_startswith(self):
        """A word that starts with a key should match (tier 2)."""
        emoji_char, anim = find_emoji_for_word("starlight", SAMPLE_EMOJI_MAP)
        # "starlight" starts with "star"
        self.assertEqual(emoji_char, "⭐")

    def test_partial_match_left_boundary_substring(self):
        """A word containing a key at a non-alnum boundary should match (tier 3)."""
        emoji_char, anim = find_emoji_for_word("the-stars", SAMPLE_EMOJI_MAP)
        # "star" appears after '-', a non-alnum boundary
        self.assertEqual(emoji_char, "⭐")

    def test_no_match_returns_empty_string(self):
        """A word not in the map should return ('', 'none')."""
        emoji_char, anim = find_emoji_for_word("xyzzy", SAMPLE_EMOJI_MAP)
        self.assertEqual(emoji_char, "")
        self.assertEqual(anim, "none")

    def test_empty_emoji_map(self):
        """An empty emoji map should always return ('', 'none')."""
        emoji_char, anim = find_emoji_for_word("fire", {})
        self.assertEqual(emoji_char, "")
        self.assertEqual(anim, "none")

    def test_exact_match_tier1_wins_over_longer_key(self):
        """An exact match (tier 1) should win even if a longer key also matches."""
        # "laughing" exactly matches "laughing" (not just "laugh")
        emoji_char, anim = find_emoji_for_word("laughing", SAMPLE_EMOJI_MAP)
        self.assertEqual(emoji_char, "😆")  # laughing → 😆, not 😂

    def test_longer_key_preferred_within_same_tier(self):
        """Within the same tier, the longest key should be preferred."""
        # "science" and "scientist" — "scientist" is longer, so
        # "scientist" should match "scientist" exactly
        emoji_char, anim = find_emoji_for_word("scientist", SAMPLE_EMOJI_MAP)
        self.assertEqual(emoji_char, "🧪")

    def test_non_alphanumeric_stripped(self):
        """Punctuation characters should be stripped before matching."""
        emoji_char, anim = find_emoji_for_word("fire!!!", SAMPLE_EMOJI_MAP)
        self.assertEqual(emoji_char, "🔥")


# ===================================================================
# hex_to_ass_color
# ===================================================================
class TestHexToAssColor(unittest.TestCase):
    """Tests for generator.subtitles.hex_to_ass_color()."""

    def test_white(self):
        """#FFFFFF should convert to &HFFFFFF (BGR swap of FFFFFF)."""
        self.assertEqual(hex_to_ass_color("#FFFFFF"), "&HFFFFFF")

    def test_black(self):
        """#000000 should convert to &H000000."""
        self.assertEqual(hex_to_ass_color("#000000"), "&H000000")

    def test_red_becomes_blue(self):
        """#FF0000 (red) should swap to BGR: &H0000FF."""
        self.assertEqual(hex_to_ass_color("#FF0000"), "&H0000FF")

    def test_green_stays_green(self):
        """#00FF00 (green) has identical RGB and BGR: &H00FF00."""
        self.assertEqual(hex_to_ass_color("#00FF00"), "&H00FF00")

    def test_blue_becomes_red(self):
        """#0000FF (blue) should swap to BGR: &HFF0000."""
        self.assertEqual(hex_to_ass_color("#0000FF"), "&HFF0000")

    def test_without_hash(self):
        """Hex string without # should also work."""
        self.assertEqual(hex_to_ass_color("FFFFFF"), "&HFFFFFF")

    def test_malformed_fallback(self):
        """Malformed hex should log a warning and fall back to white."""
        result = hex_to_ass_color("#XYZ")
        self.assertEqual(result, "&HFFFFFF")

    def test_8char_with_alpha(self):
        """8-character hex (#RRGGBBAA) should be handled with BGR + alpha."""
        # "#FF000080" -> r=FF, g=00, b=00, a=80 -> "&H800000FF"
        result = hex_to_ass_color("#FF000080")
        self.assertEqual(result, "&H800000FF")


# ===================================================================
# hex_and_alpha_to_ass
# ===================================================================
class TestHexAndAlphaToAss(unittest.TestCase):
    """Tests for generator.subtitles.hex_and_alpha_to_ass()."""

    def test_white_80(self):
        """#FFFFFF with alpha 80 -> &H80FFFFFF."""
        self.assertEqual(hex_and_alpha_to_ass("#FFFFFF", "80"), "&H80FFFFFF")

    def test_black_ff(self):
        """#000000 with alpha FF -> &HFF000000."""
        self.assertEqual(hex_and_alpha_to_ass("#000000", "FF"), "&HFF000000")

    def test_red_40(self):
        """#FF0000 with alpha 40 -> &H400000FF."""
        self.assertEqual(hex_and_alpha_to_ass("#FF0000", "40"), "&H400000FF")

    def test_default_alpha(self):
        """Default alpha (00) should produce &H00BBGGRR."""
        self.assertEqual(hex_and_alpha_to_ass("#FFFFFF"), "&H00FFFFFF")

    def test_single_char_alpha_padded(self):
        """Single hex digit alpha should be zero-padded."""
        self.assertEqual(hex_and_alpha_to_ass("#000000", "F"), "&H0F000000")

    def test_malformed_hex_fallback(self):
        """Malformed hex should use 000000 as fallback."""
        result = hex_and_alpha_to_ass("#XYZ", "80")
        self.assertEqual(result, "&H80000000")

    def test_alpha_empty_string(self):
        """Empty alpha string should default to 00."""
        self.assertEqual(hex_and_alpha_to_ass("#FFFFFF", ""), "&H00FFFFFF")


if __name__ == "__main__":
    unittest.main()
