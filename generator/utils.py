"""Utility functions for the generator package: file downloads, time formatting, and memory management."""

import logging
import os
import sys
import urllib.request

# --- Named constants ---

SECONDS_PER_HOUR: int = 3600
"""Number of seconds in one hour."""

SECONDS_PER_MINUTE: int = 60
"""Number of seconds in one minute."""

CENTISECONDS_PER_SECOND: int = 100
"""Number of centiseconds in one second."""

PROGRESS_PERCENT_MAX: int = 100
"""Maximum value for download progress percentage."""

# --- Logger ---

logger: logging.Logger = logging.getLogger("shorts_creator.generator")


# --- Public functions ---


def download_file(url: str, dest: str, description: str) -> None:
    """Download a file from a URL to a local destination with progress reporting.

    Creates destination directories as needed.  Prints a live percentage
    progress bar to stdout during the download.

    Args:
        url: The source URL to download from.
        dest: Local filesystem path where the file will be saved.
        description: Human-readable label for logging and progress output
            (e.g. "Kokoro ONNX Model").

    Raises:
        RuntimeError: If the download fails for any reason (network,
            invalid URL, disk full, etc.).
    """
    print(f"Downloading {description} from {url}...")
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    def _progress_hook(count: int, block_size: int, total_size: int) -> None:
        """Inner callback for ``urllib.request.urlretrieve`` progress tracking."""
        if total_size > 0:
            percent: int = min(
                PROGRESS_PERCENT_MAX,
                int(count * block_size * PROGRESS_PERCENT_MAX / total_size),
            )
            sys.stdout.write(f"\rDownloading... {percent}%")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, dest, reporthook=_progress_hook)
        print("\nDownload complete.")
        logger.info(
            "Downloaded %s -> %s (%d bytes)", description, dest, os.path.getsize(dest)
        )
    except Exception as e:
        print()  # New line after the progress carriage return
        logger.error(
            "Failed to download %s from %s: %s", description, url, e, exc_info=True
        )
        raise RuntimeError(
            f"Failed to download {description} from {url}. "
            f"Please check your internet connection. Error: {e}"
        ) from e


def format_time(seconds: float) -> str:
    """Format a time value as an ASS/SSA timestamp (``H:MM:SS.cs``).

    The format uses hours without zero-padding, minutes and seconds zero-padded
    to two digits, and centiseconds zero-padded to two digits.  Centisecond
    rounding is handled with carry-over through seconds, minutes, and hours.

    Args:
        seconds: Time value in seconds (may be fractional).

    Returns:
        Formatted timestamp string (e.g. ``"0:00:00.00"``, ``"1:01:01.75"``).
    """
    h: int = int(seconds // SECONDS_PER_HOUR)
    m: int = int((seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE)
    s: int = int(seconds % SECONDS_PER_MINUTE)
    cs: int = int(round((seconds % 1) * CENTISECONDS_PER_SECOND))

    # Carry-over when centiseconds round up to 100
    if cs == CENTISECONDS_PER_SECOND:
        cs = 0
        s += 1
        if s == SECONDS_PER_MINUTE:
            s = 0
            m += 1
            if m == SECONDS_PER_MINUTE:
                m = 0
                h += 1

    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# --- Private / internal functions ---


def _release_memory_to_os() -> None:
    """Run garbage collection and call ``malloc_trim`` to release free memory back to the OS.

    This is called after unloading large models (e.g. Kokoro TTS) so that
    the process RSS drops promptly rather than holding freed pages.
    """
    import ctypes
    import gc

    gc.collect()
    try:
        libc: ctypes.CDLL = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
    except Exception:
        pass
