"""LLM utility functions extracted from batch.py — zero behavioral change."""

import re
import time
import traceback

from openai import OpenAI

from gui.config import console, logger
from gui.utils import get_active_llm_profile


def retry_with_backoff(func, max_attempts=3, base_delay=1.0):
    """Retry a callable on transient errors with exponential backoff.
    Retries on ConnectionError, Timeout, and exceptions mentioning
    rate/timeout/connection/overloaded.  Does NOT retry on bad request
    or auth errors (those are configuration problems).
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            err_str = str(e).lower()
            # Never retry bad-request / auth errors
            if (
                "bad request" in err_str
                or "auth" in err_str
                or "unauthorized" in err_str
                or "401" in err_str
                or "403" in err_str
            ):
                raise
            is_retryable = isinstance(e, (ConnectionError, TimeoutError)) or any(
                w in err_str for w in ["rate", "timeout", "connection", "overloaded", "api_error"]
            )
            if not is_retryable or attempt == max_attempts - 1:
                raise
            delay = base_delay * (2**attempt)
            time.sleep(delay)


def parse_title_hashtags(script_text: str) -> tuple:
    """Extract TITLE/HASHTAGS lines from LLM output, case-insensitive.
    Returns (cleaned_script, title, hashtags).
    """
    title = ""
    hashtags = ""
    cleaned_lines = []
    for line in script_text.split("\n"):
        m_title = re.match(r"^title\s*:\s*(.*)", line, re.I)
        m_h_tags = re.match(r"^hashtags?\s*:\s*(.*)", line, re.I)
        if m_title:
            title = m_title.group(1).strip()
        elif m_h_tags:
            hashtags = m_h_tags.group(1).strip()
        else:
            cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines).strip()

    if not title:
        words = cleaned.split()
        title = " ".join(words[:8]) if words else ""

    return cleaned, title, hashtags


def generate_title_hashtags(
    script_text: str, client, model: str, temperature: float = 0.7
) -> tuple:
    """Generate title and hashtags from a finished script via a dedicated LLM call.
    Always uses a second call — never expects TITLE/HASHTAGS in the first response.
    Returns (title, hashtags).
    """
    prompt = (
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
        reply = (response.choices[0].message.content or "").strip()
        _, title, hashtags = parse_title_hashtags(reply)
    except Exception:
        logger.warning("Title/hashtag LLM call failed; falling back")
        title = ""
        hashtags = ""

    if not title:
        words = script_text.split()
        title = " ".join(words[:8]) if words else ""

    return title, hashtags
