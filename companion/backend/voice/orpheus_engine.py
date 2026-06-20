"""Orpheus TTS — emotional tags (laugh/whisper). Phase 6 stub.

Will route the brain's emotion to a matching vocal delivery (a real snicker on a
mischievous reply). Mind the roommate problem: it's a ~3B model that has to
cohabit with the LLM in 16GB. Same ``synth(text, emotion) -> wav`` contract.
"""

from __future__ import annotations

from . import VoiceUnavailable


class OrpheusEngine:
    def synth(self, text: str, emotion: str) -> bytes:
        raise VoiceUnavailable("Orpheus voice lands in Phase 6 (not wired yet).")
