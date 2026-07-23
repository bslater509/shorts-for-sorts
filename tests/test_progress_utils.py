import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gui.progress_utils import (
    get_progress_percentage,
    format_elapsed,
    make_progress_bar,
    log_memory_usage,
)


# ===================================================================
# get_progress_percentage
# ===================================================================
class TestGetProgressPercentage(unittest.TestCase):
    """Tests for gui.progress_utils.get_progress_percentage()."""

    def test_queued_returns_0(self):
        """'Queued' should return 0."""
        self.assertEqual(get_progress_percentage("Queued"), 0)

    def test_waiting_for_llm_returns_5(self):
        """'Waiting for LLM' should return 5."""
        self.assertEqual(get_progress_percentage("Waiting for LLM"), 5)

    def test_llm_script_50_words(self):
        """'LLM Script (50 words)' -> 5 + int((50/400)*9) = 6."""
        result = get_progress_percentage("LLM Script (50 words)")
        self.assertEqual(result, 6)

    def test_llm_script_400_words_max_within_range(self):
        """'LLM Script (400 words)' -> 14 (max before cap)."""
        result = get_progress_percentage("LLM Script (400 words)")
        self.assertEqual(result, 14)

    def test_llm_script_800_words_capped_at_14(self):
        """'LLM Script (800 words)' should be capped at 14."""
        result = get_progress_percentage("LLM Script (800 words)")
        self.assertEqual(result, 14)

    def test_llm_script_zero_words(self):
        """'LLM Script (0 words)' -> 5 + 0 = 5."""
        result = get_progress_percentage("LLM Script (0 words)")
        self.assertEqual(result, 5)

    def test_llm_script_no_match_returns_10(self):
        """'LLM Script' without word count should return 10."""
        result = get_progress_percentage("LLM Script (no match)")
        self.assertEqual(result, 10)

    def test_llm_metadata_returns_15(self):
        """'LLM Metadata' should return 15."""
        self.assertEqual(get_progress_percentage("LLM Metadata"), 15)

    def test_waiting_for_compilation_returns_20(self):
        """'Waiting for Compilation' should return 20."""
        self.assertEqual(get_progress_percentage("Waiting for Compilation"), 20)

    def test_voice_generation_3_of_5(self):
        """'Voice Generation (3/5)' -> 20 + int((3/5)*25) = 35."""
        result = get_progress_percentage("Voice Generation (3/5)")
        self.assertEqual(result, 35)

    def test_voice_generation_5_of_5(self):
        """'Voice Generation (5/5)' -> 20 + int((5/5)*25) = 45."""
        result = get_progress_percentage("Voice Generation (5/5)")
        self.assertEqual(result, 45)

    def test_voice_generation_0_of_5(self):
        """'Voice Generation (0/5)' -> 20 + 0 = 20."""
        result = get_progress_percentage("Voice Generation (0/5)")
        self.assertEqual(result, 20)

    def test_voice_generation_no_match_returns_30(self):
        """'Voice Generation' without fraction should return 30."""
        result = get_progress_percentage("Voice Generation")
        self.assertEqual(result, 30)

    def test_reusing_cache_voice_returns_45(self):
        """'Reusing Cache (Voice)' should return 45."""
        self.assertEqual(get_progress_percentage("Reusing Cache (Voice)"), 45)

    def test_compiling_returns_28(self):
        """'Compiling' should return 28."""
        self.assertEqual(get_progress_percentage("Compiling"), 28)

    def test_transcription_50_percent(self):
        """'Transcription (50%)' -> 45 + int((50/100)*10) = 50."""
        result = get_progress_percentage("Transcription (50%)")
        self.assertEqual(result, 50)

    def test_transcription_100_percent(self):
        """'Transcription (100%)' -> 45 + int((100/100)*10) = 55."""
        result = get_progress_percentage("Transcription (100%)")
        self.assertEqual(result, 55)

    def test_transcription_0_percent(self):
        """'Transcription (0%)' -> 45 + 0 = 45."""
        result = get_progress_percentage("Transcription (0%)")
        self.assertEqual(result, 45)

    def test_transcription_no_match_returns_48(self):
        """'Transcription' without percentage should return 48."""
        result = get_progress_percentage("Transcription")
        self.assertEqual(result, 48)

    def test_subtitles_returns_55(self):
        """'Subtitles' should return 55."""
        self.assertEqual(get_progress_percentage("Subtitles"), 55)

    def test_ffmpeg_rendering_50_percent(self):
        """'FFmpeg Rendering (50.0%)' -> 55 + int((50/100)*45) = 77."""
        result = get_progress_percentage("FFmpeg Rendering (50.0%)")
        self.assertEqual(result, 77)

    def test_ffmpeg_rendering_100_percent(self):
        """'FFmpeg Rendering (100.0%)' -> 55 + int((100/100)*45) = 100."""
        result = get_progress_percentage("FFmpeg Rendering (100.0%)")
        self.assertEqual(result, 100)

    def test_ffmpeg_rendering_0_percent(self):
        """'FFmpeg Rendering (0.0%)' -> 55 + 0 = 55."""
        result = get_progress_percentage("FFmpeg Rendering (0.0%)")
        self.assertEqual(result, 55)

    def test_ffmpeg_rendering_integer_percent(self):
        """'FFmpeg Rendering (75%)' (no decimal) should also match."""
        result = get_progress_percentage("FFmpeg Rendering (75%)")
        self.assertEqual(result, 55 + int((75 / 100) * 45))

    def test_ffmpeg_rendering_no_match_returns_75(self):
        """'FFmpeg Rendering' without percentage should return 75."""
        result = get_progress_percentage("FFmpeg Rendering")
        self.assertEqual(result, 75)

    def test_done_returns_100(self):
        """'Done' should return 100."""
        self.assertEqual(get_progress_percentage("Done"), 100)

    def test_failed_with_message_returns_none(self):
        """'Failed: something' should return None."""
        self.assertIsNone(get_progress_percentage("Failed: something"))

    def test_failed_returns_none(self):
        """'Failed' should return None."""
        self.assertIsNone(get_progress_percentage("Failed"))

    def test_failed_any_prefix(self):
        """Any status starting with 'Failed' should return None."""
        self.assertIsNone(get_progress_percentage("Failed: network error"))
        self.assertIsNone(get_progress_percentage("Failed: OOM"))

    def test_unknown_status_returns_0(self):
        """An unknown status should return 0."""
        self.assertEqual(get_progress_percentage("Unknown"), 0)

    def test_empty_status_returns_0(self):
        """An empty status should return 0."""
        self.assertEqual(get_progress_percentage(""), 0)

    def test_llm_script_boundary_below_400(self):
        """Just below 400 words should be less than 14."""
        result = get_progress_percentage("LLM Script (399 words)")
        # 5 + int((399/400)*9) = 5 + int(8.9775) = 5 + 8 = 13
        self.assertEqual(result, 13)

    def test_voice_generation_1_of_1(self):
        """'Voice Generation (1/1)' -> 20 + int((1/1)*25) = 45."""
        result = get_progress_percentage("Voice Generation (1/1)")
        self.assertEqual(result, 45)

    def test_voice_generation_2_of_10(self):
        """'Voice Generation (2/10)' -> 20 + int((2/10)*25) = 20 + 5 = 25."""
        result = get_progress_percentage("Voice Generation (2/10)")
        self.assertEqual(result, 25)


