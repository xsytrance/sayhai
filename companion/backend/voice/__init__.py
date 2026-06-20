"""Voice OUT — the ``speak(text, emotion)`` dispatcher.

Stub. Lands in Phase 1 (Kokoro engine first). The dispatcher will pick an engine
(Kokoro / Orpheus / ElevenLabs) and stream amplitude to the face for lip-sync.
The single ``speak()`` seam is why Orpheus and ElevenLabs can drop in any time
after Phase 1 with no other code changes.
"""
