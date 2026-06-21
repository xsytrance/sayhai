"""Central settings for the companion.

Phase 0 only needs a handful of these (name, host, port, paths). The rest are
declared now so later phases (brain, voice, channels) have a single home to read
from instead of scattering os.getenv calls everywhere.

Values come from the environment / a .env file (see .env.example). We load .env
by hand with a tiny parser so Phase 0 has *zero* third-party config deps.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
DATA_DIR = PROJECT_DIR / "data"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader. No dependency, no surprises.

    Only sets keys that are not already present in the real environment, so an
    explicitly-exported variable always wins over the file.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]               # quoted: take verbatim ('#' allowed inside)
        else:
            m = re.search(r"\s#", value)      # strip an inline "  # comment"
            if m:
                value = value[: m.start()]
            value = value.strip()
        os.environ.setdefault(key, value)


_load_dotenv(PROJECT_DIR / ".env")


def _get(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _opt_float(key: str):
    v = _get(key, "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
# The creature's name. It will become the wake word in Phase 2, so it matters —
# shown in the window title/debug panel and used in the brain's personality.
CREATURE_NAME = _get("CREATURE_NAME", "Chatty")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
HOST = _get("HOST", "127.0.0.1")
PORT = int(_get("PORT", "8000"))

# Launch a chrome-less pywebview window on startup (the Legion Go experience).
# When false, just run the server and open the URL in any browser yourself —
# handy for headless dev and for testing on the Go via `Edge --kiosk --app`.
USE_WEBVIEW = _get("USE_WEBVIEW", "false").lower() in ("1", "true", "yes", "on")

# Design resolution of the Legion Go panel. The face is authored for this and
# scaled to fit whatever window it lands in.
DESIGN_WIDTH = int(_get("DESIGN_WIDTH", "2560"))
DESIGN_HEIGHT = int(_get("DESIGN_HEIGHT", "1600"))

# ---------------------------------------------------------------------------
# Brain (Ollama) — Phase 1
# ---------------------------------------------------------------------------
OLLAMA_HOST = _get("OLLAMA_HOST", "http://localhost:11434")
# The chat model. Set this to one you've pulled, e.g. "qwen3:4b", "llama3.2:3b".
OLLAMA_MODEL = _get("OLLAMA_MODEL", "qwen3.5:4b")
# Keep replies short & quippy; cap generation so it can't ramble into an essay.
# Shorter = faster first audio. Parrot quips rarely need more.
OLLAMA_NUM_PREDICT = int(_get("OLLAMA_NUM_PREDICT", "120"))
OLLAMA_TEMPERATURE = float(_get("OLLAMA_TEMPERATURE", "0.8"))
# Context window. Smaller = faster + less RAM (helps the roommate problem). The
# system prompt + a few short turns fit easily in 2k.
OLLAMA_NUM_CTX = int(_get("OLLAMA_NUM_CTX", "2048"))
# How long Ollama keeps the model resident between turns (snappier replies).
OLLAMA_KEEP_ALIVE = _get("OLLAMA_KEEP_ALIVE", "30m")
# How many recent turns of conversation to feed back as context (RAM only;
# real persisted memory is Phase 7).
HISTORY_TURNS = int(_get("HISTORY_TURNS", "6"))
# Prime the brain + voice on startup so the first message isn't a cold start.
WARMUP = _get("WARMUP", "true").lower() in ("1", "true", "yes", "on")

# ---------------------------------------------------------------------------
# Voice OUT — Phase 1 (Kokoro). Orpheus/ElevenLabs are Phase 6.
# ---------------------------------------------------------------------------
VOICE_ENGINE = _get("VOICE_ENGINE", "kokoro")
# Kokoro model files (download once — see README). Paths are resolved relative
# to the project dir if not absolute.
KOKORO_MODEL = _get("KOKORO_MODEL", "kokoro-v1.0.onnx")
KOKORO_VOICES = _get("KOKORO_VOICES", "voices-v1.0.bin")
KOKORO_VOICE = _get("KOKORO_VOICE", "af_heart")
KOKORO_LANG = _get("KOKORO_LANG", "en-us")
# Orpheus (Phase 6): emotional GGUF voice via llama.cpp + SNAC. Opt-in:
#   VOICE_ENGINE=orpheus  (pip install orpheus-cpp llama-cpp-python)
ORPHEUS_VOICE = _get("ORPHEUS_VOICE", "tara")   # tara, leah, jess, leo, dan, mia, zac, zoe
ORPHEUS_GPU_LAYERS = int(_get("ORPHEUS_GPU_LAYERS", "0"))  # >0 to offload to GPU
ELEVENLABS_API_KEY = _get("ELEVENLABS_API_KEY", "")

# ---------------------------------------------------------------------------
# Ears — Phase 2 (faster-whisper STT). Browser captures the mic; we transcribe.
# ---------------------------------------------------------------------------
# base.en is fast + accurate enough for short push-to-talk clips. Try small.en
# for more accuracy, tiny.en for more speed. int8 keeps it snappy on CPU.
STT_MODEL = _get("STT_MODEL", "base.en")
STT_DEVICE = _get("STT_DEVICE", "cpu")
STT_COMPUTE = _get("STT_COMPUTE", "int8")
STT_LANG = _get("STT_LANG", "en")  # blank to auto-detect (slower)

# ---------------------------------------------------------------------------
# Channels — Phase 3 (Telegram: text it from anywhere)
# ---------------------------------------------------------------------------
# Create a bot with @BotFather and paste the token. Blank = Telegram off.
TELEGRAM_TOKEN = _get("TELEGRAM_TOKEN", "")
# Also reply with a spoken voice note (stretch). Needs ffmpeg on PATH.
TELEGRAM_VOICE = _get("TELEGRAM_VOICE", "true").lower() in ("1", "true", "yes", "on")
# Lock the bot to specific Telegram user IDs (comma-separated). Blank = anyone.
TELEGRAM_ALLOWED_IDS = [s.strip() for s in _get("TELEGRAM_ALLOWED_IDS", "").split(",") if s.strip()]

# ---------------------------------------------------------------------------
# Senses — Phase 4 (the nervous system)
# ---------------------------------------------------------------------------
SENSES_ENABLED = _get("SENSES_ENABLED", "true").lower() in ("1", "true", "yes", "on")
# How often it pipes up unprompted: 0 = never, 1 = chatty. The reactor also
# rate-limits and waits for quiet, so even 1.0 isn't spammy.
CHATTINESS = float(_get("CHATTINESS", "0.5"))
# Location for weather. Blank = auto-detect once by IP. (e.g. 40.71 / -74.0)
WEATHER_LAT = _opt_float("WEATHER_LAT")
WEATHER_LON = _opt_float("WEATHER_LON")


def resolve_path(p: str) -> Path:
    """Absolute paths pass through; relative ones resolve against the project dir."""
    path = Path(p)
    return path if path.is_absolute() else (PROJECT_DIR / path)

# The canonical emotion set the face knows how to render. The brain (Phase 1)
# must only ever emit one of these. Single source of truth, shared with the
# frontend via /api/emotions so the two can never drift apart.
EMOTIONS = [
    "neutral",
    "happy",
    "excited",
    "mischievous",
    "curious",
    "thinking",
    "surprised",
    "sad",
    "sleepy",
    "grumpy",
    "love",
    "dizzy",
]
