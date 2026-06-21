"""Battery sense — charging / low-battery reactions (Phase 4).

Plugged in -> happy "snacks!"; low and unplugged -> worried. On Windows read it
via the power APIs (or ``psutil.sensors_battery()`` cross-platform). Scaffold only;
emits ``{"kind": "battery", ...}`` once wired.
"""

from __future__ import annotations


async def run(bus) -> None:  # pragma: no cover - device-specific, not started yet
    return
