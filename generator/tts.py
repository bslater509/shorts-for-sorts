"""Text-to-speech voice generation using the Kokoro ONNX model.

Provides functions to initialise, use, and unload the Kokoro TTS session,
with FFmpeg post-processing for a polished broadcast-quality sound.
"""

import logging
import os
import re
import tempfile
import threading

import ffmpeg
import numpy as np
import soundfile as sf

# --- Logger ---

logger: logging.Logger = logging.getLogger("shorts_creator.generator")
if not logger.handlers and not logging.getLogger("shorts_creator").handlers:
    logger.addHandler(logging.NullHandler())

# Suppress noisy asyncio logs from downstream libraries
logging.getLogger("asyncio").setLevel(logging.ERROR)

# --- Path constants ---

BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR: str = os.path.join(BASE_DIR, "models")
MODEL_PATH: str = os.path.join(MODELS_DIR, "kokoro-v1.0.onnx")
VOICES_PATH: str = os.path.join(MODELS_DIR, "voices.json")

MODEL_URL: str = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/kokoro-v1.0.onnx"
)
VOICES_URL: str = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files/voices.json"
)

# --- TTS audio processing constants ---

SILENCE_SAMPLE_RATE: int = 24000
"""Sample rate (Hz) used when generating silence as a fallback."""

DEFAULT_VOICE: str = "af_bella"
"""Fallback voice name used when the requested voice is empty or unrecognised."""

# FFmpeg EQ filter parameters for radio/podcast-style audio enhancement
HIGH_PASS_FREQ: int = 80
"""High-pass filter cutoff frequency in Hz (removes low rumble)."""
LOWSHELF_FREQ: int = 200
"""Low-shelf equaliser centre frequency in Hz (bass boost band)."""
LOWSHELF_GAIN: float = 3.0
"""Low-shelf boost gain in dB."""
HIGHSHELF_FREQ: int = 3000
"""High-shelf equaliser centre frequency in Hz (treble boost band)."""
HIGHSHELF_GAIN: float = 4.0
"""High-shelf boost gain in dB."""

# --- Regex patterns ---

PAUSE_TAG_RE: re.Pattern = re.compile(r"\[(pause|silence)=.*?\]")
"""Matches ``[pause=...]`` or ``[silence=...]`` tags for replacement with a natural pause."""

ANY_TAG_RE: re.Pattern = re.compile(r"\[.*?\]")
"""Matches any remaining bracketed tag (e.g. ``[slow]``, ``[voice=...]``)."""

# --- Module-level TTS state ---

_TTS_INSTANCE = None
"""Singleton holding the loaded ``kokoro_onnx.Kokoro`` instance, or ``None``."""

# Use RLock (reentrant lock) so the same thread can acquire the lock multiple times.
# This prevents a deadlock where ``generate_voice`` holds the lock and calls
# ``init_tts_session()``, which also tries to acquire the same lock.
_TTS_LOCK: threading.RLock = threading.RLock()

# --- Public API ---


def init_tts_session() -> None:
    """Initialise the Kokoro TTS session (singleton).

    Downloads the ONNX model and voices profile if they do not already exist
    on disk, then loads the model into memory.  Safe to call multiple times;
    subsequent calls are a no-op while the session is already initialised.

    Raises:
        RuntimeError: If the ``kokoro_onnx`` package cannot be imported or
            the model fails to load.
    """
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
            logger.error(
                "Failed to import 'kokoro_onnx'. Ensure it is installed.",
                exc_info=True,
            )
            raise RuntimeError(
                "Failed to import 'kokoro_onnx'. "
                "Please run 'pip install kokoro-onnx' to install it."
            ) from e

        logger.info("Loading Kokoro TTS model (CPU ONNX)...")
        try:
            import onnxruntime as ort

            providers: list[str] = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if "CUDAExecutionProvider" in ort.get_available_providers()
                else ["CPUExecutionProvider"]
            )
            session = ort.InferenceSession(MODEL_PATH, providers=providers)
            _TTS_INSTANCE = Kokoro.from_session(session, VOICES_PATH)
            logger.info("Kokoro model loaded successfully with providers: %s", providers)
        except Exception as e:
            logger.error(
                "Failed to initialize Kokoro model: %s", e, exc_info=True
            )
            raise RuntimeError(f"Failed to initialize Kokoro model: {e}") from e


def unload_tts_model() -> None:
    """Unload the TTS model from memory and release memory back to the OS.

    Intended for batch-processing pipelines where the model should not be
    kept resident between generations.
    """
    global _TTS_INSTANCE
    from generator.utils import _release_memory_to_os

    with _TTS_LOCK:
        if _TTS_INSTANCE is not None:
            del _TTS_INSTANCE
            _TTS_INSTANCE = None
            _release_memory_to_os()
            logger.info("Kokoro model unloaded from memory.")


def generate_voice(
    text: str,
    voice: str,
    output_path: str,
    default_speed: float = 1.0,
) -> None:
    """Generate voice audio from text using the Kokoro TTS model.

    The generated waveform is post-processed with FFmpeg EQ filters
    (high-pass, bass boost, treble boost) and saved to ``output_path``
    as a WAV file.

    Args:
        text: Input text to synthesise.  May contain tags such as
            ``[pause=0.5]`` or ``[slow]`` which are stripped or converted.
        voice: Voice identifier recognised by the Kokoro model
            (e.g. ``"af_bella"``, ``"am_adam"``).  Falls back to
            :data:`DEFAULT_VOICE` when empty.
        output_path: Destination path for the generated WAV file.
        default_speed: Speech speed multiplier (1.0 = normal).

    Raises:
        RuntimeError: If voice generation or FFmpeg post-processing fails.
    """
    global _TTS_INSTANCE

    # Acquire lock immediately to prevent races
    with _TTS_LOCK:
        if _TTS_INSTANCE is None:
            init_tts_session()

    # Convert pause/silence tags into natural-sounding ellipsis
    text_with_pauses: str = PAUSE_TAG_RE.sub("... ", text)
    # Strip any other remaining tags like [slow], [voice=...]
    clean_text: str = ANY_TAG_RE.sub("", text_with_pauses).strip()

    if not clean_text:
        # Fallback: write a brief silence when no text remains after stripping
        final_audio: np.ndarray = np.zeros(SILENCE_SAMPLE_RATE, dtype=np.float32)
        sf.write(output_path, final_audio, SILENCE_SAMPLE_RATE)
        return

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            tmp_path: str = tmp_audio.name

        try:
            with _TTS_LOCK:
                target_voice: str = voice if voice else DEFAULT_VOICE
                samples, sample_rate = _TTS_INSTANCE.create(
                    clean_text, voice=target_voice, speed=default_speed, lang="en-us"
                )
                sf.write(tmp_path, samples, sample_rate)

            # Apply FFmpeg post-processing: radio/podcast-style EQ
            stream = ffmpeg.input(tmp_path)

            stream = ffmpeg.filter(stream, "highpass", f=HIGH_PASS_FREQ)
            stream = ffmpeg.filter(stream, "lowshelf", g=LOWSHELF_GAIN, f=LOWSHELF_FREQ)
            stream = ffmpeg.filter(stream, "highshelf", g=HIGHSHELF_GAIN, f=HIGHSHELF_FREQ)

            stream = ffmpeg.output(stream, output_path, loglevel="error")
            ffmpeg.run(stream, overwrite_output=True)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        logger.error(
            "Error during Kokoro voice generation: %s", e, exc_info=True
        )
        raise RuntimeError(f"Failed to generate voice audio with Kokoro: {e}") from e
