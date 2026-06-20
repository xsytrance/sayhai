# 🦜 A Living Desktop Companion

A bright, chaotic-goofy cartoon face that fills the screen, blinks, breathes, and
reacts — and now **talks back out loud**. Built for the Lenovo Legion Go, but it
runs in any modern browser.

Built phase by phase (see `TAMAGOTCHI_BUILD_PLAN.md`). One creature, three layers:
**Body** (the face), **Mind** (brain + memory + mood), **Life** (the Tamagotchi game
+ senses). A single **emotion signal** is the spine that drives the face, the voice,
and the animation springiness together.

---

## Status

- ✅ **Phase 0 — Scaffold + the alive face**
- ✅ **Phase 1 — Brain + Voice OUT + Emotion** *(current)*
- ⬜ Phase 2 — Ears (Voice IN)
- ⬜ Phase 3 — Channels (text it from anywhere)
- ⬜ Phase 4 — Senses (the nervous system)
- ⬜ Phase 5 — The Tamagotchi layer
- ⬜ Phase 6 — Voice upgrades (Orpheus / ElevenLabs)
- ⬜ Phase 7 — The soul polish

---

## Run it (Phase 1)

You need two local things running alongside the app: **Ollama** (the brain) and the
**Kokoro** voice files (the voice). Both are free and fully offline.

### 1. Brain — Ollama
```bash
# install Ollama from https://ollama.com, then pull a small chat model:
ollama pull llama3.2:3b        # or qwen2.5:3b, etc. (3B-class leaves room for the voice)
```
Set `OLLAMA_MODEL` in `.env` to whatever you pulled.

### 2. Voice — Kokoro model files (one-time, ~330MB)
Download into the `companion/` directory (next to this README):
```bash
curl -L -o kokoro-v1.0.onnx  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -L -o voices-v1.0.bin   https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```
(If they're missing, the creature still shows the face + reply text — just silently.)

### 3. The app
```bash
cd companion
cp .env.example .env            # then set OLLAMA_MODEL
pip install -r requirements.txt
python -m backend.main
```
Open the **face** at <http://127.0.0.1:8000> (or `USE_WEBVIEW=true` for the fullscreen
window / `msedge --kiosk --app=http://127.0.0.1:8000` on the Go).

> **Sound note:** browsers block audio until you interact with the page. Click the
> face once (a poke) to unlock sound for the session. For Edge kiosk you can also add
> `--autoplay-policy=no-user-gesture-required`.

### 4. Talk to it
- On the same machine: open <http://127.0.0.1:8000/control> in another tab.
- **From your phone** (same wi-fi): set `HOST=0.0.0.0`, find this PC's LAN IP, and open
  `http://<that-ip>:8000/control`. Type → the creature thinks, then **replies out loud
  on the Go**, mouth synced, face matching the mood.

You can also drive it from a terminal:
```bash
curl -X POST localhost:8000/api/say -H 'content-type: application/json' -d '{"text":"hey, what song is this?"}'
```

## Play with the face (Phase 0 controls)

Still alive on its own (blinks, eye wander, breathing). A debug panel (top-left) drives
poses by hand: keys `1–9 0 - =`, `Space` = next, `p`/click = poke, `i` = idle toggle,
`f` = fullscreen, `` ` `` = panel.

The 12 emotions — `neutral, happy, excited, mischievous, curious, thinking, surprised,
sad, sleepy, grumpy, love, dizzy` — are the fixed set the whole project speaks in.

## How a reply flows (Phase 1)

```
you type ──▶ POST /api/say ──▶ switchboard
                                  │  1. broadcast {emotion: "thinking"}      → face shows thinking
                                  │  2. brain.respond(text)  → Ollama        → {emotion, text}
                                  │  3. voice.speak(text, emotion) → Kokoro  → WAV bytes
                                  └─ 4. broadcast {type:"say", emotion, text, audio}
                                                                             ▼
                                          face: set pose · play WAV (Web Audio) ·
                                          mouth-openness = live audio amplitude (RMS)
```

- **Structured emotion:** the brain is asked for `{"emotion","text"}` via a JSON schema,
  and `brain.parse_reply` is paranoid — strips `<think>`/code fences, digs the JSON out
  of noise, validates the emotion, and never crashes (worst case: speaks the prose).
- **Voice is swappable:** everything routes through `voice.speak(text, emotion)`. Kokoro
  is the first engine; Orpheus / ElevenLabs (Phase 6) drop in behind the same call.
- **Lip-sync** is amplitude-only (loud = open), measured from the exact buffer that
  plays, so it stays in sync. No phoneme mapping.

## Layout

```
companion/
├── backend/
│   ├── main.py        # switchboard + WebSocket hub + /api/say orchestration
│   ├── config.py      # settings, .env, the canonical emotion set
│   ├── brain.py       # Ollama call, parrot personality, robust JSON parsing
│   ├── voice/
│   │   ├── __init__.py        # speak(text, emotion) dispatcher + WAV helper
│   │   ├── kokoro_engine.py   # Kokoro TTS (Phase 1)
│   │   ├── orpheus_engine.py  # stub (Phase 6)
│   │   └── elevenlabs_engine.py # stub (Phase 6)
│   ├── senses/        # the event bus   (stub — Phase 4)
│   └── channels/      # telegram + web  (stub — Phase 3)
├── frontend/
│   ├── face.html / face.css / face.js   # the creature + lip-sync playback
│   └── control.html                     # the phone/desktop text box
├── data/              # memory.json / state.json land here (Phase 5+)
├── requirements.txt
└── .env.example
```
