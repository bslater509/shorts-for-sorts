import logging
import os
import sys
import urllib.request

logger = logging.getLogger("shorts_creator.generator")


def download_file(url: str, dest: str, description: str):
    print(f"Downloading {description} from {url}...")
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    def progress_hook(count, block_size, total_size):
        if total_size > 0:
            percent = min(100, int(count * block_size * 100 / total_size))
            sys.stdout.write(f"\rDownloading... {percent}%")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress_hook)
        print("\nDownload complete.")
        logger.info("Downloaded %s -> %s (%d bytes)", description, dest, os.path.getsize(dest))
    except Exception as e:
        print()  # New line after the progress carriage return
        logger.error(f"Failed to download {description} from {url}: {e}", exc_info=True)
        raise RuntimeError(
            f"Failed to download {description} from {url}. "
            f"Please check your internet connection. Error: {e}"
        ) from e


def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    if cs == 100:
        cs = 0
        s += 1
        if s == 60:
            s = 0
            m += 1
            if m == 60:
                m = 0
                h += 1
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _release_memory_to_os():
    import ctypes
    import gc

    gc.collect()
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
    except Exception:
        pass
