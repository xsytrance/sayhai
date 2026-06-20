"""Central settings for the companion.

Phase 0 only needs a handful of these (name, host, port, paths). The rest are
declared now so later phases (brain, voice, channels) have a single home to read
from instead of scattering os.getenv calls everywhere.

Values come from the environment / a .env file (see .env.example). We load .env
by hand with a tiny parser so Phase 0 has *zero* third-party config deps.
"""

from __future__ import annotations

import os
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
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(PROJECT_DIR / ".env")


def _get(key: str, default: str) -> str:
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
# The creature's name. It will become the wake word in Phase 2, so it matters —
# but Phase 0 just shows it in the window title and debug panel. Rename freely.
CREATURE_NAME = _get("CREATURE_NAME", "Pip")

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
# Future-phase settings (declared early, unused in Phase 0)
# ---------------------------------------------------------------------------
OLLAMA_HOST = _get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = _get("OLLAMA_MODEL", "")
VOICE_ENGINE = _get("VOICE_ENGINE", "kokoro")
ELEVENLABS_API_KEY = _get("ELEVENLABS_API_KEY", "")
TELEGRAM_TOKEN = _get("TELEGRAM_TOKEN", "")

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
