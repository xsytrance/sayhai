# 🦜 A Living Desktop Companion

A bright, chaotic-goofy cartoon face that fills the screen, blinks, breathes, and
reacts. Built for the Lenovo Legion Go, but it runs in any modern browser.

This repo is built **phase by phase** (see `TAMAGOTCHI_BUILD_PLAN.md` for the full
plan). One creature, three layers: **Body** (the face), **Mind** (brain + memory +
mood), **Life** (the Tamagotchi game + senses). A single **emotion signal** is the
spine that drives the face, the voice, and the animation springiness together.

---

## Status

- ✅ **Phase 0 — Scaffold + the alive face** *(current)*
- ⬜ Phase 1 — Brain + Voice OUT + Emotion
- ⬜ Phase 2 — Ears (Voice IN)
- ⬜ Phase 3 — Channels (text it from anywhere)
- ⬜ Phase 4 — Senses (the nervous system)
- ⬜ Phase 5 — The Tamagotchi layer
- ⬜ Phase 6 — Voice upgrades (Orpheus / ElevenLabs)
- ⬜ Phase 7 — The soul polish

---

## Run it (Phase 0)

```bash
cd companion
pip install -r requirements.txt          # or: pip install --break-system-packages -r requirements.txt
python -m backend.main
```

Then open <http://127.0.0.1:8000> in a browser.

On the Legion Go you have two fullscreen options:

- **pywebview window** (chrome-less, on-device feel): `pip install pywebview`, set
  `USE_WEBVIEW=true` in `.env`, then `python -m backend.main`.
- **Edge kiosk**: `msedge --kiosk --app=http://127.0.0.1:8000` while the server runs.

Copy `.env.example` to `.env` to set the creature's name, port, etc. Nothing in
there is required for Phase 0.

## Play with the face

It's alive on its own — it blinks, its eyes wander, it breathes, its brows twitch.
A debug panel (top-left) lets you drive it:

| Action | How |
|---|---|
| Pick an emotion | Click a button, or keys `1–9 0 - =` |
| Next emotion | `Space` |
| Back to neutral | `Backspace` |
| Auto-cycle all poses | `a` (or the button) |
| Poke it | `p`, or click/tap the face |
| Toggle idle life | `i` |
| Fullscreen | `f` |
| Show/hide the panel | `` ` `` |

The 12 emotions — `neutral, happy, excited, mischievous, curious, thinking,
surprised, sad, sleepy, grumpy, love, dizzy` — are the fixed set the rest of the
project speaks in. Each one is a face pose **and** (later) a voice delivery **and**
an animation springiness profile.

You can also drive it from outside the browser — this is the same nerve the brain
and the senses will use in later phases:

```bash
curl -X POST http://127.0.0.1:8000/api/emotion/excited
```

## Layout

```
companion/
├── backend/
│   ├── main.py        # FastAPI switchboard + WebSocket hub  (the spine)
│   ├── config.py      # settings, .env, the canonical emotion set
│   ├── brain.py       # Ollama          (stub — Phase 1)
│   ├── voice/         # speak() + TTS   (stub — Phase 1)
│   ├── senses/        # the event bus   (stub — Phase 4)
│   └── channels/      # telegram + web  (stub — Phase 3)
├── frontend/
│   ├── face.html      # inline SVG face + debug panel
│   ├── face.css
│   └── face.js        # spring engine, idle life, 12 poses, WS client
├── data/              # memory.json / state.json land here (Phase 5+)
├── requirements.txt
└── .env.example
```

### How the face works (the one idea)

Every moving part is a **spring** with a target value. An **emotion** is just a
table of targets plus a *springiness profile* (stiffness + damping). Switching
emotion retargets the springs and they **jiggle to a stop** — that overshoot is
the whole goofy-gremlin vibe. On top of that runs an always-on **idle loop**
(blinks, eye saccades, breathing, brow twitches) so it's never perfectly still.

Adding the brain later = pushing `{"type":"emotion","emotion":"..."}` down the
WebSocket. Nothing in the face has to change.
