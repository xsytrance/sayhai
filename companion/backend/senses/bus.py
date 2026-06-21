"""The nervous system — a shared event bus + a tasteful reactor (Phase 4).

Everything the creature can sense is just a **signal** on this bus:
``{"kind": "weather", "summary": "it started raining (12°C)", "weight": 1.0}``.

Sources (clock, weather, …) emit signals. The **Reactor** decides whether a
signal is worth squawking about — gated by a chattiness dial, a cooldown, a
"don't butt in right after the user" window, and a "not while already talking"
check. Adding a new sense later = one more source emitting on the same bus; the
reactor and the rest of the app don't change. That's the whole point.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time

log = logging.getLogger("companion.senses")


class Bus:
    """Dead-simple async pub/sub. Subscribers are ``async (signal) -> None``."""

    def __init__(self) -> None:
        self._subs: list = []

    def subscribe(self, fn):
        self._subs.append(fn)
        return fn

    async def emit(self, signal: dict) -> None:
        log.debug("signal: %s", signal.get("summary"))
        for fn in list(self._subs):
            try:
                await fn(signal)
            except Exception:
                log.exception("bus subscriber error")


class Reactor:
    """Turns worthy signals into spontaneous, in-character remarks — tastefully.

    ``react_fn`` is ``async (summary: str) -> None`` (it makes the creature speak).
    The gates, in order: chattiness on at all, not currently talking, the user
    hasn't just spoken, the cooldown has elapsed, and a probability roll scaled by
    chattiness × the signal's weight.
    """

    def __init__(self, react_fn, *, chattiness: float = 0.5, cooldown: float = 120.0,
                 quiet_after_user: float = 25.0, busy_check=None,
                 now_fn=time.monotonic, rng=random.random) -> None:
        self._react = react_fn
        self.chattiness = chattiness
        self.cooldown = cooldown
        self.quiet_after_user = quiet_after_user
        self._busy = busy_check or (lambda: False)
        self._now = now_fn
        self._rng = rng
        self._last_react = -1e9
        self._last_user = -1e9

    def mark_user_activity(self) -> None:
        self._last_user = self._now()

    async def on_signal(self, signal: dict) -> bool:
        if self.chattiness <= 0:
            return False
        now = self._now()
        if self._busy():
            return False
        if now - self._last_user < self.quiet_after_user:
            return False
        eff_cooldown = self.cooldown / max(0.15, self.chattiness)
        if now - self._last_react < eff_cooldown:
            return False
        if self._rng() > self.chattiness * signal.get("weight", 1.0):
            return False
        self._last_react = now
        try:
            await self._react(signal["summary"])
        except Exception:
            log.exception("reactor react failed")
        return True


class SenseHub:
    """Owns the background source tasks; cancels them cleanly on shutdown."""

    def __init__(self, bus: Bus) -> None:
        self.bus = bus
        self._tasks: list[asyncio.Task] = []

    def start_source(self, run_coro, *args) -> None:
        # sources get the bus; some (motion) also get a broadcaster for fast,
        # un-gated face reactions (eyes sliding with gravity can't wait on the brain).
        self._tasks.append(asyncio.create_task(run_coro(self.bus, *args)))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._tasks = []
