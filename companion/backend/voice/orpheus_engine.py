"""Orpheus TTS — emotional GGUF voice (Phase 6, pulled forward).

Runs the Orpheus 3B speech model locally via ``orpheus-cpp`` (llama.cpp + an ONNX
SNAC decoder — CPU-capable, no separate server). The brain's **emotion** picks a
matching paralinguistic tag, so a ``mischievous`` reply actually snickers and a
``sad`` one sighs — the same emotion value that drives the face and the animation.

Lazy-loaded: the server runs fine without it; a missing install raises
``VoiceUnavailable`` with the fix. First synth downloads the GGUF (~2–3GB).

⚠️ Roommate problem: Orpheus (~3B) shares 16GB with the LLM + Whisper + browser —
keep the chat model small (the plan's whole point).
"""

from __future__ import annotations

from .. import config
from . import VoiceUnavailable, float_to_wav

# emotion -> an Orpheus paralinguistic tag, prepended so the delivery carries the
# mood. Empty = just say it. Tags Orpheus knows: <laugh> <chuckle> <sigh> <gasp>
# <yawn> <groan> <cough> <sniffle>.
_EMO_TAG = {
    "mischievous": "<chuckle> ",
    "surprised": "<gasp> ",
    "sad": "<sigh> ",
    "sleepy": "<yawn> ",
    "grumpy": "<groan> ",
    "happy": "", "excited": "", "love": "", "curious": "", "thinking": "",
    "neutral": "", "dizzy": "",
}


class OrpheusEngine:
    def __init__(self) -> None:
        self._model = None

    def _ensure(self) -> None:
        if self._model is not None:
            return
        try:
            from orpheus_cpp import OrpheusCpp
        except ImportError as e:
            raise VoiceUnavailable(
                "Orpheus not installed. Run: pip install orpheus-cpp "
                "&& pip install llama-cpp-python "
                "--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu"
            ) from e
        try:
            try:
                self._model = OrpheusCpp(n_gpu_layers=config.ORPHEUS_GPU_LAYERS, verbose=False)
            except TypeError:
                self._model = OrpheusCpp()      # older signature
        except Exception as e:
            raise VoiceUnavailable(
                f"couldn't start Orpheus ({type(e).__name__}: {e}). "
                "The first run downloads the GGUF model (~2–3GB)."
            ) from e

    def synth(self, text: str, emotion: str) -> bytes:
        self._ensure()
        import numpy as np

        tagged = _EMO_TAG.get(emotion, "") + text
        sample_rate, samples = self._model.tts(tagged, options={"voice_id": config.ORPHEUS_VOICE})
        a = np.asarray(samples).squeeze().astype("float32")
        if a.size:
            a = a / 32768.0                     # int16 -> [-1, 1] for the WAV writer
        return float_to_wav(a, sample_rate)