# ===================================================================
# format_elapsed
# ===================================================================
class TestFormatElapsed(unittest.TestCase):
    """Tests for gui.progress_utils.format_elapsed()."""

    def test_zero_seconds(self):
        """0 should return '0s'."""
        self.assertEqual(format_elapsed(0), "0s")

    def test_five_seconds(self):
        """5 should return '5s'."""
        self.assertEqual(format_elapsed(5), "5s")

    def test_one_minute_five_seconds(self):
        """65 -> '1m 05s'."""
        self.assertEqual(format_elapsed(65), "1m 05s")

    def test_sixty_minutes(self):
        """3600 -> '60m 00s'."""
        self.assertEqual(format_elapsed(3600), "60m 00s")

    def test_sixty_one_minutes(self):
        """3661 -> '61m 01s'."""
        self.assertEqual(format_elapsed(3661), "61m 01s")

    def test_negative_returns_0s(self):
        """Negative values should return '0s'."""
        self.assertEqual(format_elapsed(-5), "0s")

    def test_negative_zero(self):
        """-1 should return '0s'."""
        self.assertEqual(format_elapsed(-1), "0s")

    def test_exact_one_minute(self):
        """60 -> '1m 00s'."""
        self.assertEqual(format_elapsed(60), "1m 00s")

    def test_large_value(self):
        """7200 (2 hours) -> '120m 00s'."""
        self.assertEqual(format_elapsed(7200), "120m 00s")


