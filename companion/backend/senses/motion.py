"""Motion sense — the Legion Go IMU (Phase 4). The device's killer feature.

Reads the accelerometer (``Windows.Devices.Sensors`` via ``winsdk``) and turns it
into reactions:
  tilt      -> eyes slide with gravity   (fast, broadcast straight to the face)
  shake     -> the `dizzy` pose
  pickup    -> eyes snap up + "whoa!"     (+ a remark on the bus)
  set down  -> a content sigh

Tilt/shake are pushed straight to the face (they can't wait on the brain); pickup/
set-down also drop a signal on the bus so it can *say* something, tastefully.

⚠️ This is the plan's RISK item — heuristic thresholds tuned blind; expect to
adjust ``_THRESH`` / axis signs on the actual Go. Windows-only; ``winsdk`` is
lazy-imported so this module is harmless elsewhere.
"""

from __future__ import annotations

import asyncio
import logging
import math

log = logging.getLogger("companion.senses.motion")

# tunables (per ~12Hz sample) — adjust on the device
_TILT_DEADBAND = 0.03     # don't spam tiny tilt changes
_MOVE_DEV = 0.18          # |accel|-1g above this = "in motion"
_SHAKE_ENERGY = 3.0       # accumulated jitter that counts as a shake
_STILL_SAMPLES = 8        # consecutive still samples = "set down"


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


async def run(bus, broadcast, interval: float = 0.08) -> None:
    try:
        from winsdk.windows.devices.sensors import Accelerometer
    except Exception:
        log.info("motion sense: winsdk unavailable (not Windows?) — skipping")
        return
    acc = Accelerometer.get_default()
    if acc is None:
        log.info("motion sense: no accelerometer found — skipping")
        return

    moving = False
    still = move = shake_cd = pickup_cd = 0
    shake_energy = 0.0
    last_tx = last_ty = 0.0

    while True:
        try:
            r = acc.get_current_reading()
            if r is not None:
                x, y, z = r.acceleration_x, r.acceleration_y, r.acceleration_z
                dev = abs(math.sqrt(x * x + y * y + z * z) - 1.0)

                # tilt -> eyes slide (throttled). Flip signs here if it feels inverted.
                tx, ty = _clamp(x), _clamp(-y)
                if abs(tx - last_tx) > _TILT_DEADBAND or abs(ty - last_ty) > _TILT_DEADBAND:
                    await broadcast({"type": "tilt", "x": round(tx, 3), "y": round(ty, 3)})
                    last_tx, last_ty = tx, ty

                # shake
                shake_energy = shake_energy * 0.85 + dev
                if shake_cd > 0:
                    shake_cd -= 1
                elif shake_energy > _SHAKE_ENERGY:
                    await broadcast({"type": "emotion", "emotion": "dizzy"})
                    await bus.emit({"kind": "motion", "gesture": "shake",
                                    "summary": "you shook me silly!", "weight": 0.5})
                    shake_cd, shake_energy = 30, 0.0

                # pickup / set-down
                if dev > _MOVE_DEV:
                    move += 1
                    still = 0
                    if not moving and move > 1:
                        moving = True
                        if pickup_cd <= 0:
                            await broadcast({"type": "emotion", "emotion": "surprised"})
                            await bus.emit({"kind": "motion", "gesture": "pickup",
                                            "summary": "whoa — you picked me up!", "weight": 0.7})
                            pickup_cd = 40
                else:
                    still += 1
                    move = 0
                    if moving and still > _STILL_SAMPLES:
                        moving = False
                        await broadcast({"type": "emotion", "emotion": "happy"})
                        await bus.emit({"kind": "motion", "gesture": "setdown",
                                        "summary": "set down gently", "weight": 0.3})
                if pickup_cd > 0:
                    pickup_cd -= 1
        except Exception:
            pass
        await asyncio.sleep(interval)
