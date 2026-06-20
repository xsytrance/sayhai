"""ElevenLabs TTS — premium cloud voice. Phase 6 stub.

Online-only treat, gated behind ELEVENLABS_API_KEY. Same
``synth(text, emotion) -> wav`` contract as every other engine.
"""

from __future__ import annotations

from . import VoiceUnavailable


class ElevenLabsEngine:
    def synth(self, text: str, emotion: str) -> bytes:
        raise VoiceUnavailable("ElevenLabs voice lands in Phase 6 (not wired yet).")
