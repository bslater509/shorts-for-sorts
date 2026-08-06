"""LLM utility functions — retry with exponential backoff and title/hashtag parsing."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from gui.config import logger
from gui.exceptions import BatchCancelledError

# --- Constants ---

DEFAULT_MAX_ATTEMPTS: int = 3
"""Default number of retry attempts for :func:`retry_with_backoff`."""

DEFAULT_BASE_DELAY: float = 1.0
"""Default base delay in seconds for exponential backoff."""

MAX_TITLE_WORDS: int = 8
"""Maximum number of words for the fallback title."""

# Patterns for non-retryable errors
NON_RETRYABLE_PATTERNS: tuple[str, ...] = (
    "bad request",
    "auth",
    "unauthorized",
    "401",
    "403",
)

# Keywords that indicate a retryable transient error
RETRYABLE_KEYWORDS: tuple[str, ...] = (
    "rate",
    "timeout",
    "connection",
    "overloaded",
    "api_error",
)

# Regex for TITLE/HASHTAGS lines
TITLE_RE: re.Pattern = re.compile(r"^title\s*:\s*(.*)", re.I)
HASHTAGS_RE: re.Pattern = re.compile(r"^hashtags?\s*:\s*(.*)", re.I)


# --- Public API ---


def retry_with_backoff(
    func: Callable[[], Any],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
) -> Any:
    """Retry a callable on transient errors with exponential backoff.

    Retries on :class:`ConnectionError`, :class:`TimeoutError`, and
    exceptions whose message contains retryable keywords (e.g.
    ``"rate"``, ``"timeout"``, ``"overloaded"``).  Does **not** retry
    on bad-request or auth errors (those are configuration problems).

    Args:
        func: The zero-argument callable to execute.
        max_attempts: Maximum number of attempts before giving up.
        base_delay: Base delay in seconds (doubled after each retry).

    Returns:
        The return value of ``func`` on success.

    Raises:
        Exception: The last exception encountered if all attempts fail,
            or immediately if a non-retryable error occurs.
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except BatchCancelledError:
            raise
        except Exception as e:
            err_str: str = str(e).lower()

            # Never retry bad-request / auth errors
            if _is_non_retryable(err_str):
                raise

            is_retryable: bool = isinstance(
                e, (ConnectionError, TimeoutError)
            ) or any(w in err_str for w in RETRYABLE_KEYWORDS)

            if not is_retryable or attempt == max_attempts - 1:
                raise

            delay: float = base_delay * (2**attempt)
            time.sleep(delay)

    # Should not be reached (the last attempt re-raises), but keep the type checker happy
    raise RuntimeError("Unexpected exit from retry loop")


def parse_title_hashtags(
    script_text: str,
) -> tuple[str, str, str]:
    """Extract ``TITLE`` / ``HASHTAGS`` lines from LLM output (case-insensitive).

    If no title is found, the first :data:`MAX_TITLE_WORDS` words of the
    cleaned script are used as a fallback.

    Args:
        script_text: Raw LLM output that may contain ``TITLE: ...`` and
            ``HASHTAGS: ...`` lines.

    Returns:
        Tuple of ``(cleaned_script, title, hashtags)`` where ``cleaned_script``
        has the TITLE and HASHTAGS lines removed.
    """
    title: str = ""
    hashtags: str = ""
    cleaned_lines: list[str] = []

    for line in script_text.split("\n"):
        m_title = TITLE_RE.match(line)
        m_h_tags = HASHTAGS_RE.match(line)
        if m_title:
            title = m_title.group(1).strip()
        elif m_h_tags:
            hashtags = m_h_tags.group(1).strip()
        else:
            cleaned_lines.append(line)

    cleaned: str = "\n".join(cleaned_lines).strip()

    if not title:
        words: list[str] = cleaned.split()
        title = " ".join(words[:MAX_TITLE_WORDS]) if words else ""

    return cleaned, title, hashtags


def generate_title_hashtags(
    script_text: str,
    client: Any,
    model: str,
    temperature: float = 0.7,
) -> tuple[str, str]:
    """Generate title and hashtags from a finished script via a dedicated LLM call.

    Always uses a second LLM call — never expects ``TITLE`` / ``HASHTAGS``
    in the initial script response.

    Args:
        script_text: The completed script text.
        client: An OpenAI-compatible API client instance.
        model: The model identifier to use for generation.
        temperature: Sampling temperature for the LLM call.

    Returns:
        Tuple of ``(title, hashtags)``.
    """
    prompt: str = (
        "Based on the following short-form video script, "
        "generate a catchy title (under 5 words) "
        "and 5 trending, relevant hashtags.\n\n"
        "Script:\n" + script_text + "\n\n"
        "Respond with exactly:\n"
        "TITLE: <title>\nHASHTAGS: <5 hashtags>"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            timeout=300.0,
        )
        reply: str = (response.choices[0].message.content or "").strip()
        _, title, hashtags = parse_title_hashtags(reply)
    except Exception:
        logger.warning("Title/hashtag LLM call failed; falling back")
        title = ""
        hashtags = ""

    if not title:
        words: list[str] = script_text.split()
        title = " ".join(words[:MAX_TITLE_WORDS]) if words else ""

    return title, hashtags


# --- Internal helpers ---


def _is_non_retryable(err_str: str) -> bool:
    """Check if an error string indicates a non-retryable (configuration) error.

    Args:
        err_str: Lowercase error message string.

    Returns:
        ``True`` if the error should not be retried.
    """
    return any(p in err_str for p in NON_RETRYABLE_PATTERNS)
