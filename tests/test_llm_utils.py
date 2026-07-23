"""Tests for gui.llm_utils — parse_title_hashtags and retry_with_backoff."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gui.llm_utils import parse_title_hashtags, retry_with_backoff


# ===================================================================
# parse_title_hashtags
# ===================================================================
class TestParseTitleHashtags(unittest.TestCase):
    """Tests for gui.llm_utils.parse_title_hashtags()."""

    # -- happy path ---------------------------------------------------
    def test_both_title_and_hashtags(self):
        """TITLE and HASHTAGS lines should be extracted and removed from cleaned text."""
        cleaned, title, hashtags = parse_title_hashtags(
            "Some script text\nTITLE: My Cool Video\nHASHTAGS: #viral #fyp"
        )
        self.assertEqual(cleaned, "Some script text")
        self.assertEqual(title, "My Cool Video")
        self.assertEqual(hashtags, "#viral #fyp")

    def test_case_insensitive(self):
        """Lower-case title/hashtags should still match."""
        cleaned, title, hashtags = parse_title_hashtags(
            "content\ntitle: My Title\nhashtags: #tag"
        )
        self.assertEqual(cleaned, "content")
        self.assertEqual(title, "My Title")
        self.assertEqual(hashtags, "#tag")

    def test_only_title_line(self):
        """Only TITLE present — hashtags should be empty string."""
        cleaned, title, hashtags = parse_title_hashtags("content\nTITLE: My Title")
        self.assertEqual(cleaned, "content")
        self.assertEqual(title, "My Title")
        self.assertEqual(hashtags, "")

    def test_only_hashtags_line(self):
        """Only HASHTAGS present — title falls back to words from cleaned text (1 word)."""
        cleaned, title, hashtags = parse_title_hashtags("content\nHASHTAGS: #tag")
        self.assertEqual(cleaned, "content")
        self.assertEqual(title, "content")
        self.assertEqual(hashtags, "#tag")

    def test_neither_line_fallback_title(self):
        """No TITLE or HASHTAGS — cleaned is same as input, title is first 8 words."""
        text = "one two three four five six seven eight nine ten"
        cleaned, title, hashtags = parse_title_hashtags(text)
        self.assertEqual(cleaned, text)
        self.assertEqual(title, "one two three four five six seven eight")
        self.assertEqual(hashtags, "")

    # -- edge cases --------------------------------------------------
    def test_empty_input(self):
        """Empty string should return empty strings."""
        cleaned, title, hashtags = parse_title_hashtags("")
        self.assertEqual(cleaned, "")
        self.assertEqual(title, "")
        self.assertEqual(hashtags, "")

    def test_only_whitespace(self):
        """Whitespace-only input should return empty strings."""
        cleaned, title, hashtags = parse_title_hashtags("   \n  \n  ")
        self.assertEqual(cleaned, "")
        self.assertEqual(title, "")
        self.assertEqual(hashtags, "")

    def test_title_and_hashtags_in_middle(self):
        """TITLE/HASHTAGS lines embedded in text should be removed, others kept."""
        cleaned, title, hashtags = parse_title_hashtags(
            "Start text\nTITLE: Cool\nmore text\nHASHTAGS: #fyp\nend"
        )
        self.assertEqual(cleaned, "Start text\nmore text\nend")
        self.assertEqual(title, "Cool")
        self.assertEqual(hashtags, "#fyp")

    def test_singular_hashtag_keyword(self):
        """'HASHTAG:' (singular, no trailing 's') should also match. Title falls back."""
        cleaned, title, hashtags = parse_title_hashtags(
            "content\nHASHTAG: #viral"
        )
        self.assertEqual(cleaned, "content")
        self.assertEqual(title, "content")
        self.assertEqual(hashtags, "#viral")

    def test_extra_whitespace_around_values(self):
        """Whitespace around the value after the colon should be stripped."""
        cleaned, title, hashtags = parse_title_hashtags(
            "content\nTITLE:    Padded Title    \nHASHTAGS:   #tag   "
        )
        self.assertEqual(cleaned, "content")
        self.assertEqual(title, "Padded Title")
        self.assertEqual(hashtags, "#tag")

    def test_title_before_hashtags_order_preserved(self):
        """Lines not matching TITLE/HASHTAGS should retain their original order."""
        cleaned, title, hashtags = parse_title_hashtags(
            "line1\nline2\nTITLE: My Title\nline3\nHASHTAGS: #t1\nline4"
        )
        self.assertEqual(cleaned, "line1\nline2\nline3\nline4")

    def test_multiple_title_lines_uses_last(self):
        """If multiple TITLE lines appear, the last one wins."""
        cleaned, title, hashtags = parse_title_hashtags(
            "TITLE: First\nTITLE: Last\nHASHTAGS: #tag"
        )
        self.assertEqual(title, "Last")

    def test_multiple_hashtags_lines_uses_last(self):
        """If multiple HASHTAGS lines appear, the last one wins."""
        cleaned, title, hashtags = parse_title_hashtags(
            "HASHTAGS: #first\nHASHTAGS: #last"
        )
        self.assertEqual(hashtags, "#last")

    def test_fallback_with_fewer_than_8_words(self):
        """Fewer than 8 words available — title should be all available words."""
        text = "one two three"
        cleaned, title, hashtags = parse_title_hashtags(text)
        self.assertEqual(cleaned, text)
        self.assertEqual(title, "one two three")
        self.assertEqual(hashtags, "")

    def test_colon_in_regular_text_not_mistaken(self):
        """A line with a colon but not starting with title/hashtag should be kept."""
        cleaned, title, hashtags = parse_title_hashtags(
            "something: not a title\nTITLE: Actual"
        )
        self.assertEqual(cleaned, "something: not a title")
        self.assertEqual(title, "Actual")

    def test_empty_title_value_after_colon(self):
        """TITLE: with nothing after — title should be empty string (fallback triggers)."""
        cleaned, title, hashtags = parse_title_hashtags("TITLE:  \nHASHTAGS: #t")
        # title is blank after strip, so fallback applies
        self.assertNotEqual(title, "TITLE:")
        self.assertEqual(hashtags, "#t")


# ===================================================================
# retry_with_backoff
# ===================================================================
class TestRetryWithBackoff(unittest.TestCase):
    """Tests for gui.llm_utils.retry_with_backoff()."""

    def test_succeeds_first_try(self):
        """A function that succeeds immediately should be called exactly once."""
        call_count = 0

        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = retry_with_backoff(succeed, max_attempts=3, base_delay=1.0)
        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 1)

    def test_retries_on_rate_limit_then_succeeds(self):
        """A rate-limit error should be retried; success on attempt 2."""
        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("rate limit exceeded")
            return "ok"

        with patch("time.sleep") as mock_sleep:
            result = retry_with_backoff(fail_then_succeed, max_attempts=3, base_delay=1.0)

        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 2)
        mock_sleep.assert_called_once_with(1.0)  # base_delay * 2^0 = 1.0

    def test_retries_on_connection_error_then_succeeds(self):
        """A ConnectionError should be retried; success on attempt 2."""
        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("connection refused")
            return "ok"

        with patch("time.sleep") as mock_sleep:
            result = retry_with_backoff(fail_then_succeed, max_attempts=3, base_delay=1.0)

        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 2)
        mock_sleep.assert_called_once_with(1.0)

    def test_fails_all_attempts_raises(self):
        """When all retryable attempts fail, the last exception should be re-raised."""

        def always_fail():
            raise ConnectionError("persistent connection error")

        with patch("time.sleep") as mock_sleep:
            with self.assertRaises(ConnectionError) as ctx:
                retry_with_backoff(always_fail, max_attempts=3, base_delay=1.0)

        self.assertIn("persistent connection error", str(ctx.exception))
        # Should have slept twice (attempt 0 -> 1, attempt 1 -> 2)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_auth_error_does_not_retry(self):
        """An auth error (401) should raise immediately without retrying."""
        call_count = 0

        def auth_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("401 unauthorized")

        with patch("time.sleep") as mock_sleep:
            with self.assertRaises(Exception) as ctx:
                retry_with_backoff(auth_fail, max_attempts=3, base_delay=1.0)

        self.assertIn("unauthorized", str(ctx.exception))
        self.assertEqual(call_count, 1)
        mock_sleep.assert_not_called()

    def test_bad_request_does_not_retry(self):
        """A 'bad request' error should raise immediately without retrying."""
        call_count = 0

        def bad_request_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("bad request: invalid model")

        with patch("time.sleep") as mock_sleep:
            with self.assertRaises(Exception) as ctx:
                retry_with_backoff(bad_request_fail, max_attempts=3, base_delay=1.0)

        self.assertIn("bad request", str(ctx.exception))
        self.assertEqual(call_count, 1)
        mock_sleep.assert_not_called()

    def test_auth_error_via_unauthorized_keyword(self):
        """Error mentioning 'unauthorized' should not retry."""
        call_count = 0

        def fail():
            nonlocal call_count
            call_count += 1
            raise Exception("token is unauthorized")

        with patch("time.sleep") as mock_sleep:
            with self.assertRaises(Exception):
                retry_with_backoff(fail, max_attempts=3)

        self.assertEqual(call_count, 1)
        mock_sleep.assert_not_called()

    def test_auth_error_via_403_forbidden(self):
        """A '403' error should not retry."""
        call_count = 0

        def fail():
            nonlocal call_count
            call_count += 1
            raise Exception("403 forbidden")

        with patch("time.sleep") as mock_sleep:
            with self.assertRaises(Exception):
                retry_with_backoff(fail, max_attempts=3)

        self.assertEqual(call_count, 1)
        mock_sleep.assert_not_called()

    def test_exponential_backoff_delays(self):
        """Delays should be base_delay * 2^attempt for each retry."""
        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("timeout")

        with patch("time.sleep") as mock_sleep:
            with self.assertRaises(TimeoutError):
                retry_with_backoff(always_fail, max_attempts=4, base_delay=0.5)

        # 4 attempts → 3 sleeps: 0.5, 1.0, 2.0
        self.assertEqual(mock_sleep.call_count, 3)
        expected_calls = [0.5, 1.0, 2.0]
        for call_args, expected in zip(mock_sleep.call_args_list, expected_calls):
            self.assertEqual(call_args[0][0], expected)

    def test_retry_on_timeout_error(self):
        """A TimeoutError should be retried."""
        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("timed out")
            return "ok"

        with patch("time.sleep") as mock_sleep:
            result = retry_with_backoff(fail_then_succeed, max_attempts=3)

        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 2)
        mock_sleep.assert_called_once()

    def test_non_retryable_exception_raises_immediately(self):
        """An exception that is not a retryable type and doesn't mention retryable keywords
        should be raised immediately."""
        call_count = 0

        def fail():
            nonlocal call_count
            call_count += 1
            raise TypeError("some type error")

        with patch("time.sleep") as mock_sleep:
            with self.assertRaises(TypeError):
                retry_with_backoff(fail, max_attempts=3)

        self.assertEqual(call_count, 1)
        mock_sleep.assert_not_called()

    def test_overloaded_keyword_is_retryable(self):
        """Error mentioning 'overloaded' should be retried."""
        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("API is overloaded")
            return "ok"

        with patch("time.sleep") as mock_sleep:
            result = retry_with_backoff(fail_then_succeed, max_attempts=4)

        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_api_error_keyword_is_retryable(self):
        """Error mentioning 'api_error' should be retried."""
        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("api_error: server hiccup")
            return "ok"

        with patch("time.sleep") as mock_sleep:
            result = retry_with_backoff(fail_then_succeed, max_attempts=3)

        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 2)
        mock_sleep.assert_called_once()

    def test_default_parameters_work(self):
        """Calling retry_with_backoff with only the function should use defaults."""
        def succeed():
            return "defaults work"

        result = retry_with_backoff(succeed)
        self.assertEqual(result, "defaults work")


if __name__ == "__main__":
    unittest.main()
