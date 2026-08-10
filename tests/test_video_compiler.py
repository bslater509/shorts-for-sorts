import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gui.word_alignment import align_words_to_script as _align_words_to_script

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_words(word_list):
    """Build a list of word dicts from (word, start, end) tuples."""
    return [
        {"word": w, "start": s, "end": e}
        for w, s, e in word_list
    ]


# ---------------------------------------------------------------------------
# _align_words_to_script
# ---------------------------------------------------------------------------

class TestAlignWordsToScript(unittest.TestCase):
    """Tests for _align_words_to_script() — script-aligned transcription."""

    def test_exact_match_preserves_timing(self):
        """A verbatim transcript keeps every word and its timing."""
        words = build_words([
            ("Hello", 0.0, 0.5),
            ("world", 0.7, 1.2),
            ("test", 1.4, 2.0),
        ])
        aligned, stats = _align_words_to_script(words, "Hello world test")
        self.assertEqual(
            [w["word"] for w in aligned], ["Hello", "world", "test"]
        )
        self.assertEqual(
            [(w["start"], w["end"]) for w in aligned],
            [(0.0, 0.5), (0.7, 1.2), (1.4, 2.0)],
        )
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["corrected"], 0)
        self.assertEqual(stats["inserted"], 0)
        self.assertEqual(stats["removed"], 0)
        self.assertEqual(stats["match_pct"], 100.0)

    def test_homophone_corrected(self):
        """Mis-transcribed word is corrected to the script while keeping timing."""
        words = build_words([
            ("there", 0.0, 0.4),
            ("going", 0.6, 1.0),
            ("home", 1.2, 1.6),
            ("today", 1.8, 2.2),
        ])
        aligned, stats = _align_words_to_script(words, "Their going home today")
        self.assertEqual(
            [w["word"] for w in aligned], ["Their", "going", "home", "today"]
        )
        # Corrected word keeps the transcript timing.
        self.assertEqual(aligned[0]["start"], 0.0)
        self.assertEqual(aligned[0]["end"], 0.4)
        self.assertEqual(stats["corrected"], 1)
        self.assertEqual(stats["match_pct"], 75.0)

    def test_case_and_punctuation_normalized(self):
        """Transcript case/punctuation is normalised to the script text."""
        words = build_words([
            ("HELLO,", 0.0, 0.5),
            ("WORLD!", 0.7, 1.2),
        ])
        aligned, stats = _align_words_to_script(words, "hello world")
        self.assertEqual([w["word"] for w in aligned], ["hello", "world"])
        self.assertEqual(stats["corrected"], 0)
        self.assertEqual(stats["match_pct"], 100.0)

    def test_dropped_word_inserted_with_interpolated_timing(self):
        """A script word missing from the transcript is inserted between anchors."""
        words = build_words([
            ("This", 0.0, 0.5),
            ("is", 0.7, 1.0),
            ("test", 1.3, 1.8),
        ])
        aligned, stats = _align_words_to_script(words, "This is a test")
        self.assertEqual([w["word"] for w in aligned], ["This", "is", "a", "test"])
        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(stats["removed"], 0)
        # Inserted word lands between the previous anchor end and next start.
        self.assertGreaterEqual(aligned[2]["start"], words[1]["end"])
        self.assertLessEqual(aligned[2]["end"], words[2]["start"])
        self.assertAlmostEqual(aligned[2]["start"], 1.15)
        self.assertAlmostEqual(aligned[2]["end"], 1.3)

    def test_extra_word_removed(self):
        """Hallucinated/duplicated transcript words are dropped."""
        words = build_words([
            ("This", 0.0, 0.5),
            ("um", 0.5, 0.7),
            ("is", 0.7, 1.0),
            ("a", 1.1, 1.4),
            ("test", 1.6, 2.0),
        ])
        aligned, stats = _align_words_to_script(words, "This is a test")
        self.assertEqual([w["word"] for w in aligned], ["This", "is", "a", "test"])
        self.assertEqual(stats["removed"], 1)
        self.assertEqual(stats["inserted"], 0)
        self.assertEqual(aligned[1]["start"], 0.7)  # "is" keeps its timing

    def test_script_tags_stripped(self):
        """[tag] directives in the script are stripped and never emitted."""
        words = build_words([
            ("Hello", 0.0, 0.5),
            ("world", 0.7, 1.2),
        ])
        aligned, stats = _align_words_to_script(words, "Hello [pause=1] world")
        self.assertEqual([w["word"] for w in aligned], ["Hello", "world"])
        self.assertNotIn("pause", [w["word"] for w in aligned])
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["match_pct"], 100.0)

    def test_short_transcript_returns_unchanged(self):
        """A single-word transcript is returned untouched (guard rail)."""
        words = build_words([("Hello", 0.0, 0.5)])
        aligned, stats = _align_words_to_script(words, "Hello")
        self.assertIs(aligned, words)
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["match_pct"], 0.0)

    def test_empty_script_returns_unchanged(self):
        """A script with no tokens is returned untouched (guard rail)."""
        words = build_words([
            ("Hello", 0.0, 0.5),
            ("world", 0.7, 1.2),
        ])
        aligned, _stats = _align_words_to_script(words, "")
        self.assertIs(aligned, words)


if __name__ == "__main__":
    unittest.main()
