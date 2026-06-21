"""Music sense — now-playing + amplitude swells (Phase 4, priority #1 on the Go).

Windows path: read SMTC
(``GlobalSystemMediaTransportControlsSessionManager`` via ``winsdk``) for the
universal "now playing" — react to track changes ("ooh I like this one") and drop
artist/song facts. Reuse the audio-output amplitude listener (WASAPI loopback) to
catch big drops ("ohhh THIS is my favorite part"). Same ears, two jobs.

Scaffold only — not wired yet. On Linux it could read MPRIS over D-Bus instead;
both would emit the same ``{"kind": "music", ...}`` signal onto the bus.
"""

from __future__ import annotations


async def run(bus) -> None:  # pragma: no cover - device-specific, not started yet
    return
