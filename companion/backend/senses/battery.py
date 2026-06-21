"""Battery sense — charging / low-battery reactions (Phase 4).

Plugged in -> happy "snacks!"; low and unplugged -> worried. Uses ``psutil`` so
it's cross-platform; on a desktop with no battery it simply finds none and
disables itself. Lazy-imported; ``pip install psutil`` to enable it on the Go.
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("companion.senses.battery")


async def run(bus, interval: float = 60.0) -> None:
    try:
        import psutil
    except Exception:
        log.info("battery sense: psutil not installed — skipping (pip install psutil)")
        return
    if psutil.sensors_battery() is None:
        log.info("battery sense: no battery on this machine — skipping")
        return

    last_plugged = None
    warned_low = False
    while True:
        try:
            b = psutil.sensors_battery()
            if b is not None:
                if last_plugged is not None and b.power_plugged != last_plugged:
                    if b.power_plugged:
                        await bus.emit({"kind": "battery", "summary": "plugged in — snacks time!", "weight": 0.7})
                    else:
                        await bus.emit({"kind": "battery", "summary": "running on battery now", "weight": 0.4})
                last_plugged = b.power_plugged
                if not b.power_plugged and b.percent <= 15 and not warned_low:
                    await bus.emit({"kind": "battery", "summary": f"battery's getting low ({int(b.percent)}%)", "weight": 0.9})
                    warned_low = True
                elif b.percent > 25:
                    warned_low = False
        except Exception:
            pass
        await asyncio.sleep(interval)
