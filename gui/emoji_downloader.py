import os
import tarfile
import urllib.request
import logging

logger = logging.getLogger("shorts_creator.emoji_downloader")
if not logger.handlers and not logging.getLogger("shorts_creator").handlers:
    logger.addHandler(logging.NullHandler())

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "fonts", "emoji_cache")

STYLES = {
    "apple": "https://registry.npmjs.org/emoji-datasource-apple/-/emoji-datasource-apple-15.0.1.tgz",
    "twemoji": "https://registry.npmjs.org/emoji-datasource-twitter/-/emoji-datasource-twitter-15.0.1.tgz",
    "google": "https://registry.npmjs.org/emoji-datasource-google/-/emoji-datasource-google-15.0.1.tgz",
    "facebook": "https://registry.npmjs.org/emoji-datasource-facebook/-/emoji-datasource-facebook-15.0.1.tgz",
    "openmoji": "https://registry.npmjs.org/emoji-datasource-openmoji/-/emoji-datasource-openmoji-1.0.0.tgz",
}

def download_and_extract_emoji_style(style_name: str):
    if style_name not in STYLES:
        logger.error(f"Unknown emoji style: {style_name}")
        return

    style_dir = os.path.join(CACHE_DIR, style_name)
    if os.path.exists(style_dir) and len(os.listdir(style_dir)) > 3000:
        logger.debug(f"Emoji style {style_name} already cached.")
        return

    url = STYLES[style_name]
    tarball_path = os.path.join(CACHE_DIR, f"{style_name}.tgz")

    os.makedirs(style_dir, exist_ok=True)

    try:
        logger.info(f"Downloading emoji style {style_name} from {url}...")
        urllib.request.urlretrieve(url, tarball_path)
        
        logger.info(f"Extracting emoji style {style_name}...")
        with tarfile.open(tarball_path, "r:gz") as tar:
            for member in tar.getmembers():
                # The PNGs are typically in package/img/{style}/64/
                # We just want to extract everything that is a 64x64 PNG
                if member.name.endswith(".png") and "/64/" in member.name:
                    member.name = os.path.basename(member.name)
                    tar.extract(member, path=style_dir)
        
        logger.info(f"Successfully cached emoji style: {style_name}")
    except Exception as e:
        logger.error(f"Failed to download or extract emoji style {style_name}: {e}")
    finally:
        if os.path.exists(tarball_path):
            os.remove(tarball_path)

def ensure_emoji_styles():
    os.makedirs(CACHE_DIR, exist_ok=True)
    # Background task / synchronous startup check
    for style in STYLES:
        download_and_extract_emoji_style(style)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ensure_emoji_styles()
