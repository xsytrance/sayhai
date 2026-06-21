"""Clock sense — notices the time of day (Phase 4).

Cross-platform. Emits a signal when the day crosses into a new part (morning /
afternoon / evening / night). The plan's richer "learned work routine" (asks once
when you usually leave, runs a morning ritual) builds on this later with state.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

_SUMMARIES = {
    "morning": "it just turned morning",
    "afternoon": "it's afternoon now",
    "evening": "evening's settling in",
    "night": "it's getting late",
}
_WEIGHT = {"morning": 0.9, "afternoon": 0.5, "evening": 0.6, "night": 0.9}


def time_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


async def run(bus, interval: float = 60.0, now_fn=datetime.now) -> None:
    last = time_of_day(now_fn().hour)
    while True:
        await asyncio.sleep(interval)
        part = time_of_day(now_fn().hour)
        if part != last:
            await bus.emit({"kind": "clock", "summary": _SUMMARIES[part], "weight": _WEIGHT[part]})
            last = part