# ===================================================================
# make_progress_bar
# ===================================================================
class TestMakeProgressBar(unittest.TestCase):
    """Tests for gui.progress_utils.make_progress_bar()."""

    def test_width_10_pct_50_in_progress(self):
        """width=10, pct=50, status='In Progress' should contain blocks, 50%, and status."""
        result = make_progress_bar(50, "In Progress", width=10)
        self.assertIn("█████", result)  # 5 filled blocks
        self.assertIn("░░░░░", result)  # 5 empty blocks
        self.assertIn("50%", result)
        self.assertIn("In Progress", result)

    def test_width_10_pct_100_done(self):
        """width=10, pct=100, status='Done' should contain ✓ Done and green markup."""
        result = make_progress_bar(100, "Done", width=10)
        self.assertIn("✓ Done", result)
        self.assertIn("green", result)
        self.assertIn("100%", result)

    def test_width_10_pct_0_queued(self):
        """width=10, pct=0, status='Queued' should contain Queued... and grey37."""
        result = make_progress_bar(0, "Queued", width=10)
        self.assertIn("Queued...", result)
        self.assertIn("grey37", result)
        self.assertIn("0%", result)

    def test_width_15_pct_33_default_width(self):
        """Default width=15, pct=33 should produce correct block count."""
        result = make_progress_bar(33, "Working", width=15)
        # int(15 * 33 / 100) = int(4.95) = 4 filled blocks
        self.assertIn("████", result)
        self.assertIn("░" * 11, result)

    def test_pct_0_always_zero_blocks(self):
        """pct=0 should produce zero filled blocks regardless of width."""
        result = make_progress_bar(0, "Test", width=20)
        self.assertNotIn("█", result)
        self.assertIn("░" * 20, result)

    def test_pct_100_all_filled(self):
        """pct=100 should fill all blocks."""
        result = make_progress_bar(100, "Test", width=8)
        self.assertIn("█" * 8, result)
        self.assertNotIn("░", result)

    def test_pct_above_100_capped(self):
        """pct > 100 should be treated as 100 (all filled)."""
        result = make_progress_bar(150, "Overflow", width=10)
        self.assertIn("█" * 10, result)
        self.assertNotIn("░", result)

    def test_pct_below_0_capped(self):
        """pct < 0 should be treated as 0 (no filled blocks)."""
        result = make_progress_bar(-10, "Negative", width=10)
        self.assertNotIn("█", result)
        self.assertIn("░" * 10, result)

    def test_returns_non_empty_string(self):
        """The returned string should be non-empty for valid inputs."""
        for pct in [0, 25, 50, 75, 100]:
            for status in ["Queued", "Working", "Done"]:
                result = make_progress_bar(pct, status)
                self.assertTrue(len(result) > 0, f"Empty result for pct={pct}, status={status}")

    def test_generic_status_contains_emoji(self):
        """A non-Done, non-Queued status should include the spinner emoji."""
        result = make_progress_bar(50, "Rendering")
        self.assertIn("🔄", result)

    def test_generic_status_yellow_and_cyan(self):
        """A non-Done, non-Queued status should use cyan bar and yellow text."""
        result = make_progress_bar(50, "Processing")
        self.assertIn("cyan", result)
        self.assertIn("yellow", result)


# ===================================================================
# log_memory_usage
# ===================================================================
class TestLogMemoryUsage(unittest.TestCase):
    """Tests for gui.progress_utils.log_memory_usage() — side-effect only."""

    @patch("gui.progress_utils.psutil.Process")
    @patch("gui.progress_utils.psutil.virtual_memory")
    @patch("gui.progress_utils.logger")
    def test_logs_stage_and_rss(self, mock_logger, mock_vm, mock_proc):
        """log_memory_usage('test stage') should call logger.info once
        with a message containing 'test stage' and 'RSS='."""
        # Configure mocks
        mock_proc_instance = mock_proc.return_value
        mock_proc_instance.memory_info.return_value.rss = 104857600  # 100 MB

        mock_vm.return_value.available = 524288000  # 500 MB
        mock_vm.return_value.total = 1073741824  # 1 GB
        mock_vm.return_value.percent = 50.0

        log_memory_usage("test stage")

        mock_logger.info.assert_called_once()
        msg = mock_logger.info.call_args[0][0]
        self.assertIn("test stage", msg)
        self.assertIn("RSS=", msg)
        self.assertIn("100MB", msg)

    @patch("gui.progress_utils.psutil.Process")
    @patch("gui.progress_utils.psutil.virtual_memory")
    @patch("gui.progress_utils.logger")
    def test_logs_memory_percent(self, mock_logger, mock_vm, mock_proc):
        """The log message should include the memory percent."""
        mock_proc_instance = mock_proc.return_value
        mock_proc_instance.memory_info.return_value.rss = 209715200  # 200 MB

        mock_vm.return_value.available = 268435456  # 256 MB
        mock_vm.return_value.total = 1073741824  # 1 GB
        mock_vm.return_value.percent = 75.0

        log_memory_usage("load assets")

        msg = mock_logger.info.call_args[0][0]
        self.assertIn("load assets", msg)
        self.assertIn("75.0%", msg)
        self.assertIn("RSS=200MB", msg)

    @patch("gui.progress_utils.psutil.Process")
    @patch("gui.progress_utils.psutil.virtual_memory")
    @patch("gui.progress_utils.logger")
    def test_logs_avail_memory(self, mock_logger, mock_vm, mock_proc):
        """The log message should include available memory."""
        mock_proc_instance = mock_proc.return_value
        mock_proc_instance.memory_info.return_value.rss = 0

        mock_vm.return_value.available = 1073741824  # 1 GB
        mock_vm.return_value.total = 2147483648  # 2 GB
        mock_vm.return_value.percent = 50.0

        log_memory_usage("startup")

        msg = mock_logger.info.call_args[0][0]
        self.assertIn("Avail=1024MB", msg)
        self.assertIn("/ 2048MB", msg)


if __name__ == "__main__":
    unittest.main()
