"""Kokoro TTS — the no-drama, CPU-friendly default voice (Phase 1).

Lazy-loads the ONNX model on first use so the server boots fine without the
weights present; if they're missing it raises ``VoiceUnavailable`` with exact
download instructions instead of crashing.
"""

from __future__ import annotations

from .. import config
from . import VoiceUnavailable, float_to_wav

# emotion -> speaking rate. Kokoro has no emotion tags, so the *pace* carries the
# mood: hyped = fast, drowsy = slow. (Orpheus does real tags in Phase 6.)
_SPEED = {
    "excited": 1.18,
    "surprised": 1.12,
    "dizzy": 1.08,
    "happy": 1.10,
    "mischievous": 1.06,
    "curious": 1.05,
    "love": 1.04,
    "neutral": 1.00,
    "grumpy": 1.00,
    "thinking": 0.96,
    "sad": 0.90,
    "sleepy": 0.82,
}

_DOWNLOAD_HINT = (
    "Kokoro voice files not found.\n"
    "  expected model:  {model}\n"
    "  expected voices: {voices}\n"
    "Download them once (~330MB) into the project dir:\n"
    "  curl -L -o {model_name} "
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx\n"
    "  curl -L -o {voices_name} "
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
)


class KokoroEngine:
    def __init__(self) -> None:
        self._kokoro = None

    def _ensure(self) -> None:
        if self._kokoro is not None:
            return
        model = config.resolve_path(config.KOKORO_MODEL)
        voices = config.resolve_path(config.KOKORO_VOICES)
        if not model.exists() or not voices.exists():
            raise VoiceUnavailable(
                _DOWNLOAD_HINT.format(
                    model=model, voices=voices,
                    model_name=config.KOKORO_MODEL, voices_name=config.KOKORO_VOICES,
                )
            )
        try:
            from kokoro_onnx import Kokoro
        except ImportError as e:
            raise VoiceUnavailable(
                "kokoro-onnx not installed. Run: pip install kokoro-onnx onnxruntime"
            ) from e
        self._kokoro = Kokoro(str(model), str(voices))

    def synth(self, text: str, emotion: str) -> bytes:
        self._ensure()
        speed = _SPEED.get(emotion, 1.0)
        samples, sample_rate = self._kokoro.create(
            text, voice=config.KOKORO_VOICE, speed=speed, lang=config.KOKORO_LANG
        )
        return float_to_wav(samples, sample_rate)
