"""Music sense — Windows "now playing" via SMTC (Phase 4, priority #1 on the Go).

Reads the universal Windows now-playing
(``GlobalSystemMediaTransportControlsSessionManager`` via ``winsdk``) and emits a
signal on each track change so the creature can react ("ooh I like this one") and
drop song/artist facts. Works for Spotify, browsers, any app that reports media.

Windows-only; ``winsdk`` is lazy-imported so importing this module is harmless
elsewhere. (The amplitude-swell "favorite part!" trick reuses the Phase-1 audio
listener via WASAPI loopback — a later add.)
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("companion.senses.music")


async def run(bus, interval: float = 4.0) -> None:
    try:
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        )
    except Exception:
        log.info("music sense: winsdk unavailable (not Windows?) — skipping")
        return

    last = None
    while True:
        try:
            mgr = await MediaManager.request_async()
            session = mgr.get_current_session()
            if session is not None:
                props = await session.try_get_media_properties_async()
                title = (props.title or "").strip()
                artist = (props.artist or "").strip()
                key = (title, artist)
                if title and key != last:
                    if last is not None:          # don't squawk about whatever was already on at boot
                        summary = f"now playing: {title}" + (f" — {artist}" if artist else "")
                        await bus.emit({"kind": "music", "summary": summary,
                                        "title": title, "artist": artist, "weight": 1.0})
                    last = key
        except Exception:
            pass
        await asyncio.sleep(interval)
