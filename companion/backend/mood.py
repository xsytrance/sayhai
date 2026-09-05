"""Mood drift (Phase 7) — the creature's internal weather.

A slow-changing **baseline mood** independent of any one conversation, so some
days it just wakes up feeling chaotic (or mellow, or lovey). It drifts every few
hours and persists, then gets injected into the brain's context to *subtly* tint
everything — distinct from the per-reply emotion, more like a temperament.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

_MOODS = ["chipper", "mellow", "chaotic", "broody", "lovey", "dramatic", "sleepy", "sassy"]
_PERIOD = 3.5 * 3600     # how long a mood lingers before it might shift
_SHIFT_CHANCE = 0.6


class MoodDrift:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.mood = random.choice(_MOODS)
        self.since = time.time()
        self.load()

    def load(self) -> None:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            if d.get("mood") in _MOODS:
                self.mood = d["mood"]
            self.since = float(d.get("since", time.time()))
        except Exception:
            pass
        self.maybe_drift()   # catch up if it sat for a long while

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"mood": self.mood, "since": self.since}), encoding="utf-8")
        except Exception:
            pass

    def maybe_drift(self, now: float | None = None) -> None:
        now = now or time.time()
        if now - self.since >= _PERIOD:
            self.since = now
            if random.random() < _SHIFT_CHANCE:
                self.mood = random.choice([m for m in _MOODS if m != self.mood])
            self.save()

    def context_line(self) -> str:
        return f"Today your underlying mood drifts {self.mood} — let it subtly tint your vibe, not override the moment."
