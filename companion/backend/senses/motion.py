"""Motion sense — the Legion Go IMU (Phase 4). ⚠️ RISK: needs a spike.

Read the gyro/accelerometer on Windows (likely ``Windows.Devices.Sensors``
Accelerometer/Gyrometer, or raw HID) and map to:
  pickup    -> eyes snap up + "whoa!"
  tilt      -> eyes slide with gravity
  shake     -> the `dizzy` pose
  set down  -> a content sigh
This is the device's killer feature — worth the effort, but prove the sensor read
first. Scaffold only; emits ``{"kind": "motion", ...}`` once implemented.
"""

from __future__ import annotations


async def run(bus) -> None:  # pragma: no cover - device-specific, not started yet
    return
