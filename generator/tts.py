import logging
import os
import threading

logger = logging.getLogger("shorts_creator.generator")
if not logger.handlers and not logging.getLogger("shorts_creator").handlers:
    logger.addHandler(logging.NullHandler())

logging.getLogger("asyncio").setLevel(logging.ERROR)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_PATH = os.path.join(MODELS_DIR, "kokoro-v1.0.onnx")
VOICES_PATH = os.path.join(MODELS_DIR, "voices.json")

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"

_TTS_INSTANCE = None

# Use RLock (reentrant lock) so the same thread can acquire the lock multiple times.
# This prevents a deadlock where generate_voice holds the lock and calls
# init_tts_session(), which also tries to acquire the same lock.
_TTS_LOCK = threading.RLock()


def init_tts_session():
    global _TTS_INSTANCE
    with _TTS_LOCK:
        if _TTS_INSTANCE is not None:
            return

        from generator.utils import download_file

        if not os.path.exists(MODEL_PATH):
            download_file(MODEL_URL, MODEL_PATH, "Kokoro ONNX Model")
        if not os.path.exists(VOICES_PATH):
            download_file(VOICES_URL, VOICES_PATH, "Kokoro Voices Profile")

        try:
            from kokoro_onnx import Kokoro
        except ImportError as e:
            logger.error("Failed to import 'kokoro_onnx'. Ensure it is installed.", exc_info=True)
            raise RuntimeError(
                "Failed to import 'kokoro_onnx'. Please run 'pip install kokoro-onnx' to install it."
            ) from e

        logger.info("Loading Kokoro TTS model (CPU ONNX)...")
        try:
            _TTS_INSTANCE = Kokoro(MODEL_PATH, VOICES_PATH)
            logger.info("Kokoro model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro model: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize Kokoro model: {e}") from e


def unload_tts_model():
    """Unloads the TTS model from memory to free it up for batch processes."""
    global _TTS_INSTANCE
    from generator.utils import _release_memory_to_os

    with _TTS_LOCK:
        if _TTS_INSTANCE is not None:
            del _TTS_INSTANCE
            _TTS_INSTANCE = None
            _release_memory_to_os()
            logger.info("Kokoro model unloaded from memory.")


def generate_voice(text: str, voice: str, output_path: str, default_speed: float = 1.0):
    """
    Generates local voice audio from text using Kokoro TTS.
    """
    global _TTS_INSTANCE
    import re

    import numpy as np
    import soundfile as sf

    # Acquire lock immediately to prevent races
    with _TTS_LOCK:
        if _TTS_INSTANCE is None:
            init_tts_session()

    # Convert pause tags to ellipses for natural pauses.
    text_with_pauses = re.sub(r"\[(pause|silence)=.*?\]", "... ", text)
    # Strip any other remaining tags like [slow], [voice=...]
    clean_text = re.sub(r"\[.*?\]", "", text_with_pauses).strip()

    if not clean_text:
        # fallback to a tiny bit of silence if nothing was generated
        sample_rate = 24000
        final_audio = np.zeros(sample_rate, dtype=np.float32)
        sf.write(output_path, final_audio, sample_rate)
        return

    try:
        import tempfile

        import ffmpeg

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            tmp_path = tmp_audio.name

        try:
            with _TTS_LOCK:
                # Provide a fallback voice if the specified voice is not recognized by Kokoro
                target_voice = voice if voice else "af_bella"
                samples, sample_rate = _TTS_INSTANCE.create(
                    clean_text, voice=target_voice, speed=default_speed, lang="en-us"
                )
                sf.write(tmp_path, samples, sample_rate)

            # Apply FFmpeg post-processing: EQ
            stream = ffmpeg.input(tmp_path)

            # Radio/Podcast EQ: High-pass at 80Hz, boost bass at 200Hz, boost treble at 3000Hz
            stream = ffmpeg.filter(stream, "highpass", f=80)
            stream = ffmpeg.filter(stream, "lowshelf", g=3, f=200)
            stream = ffmpeg.filter(stream, "highshelf", g=4, f=3000)

            stream = ffmpeg.output(stream, output_path, loglevel="error")
            ffmpeg.run(stream, overwrite_output=True)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        logger.error(f"Error during Kokoro voice generation: {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate voice audio with Kokoro: {e}") from e
