"""The Ears — Voice IN via faster-whisper (Phase 2).

The browser captures the mic on push-to-talk and POSTs the clip; we transcribe
it here and feed the text into the same streaming ``converse()`` the keyboard
uses. Fully local, zero cloud, zero tokens.

faster-whisper (CTranslate2) is lazy-loaded — the server boots without it, and a
missing install/model raises ``EarsUnavailable`` with a clear hint instead of
crashing. The model decodes whatever container the browser sent (WebM/Opus) via
its bundled PyAV, so we just hand it the raw bytes.
"""

from __future__ import annotations

import asyncio
import io

from . import config


class EarsUnavailable(RuntimeError):
    """Raised when STT can't run (missing dep / model). Caller degrades gracefully."""


class Ears:
    def __init__(self) -> None:
        self._model = None

    def _ensure(self):
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise EarsUnavailable(
                "faster-whisper not installed. Run: pip install faster-whisper"
            ) from e
        # First load downloads the model (~150MB for base) and caches it.
        self._model = WhisperModel(
            config.STT_MODEL, device=config.STT_DEVICE, compute_type=config.STT_COMPUTE
        )

    def transcribe(self, audio: bytes) -> str:
        self._ensure()
        segments, _info = self._model.transcribe(
            io.BytesIO(audio),
            language=(config.STT_LANG or None),
            vad_filter=True,        # trim silence/noise -> cleaner, faster
            beam_size=1,            # greedy = fastest; plenty for short quips
            condition_on_previous_text=False,
        )
        return " ".join(seg.text for seg in segments).strip()


_ears = Ears()


async def transcribe(audio: bytes) -> str:
    """Transcribe a recorded clip (blocking model runs in a worker thread)."""
    return await asyncio.to_thread(_ears.transcribe, audio)


def warmup() -> None:
    """Pre-load the STT model so the first push-to-talk isn't a cold start."""
    _ears._ensure()
