"""Weather sense — Open-Meteo (Phase 4). No API key, cross-platform.

Emits a gentle opener on the first read, then a signal whenever precipitation
starts or stops. Location comes from config (WEATHER_LAT/LON) or a one-time IP
geolocation.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from .. import config

log = logging.getLogger("companion.senses.weather")

# Open-Meteo WMO weather codes -> human words (the bits we care about).
_WCODE = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "showers", 81: "showers", 82: "violent showers",
    85: "snow showers", 86: "snow showers", 95: "a thunderstorm", 96: "a thunderstorm", 99: "a thunderstorm",
}


def describe(code: int) -> str:
    return _WCODE.get(int(code), "odd skies")


def parse_current(payload: dict) -> dict:
    cur = payload["current"]
    return {
        "temp": round(cur["temperature_2m"]),
        "precip": float(cur["precipitation"]),
        "code": int(cur["weather_code"]),
    }


async def _geolocate():
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            j = (await c.get("http://ip-api.com/json/?fields=lat,lon,city")).json()
            return float(j["lat"]), float(j["lon"]), j.get("city")
    except Exception:
        return None


async def fetch_current(lat: float, lon: float) -> dict:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,precipitation,weather_code"
    )
    async with httpx.AsyncClient(timeout=8.0) as c:
        return parse_current((await c.get(url)).json())


async def run(bus, interval: float = 1800.0) -> None:
    lat, lon, city = config.WEATHER_LAT, config.WEATHER_LON, None
    if lat is None or lon is None:
        loc = await _geolocate()
        if not loc:
            log.warning("weather: no location available; sense disabled")
            return
        lat, lon, city = loc
    where = f" in {city}" if city else ""

    last_precip = None
    while True:
        try:
            w = await fetch_current(lat, lon)
        except Exception:
            await asyncio.sleep(interval)
            continue
        precip = w["precip"] > 0
        if last_precip is None:
            await bus.emit({"kind": "weather",
                            "summary": f"weather right now: {describe(w['code'])}, {w['temp']}°C{where}",
                            "weight": 0.5})
        elif precip != last_precip:
            change = f"it started: {describe(w['code'])}" if precip else "the rain let up"
            await bus.emit({"kind": "weather", "summary": f"{change} ({w['temp']}°C)", "weight": 1.0})
        last_precip = precip
        await asyncio.sleep(interval)
