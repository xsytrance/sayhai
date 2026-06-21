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
- ✅ **Phase 1 — Brain + Voice OUT + Emotion**
- ✅ **Phase 2 — Ears (Voice IN)**
- ✅ **Phase 3 — Channels (text it from anywhere)**
- 🚧 **Phase 4 — Senses (the nervous system)** *(current — bus + clock + weather; music/motion/battery are device senses for the Go)*
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

### 5. Talk to it out loud (Phase 2 — voice in)
On the **face** window (served at `localhost`, so the mic is allowed): **hold the mic
button** (touch the Go's screen) or **hold `T`**, talk, release. It transcribes with
faster-whisper (`base.en`, auto-downloads ~150MB on first use), thinks, and replies by
voice — a full local loop, zero cloud, zero tokens. Map a Legion Go back button to `T`
for a physical push-to-talk.

**Barge-in:** start talking (press the mic / `T`) while Chatty is mid-sentence and it
**shuts up and listens** — the in-flight reply is cancelled, not just muted.

> Mic needs a secure context, so voice-in works on the Go at `localhost` (and over
> https), but **not** from a phone over plain `http://<lan-ip>`. Use Telegram (below)
> to reach it from your actual phone, anywhere.

### 6. Text it from anywhere (Phase 3 — Telegram)
Talk to Chatty from your phone over the internet — no port-forwarding, nothing
exposed on your network (Telegram relays it).

1. In Telegram, message **@BotFather** → `/newbot` → copy the token.
2. Put it in `.env`: `TELEGRAM_TOKEN=123456:ABC...` (optionally lock it to yourself
   with `TELEGRAM_ALLOWED_IDS=<your-telegram-user-id>`).
3. Restart `python -m backend.main`. Message your bot — Chatty **speaks on the Go**
   *and* replies in the chat. With `ffmpeg` installed it also sends a **voice note**
   (`TELEGRAM_VOICE=true`).

The bot starts automatically when a token is present and is silent otherwise.

### 7. It reacts on its own (Phase 4 — senses)
Everything Chatty senses is a **signal on a shared event bus** (its nervous system).
A **reactor** decides whether a signal is worth squawking about — tastefully, gated by
a **chattiness dial**, a cooldown, and "don't butt in right after you / while talking."

Live now (cross-platform): **clock** (it notices morning/evening/night) and **weather**
(Open-Meteo — comments on conditions, reacts when rain starts/stops). Set `WEATHER_LAT`/
`WEATHER_LON` in `.env` or let it auto-detect by IP.

```bash
# turn the dial (0 = never pipes up, 1 = chatty); also in .env as CHATTINESS
curl -X POST localhost:8000/api/chattiness -H 'content-type: application/json' -d '{"value":0.7}'
```

Music (now-playing + drops), motion (the Go's gyro — pickup/tilt/shake), and battery
are **device senses** scaffolded for the Legion Go; they plug into the same bus.

## Troubleshooting

Open **http://127.0.0.1:8000/api/diag** — it reports, in one glance, whether Ollama is
reachable (and has your model), the Kokoro files are present, `faster-whisper` is
installed, and `ffmpeg` is available.

- **Silent / no voice:** click the face once to unlock audio; check `kokoro_*_present`
  in `/api/diag` (files go in the `companion/` folder).
- **Mic does nothing:** the on-screen caption now tells you why (permission, missing
  STT, etc.); details also print to the browser console (`[voice]`). If diag says
  `faster_whisper: MISSING`, run `pip install faster-whisper`. Mic only works on
  `localhost`/https (not a LAN IP over http).

## Play with the face (Phase 0 controls)

Still alive on its own (blinks, eye wander, breathing). A debug panel (top-left) drives
poses by hand: keys `1–9 0 - =`, `Space` = next, `p`/click = poke, `i` = idle toggle,
`f` = fullscreen, `` ` `` = panel.

The 12 emotions — `neutral, happy, excited, mischievous, curious, thinking, surprised,
sad, sleepy, grumpy, love, dizzy` — are the fixed set the whole project speaks in.

## How a reply flows (Phase 1 — streamed for near-real-time)

```
you type ─▶ POST /api/say ─▶ switchboard.converse()
        │ broadcast {emotion:"thinking"}                         → face: thinking
        │ stream tokens from Ollama (think=false) ──┐
        │   "[excited]" parsed  ─▶ broadcast {emotion:"excited"} → face: pose pops NOW
        │   "…first clause,"    ─▶ queue ─▶ Kokoro ─▶ {type:"speak", audio} → face plays it
        │   "…rest of it."      ─▶ queue ─▶ Kokoro ─▶ {type:"speak", audio} → gapless next
        └── (synthesis overlaps generation; chunks stay in order)
                                                      ▼
                         face queues WAV chunks (Web Audio, scheduled back-to-back) ·
                         mouth-openness = live audio amplitude (RMS)
```

- **Emotion first, instantly:** the reply starts with `[emotion]`, so the face strikes
  the pose on the first token instead of after the whole reply.
- **Streamed + chunked voice:** clauses are synthesized and played as they're generated,
  so the first words land in a beat — not after a paragraph. `brain.parse_reply` (the
  non-stream fallback) still tolerates `[emotion] text`, JSON, or bare prose, strips
  `<think>`, and never crashes.
- **Voice is swappable:** everything routes through `voice.speak(text, emotion)`. Kokoro
  is the first engine; Orpheus / ElevenLabs (Phase 6) drop in behind the same call.
- **Lip-sync** is amplitude-only (loud = open), measured from the exact buffers that
  play, so it stays in sync. No phoneme mapping.

### Tuned for speed
Non-thinking mode (`think=false`, the big Qwen3 win), streamed token-by-token, short
`num_predict`, capped `num_ctx`, a long `keep_alive`, and a **startup warm-up** that
pre-loads the model + voice so the first message isn't a cold start. Knobs live in `.env`.

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
