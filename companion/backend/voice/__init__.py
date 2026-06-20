"""Voice OUT — the ``speak(text, emotion)`` dispatcher.

One function, swappable engines. Phase 1 ships **Kokoro**; Orpheus and
ElevenLabs (Phase 6) slot in behind the same call with no other code changes —
that's the whole point of routing every reply through here.

An engine's only job is **synthesis**: text + emotion -> WAV bytes. Playback and
lip-sync happen in the browser (the face decodes the WAV via Web Audio and drives
mouth-openness from the live amplitude), so the backend needs no audio device.

The emotion shapes the *delivery*. Kokoro has no emotion tags, so we map emotion
-> speaking rate (excited talks fast, sleepy drawls). Orpheus will later use real
laugh/whisper tags off the same emotion value.
"""

from __future__ import annotations

import asyncio
import io
import wave


class VoiceUnavailable(RuntimeError):
    """Raised when the selected engine can't synthesize (missing model, dep, key).

    The switchboard catches this and still shows the face + text, just silent.
    """


def float_to_wav(samples, sample_rate: int) -> bytes:
    """Mono float32 PCM in [-1, 1] -> 16-bit WAV bytes."""
    import numpy as np

    a = np.asarray(samples, dtype=np.float32).flatten()
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sample_rate))
        w.writeframes(pcm)
    return buf.getvalue()


_engines: dict = {}


def _get_engine(name: str):
    if name not in _engines:
        if name == "kokoro":
            from .kokoro_engine import KokoroEngine
            _engines[name] = KokoroEngine()
        elif name == "orpheus":
            from .orpheus_engine import OrpheusEngine
            _engines[name] = OrpheusEngine()
        elif name == "elevenlabs":
            from .elevenlabs_engine import ElevenLabsEngine
            _engines[name] = ElevenLabsEngine()
        else:
            raise VoiceUnavailable(f"unknown voice engine: {name!r}")
    return _engines[name]


async def speak(text: str, emotion: str, engine: str | None = None) -> bytes:
    """Synthesize ``text`` (delivered per ``emotion``) -> WAV bytes.

    Runs the (blocking) engine in a worker thread so the event loop stays free.
    Raises ``VoiceUnavailable`` if the engine can't run.
    """
    from .. import config

    name = engine or config.VOICE_ENGINE
    eng = _get_engine(name)
    return await asyncio.to_thread(eng.synth, text, emotion)
