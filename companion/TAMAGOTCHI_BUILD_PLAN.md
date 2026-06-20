# 🦜 Project: [NAME-ME] — A Living Desktop Companion for the Lenovo Legion Go

> A bright, chaotic-goofy cartoon face that fills the whole screen, talks and listens,
> reacts to the world around it, remembers you, and grows like a Tamagotchi.
> **Local-first.** No tokens burned. Cloud voice is an optional treat, never a dependency.

This document is the master plan. Build it **phase by phase** — do **not** try to one-shot
the whole thing. Each phase has a clear deliverable and an acceptance check. Get a phase
working and *felt* before moving on.

---

## 0. The One Big Idea (read this first or nothing else makes sense)

This is not "a face with features bolted on." It's **one creature** with three layers that
constantly talk to each other:

1. **The Body** — the goofy SVG face. Always alive (blinks, breathes, eyes wander).
2. **The Mind** — Ollama (the brain) + memory + mood. Decides what to say and how it feels.
3. **The Life** — the Tamagotchi game layer (needs, XP, levels) + the senses.

The spine that connects everything is **one emotion signal**. The brain emits an emotion,
and that single value drives **three things at once**:
- the **face** pose (happy eyes, grumpy brows, dizzy spiral…)
- the **voice** delivery (calm, excited, a literal snicker on Orpheus)
- the **animation** springiness (bouncier when hyped, droopy when sleepy)

And everything the creature can sense is just a **signal on a shared event bus** (its
"nervous system"). Music changed? Rain started? Picked up? Hungry? Each is one event. The
brain decides whether it's worth squawking about. This is *why* the giant wishlist stays
sane: **adding a new sense or account later = plugging one new nerve into the same bus.**

Everything pours into three pools: **mood, memory, growth.** Keep that in mind and the
whole thing coheres.

---

## 1. Target Environment & Constraints

- **Device:** Lenovo Legion Go (OG), Windows 11, AMD Ryzen Z1 Extreme, ~16GB shared LPDDR5.
- **Display:** 8.8", 2560×1600, 144Hz. Design the face for this exact resolution, fullscreen.
- **No dedicated VRAM** — the GPU shares system RAM (configurable in BIOS, typically up to ~8GB).
  This is *the* constraint. Everything (LLM + TTS + STT + browser) shares 16GB.
- **Has a gyro/IMU** (the gyro-aim sensor). We will abuse this for "react to being held."
- **Foundation must run fully offline.** Cloud (ElevenLabs) is opt-in polish only.

**The roommate problem:** Orpheus TTS (wanted ASAP) is a ~3B model. To let it cohabit with
the LLM, the STT model, and the browser inside 16GB, keep the **LLM small** (a 3B-class
quantized model, e.g. `Q4_K_M`). Pick the brain to leave room for the voice.

---

## 2. Tech Stack (concrete choices)

| Layer | Choice | Notes |
|---|---|---|
| Backend | **Python 3.11+, FastAPI + uvicorn** | HTTP + WebSocket, async. The "switchboard." |
| Frontend window | **pywebview** (primary) or `Edge --kiosk --app` (fallback) | A clean, chrome-less fullscreen "app" feel. |
| Face | **Vanilla HTML + inline SVG + JS** | Use **anime.js** (or a tiny custom spring) for springy easing. |
| Brain | **Ollama** (HTTP API @ `localhost:11434`) | Small quantized model. Confirm which models are installed. |
| Voice OUT | **`speak()` dispatcher** with 3 engines | Kokoro (default), Orpheus (emotional), ElevenLabs (cloud). |
| — Kokoro | `kokoro-onnx` (CPU-friendly, ~82M, Apache-2.0) | The no-drama foundation. Ships in Phase 1. |
| — Orpheus | GGUF via llama.cpp / `orpheus-tts` | Emotional tags (laugh/whisper). Heavier; pull in after Phase 1. |
| — ElevenLabs | official `elevenlabs` SDK | API key from `.env`. Online-only treat. |
| Voice IN | **faster-whisper** (CTranslate2) | Use `base` or `small` for speed. Push-to-talk. |
| Audio amplitude | **sounddevice + numpy** | Drives lip-sync. Also taps the audio output (WASAPI loopback) to "hear" music. |
| Now-playing | **`winsdk`/`winrt`** → `GlobalSystemMediaTransportControlsSessionManager` | Universal Windows "now playing": title, artist, position. |
| Weather | **Open-Meteo** (no API key, free) | Clean and local-friendly. |
| Phone channel | **`python-telegram-bot`** (async) + local web page | Text it from anywhere; voice-note replies as a stretch. |
| Persistence | Plain JSON files | `memory.json`, `state.json`. Keep it simple. |

> Use `pip install --break-system-packages` in this environment. On the Legion Go itself,
> a normal venv is fine.

---

## 3. The Emotion Spine (the core contract)

The brain must return **structured output**, not just prose. Prompt Ollama to reply as JSON:

```json
{ "emotion": "mischievous", "text": "ohhh you put THAT song on again? bold.", "action": null }
```

- `emotion` ∈ a fixed set the face knows how to render.
- `text` is what gets spoken + shown.
- `action` (optional) is for game/sense hooks later (e.g. `"eat_treat"`, `"do_trivia"`).

**Starter emotion set** (each = one face pose + one voice modifier + one easing profile):
`neutral, happy, excited, mischievous, curious, thinking, surprised, sad, sleepy, grumpy, love, dizzy`

(`dizzy` is reserved for the shake-the-device reaction. `thinking` plays while Ollama is generating.)

---

## 4. Suggested Project Structure

```
companion/
├── backend/
│   ├── main.py            # FastAPI app, WebSocket hub, the switchboard
│   ├── config.py          # settings, .env, active voice engine
│   ├── brain.py           # Ollama call, personality prompt, JSON emotion parsing
│   ├── memory.py          # load/save memory.json, inject into context
│   ├── game.py            # Tamagotchi: stats, hunger, XP, levels, feeding
│   ├── voice/
│   │   ├── __init__.py    # speak(text, emotion) dispatcher
│   │   ├── kokoro_engine.py
│   │   ├── orpheus_engine.py
│   │   └── elevenlabs_engine.py
│   ├── ears.py            # faster-whisper STT + push-to-talk + barge-in
│   ├── senses/
│   │   ├── bus.py         # the event bus / nervous system
│   │   ├── music.py       # SMTC now-playing + amplitude swell detection
│   │   ├── weather.py     # Open-Meteo
│   │   ├── clock.py       # time of day + learned work routine
│   │   ├── motion.py      # gyro/IMU → pickup/tilt/shake  (RISK: needs a spike)
│   │   └── battery.py     # charging / low-battery reactions
│   └── channels/
│       ├── telegram_bot.py
│       └── web.py         # serves the phone control page
├── frontend/
│   ├── face.html
│   ├── face.js            # idle life, emotion poses, mouth flap, gyro reactions
│   └── face.css
├── data/
│   ├── memory.json
│   └── state.json
├── .env.example          # OLLAMA_MODEL, ELEVENLABS_API_KEY, TELEGRAM_TOKEN, VOICE_ENGINE
├── requirements.txt
└── README.md
```

---

## 5. The Phased Build Plan

> **Golden rule:** ship each phase to a *working, felt* state before the next.
> The `speak()` abstraction lands in Phase 1, which means **Orpheus and ElevenLabs can be
> dropped in any time after Phase 1** — they're just new engines behind the same function.
> Don't gate them to the end if you're itching for them.

### Phase 0 — Scaffold + The Alive Face (no brain yet)
Get the *vibe* on screen first; it's the riskiest aesthetic bit and the most motivating.
- Repo skeleton + FastAPI serving the frontend + a WebSocket channel.
- The **chaotic-goofy SVG face** (Rayman/emoji energy): big bold shapes, floating eyebrows,
  elastic mouth, oversized expressive eyes.
- **Idle life loop** (this is non-negotiable — it must NEVER be perfectly still):
  random blinks, lazy eye saccades/wander, gentle breathing scale, occasional brow twitch.
- A debug panel/keys to manually trigger each emotion pose.
- **Springy overshoot easing everywhere** (jiggle-to-a-stop). This single choice is what
  makes it read "goofy gremlin" vs "corporate mascot."
- ✅ **Acceptance:** fullscreen on the Go, it feels *alive and idle*, and you can flip
  through all ~12 emotion poses by hand and they look great + bouncy.

### Phase 1 — Brain + Voice OUT + Emotion (the MVP core)
- `brain.py`: send user text to Ollama with the personality system prompt; parse the
  `{emotion, text}` JSON (robust to the model adding stray text).
- `voice/`: implement the `speak(text, emotion)` dispatcher + **Kokoro** engine.
- Pipe TTS audio → **amplitude → mouth flap** in real time (volume = mouth openness).
- Emotion from the brain drives the face pose + animation springiness.
- A basic local web page to type to it (so phone-on-wifi works minimally already).
- ✅ **Acceptance:** type a message → it thinks (thinking face) → replies out loud in
  Kokoro's voice, mouth synced, face matching the mood. It feels like a *someone*.

### Phase 2 — Ears (Voice IN)
- `ears.py`: **faster-whisper** STT, **push-to-talk** (a hotkey or a Legion Go button).
- **Barge-in**: if you start talking while it's speaking, it stops and listens. (Pets
  interrupt and get interrupted — this makes conversation feel natural, not robotic.)
- ✅ **Acceptance:** hold the button, talk, release → it transcribes, thinks, and replies
  by voice. Full local voice loop, zero cloud, zero tokens.

### Phase 3 — Channels (text it from anywhere)
- `channels/telegram_bot.py`: a Telegram bot so you can text the creature **from anywhere**
  (Telegram relays — no port-forwarding, no exposing your home network).
- Polish the local web control page (mobile-friendly).
- **Stretch:** Telegram replies come back as **voice notes** (TTS → audio file → send).
  Now you can voice-chat your parrot from the grocery store while it *also* talks to your
  empty room like a lunatic. 🦜
- ✅ **Acceptance:** message from your phone (Telegram + local page) → it speaks on the Go
  and replies to you. All channels funnel through the same brain.

### Phase 4 — Senses (the nervous system comes online)
Build `senses/bus.py` first (the event bus), then add sources. **Music is priority #1.**
- **Music** (`music.py`): SMTC now-playing → react to track changes ("ooh I like this one"),
  drop artist/song facts. Reuse the **amplitude listener** to catch big musical swells →
  "ohhh THIS is my favorite part" on a drop. (Same ears, two jobs.)
- **Weather** (`weather.py`): Open-Meteo → "bring a jacket" / mood tints on rainy days.
- **Clock/routine** (`clock.py`): notices the hour; **asks you once** when you usually leave
  for work, remembers it, then runs a little morning ritual (weather + hype + reminders).
- **Motion** (`motion.py`) ⚠️ **RISK — do a spike first.** Read the Legion Go IMU on Windows
  (likely via `Windows.Devices.Sensors` Accelerometer/Gyrometer, or HID). Map to:
  pickup → eyes snap up + "whoa!"; tilt → eyes slide with gravity; **shake → `dizzy` pose**;
  set down gently → content sigh. This is the device's killer feature — worth the effort.
- **Battery** (`battery.py`): charging → happy "snacks!"; low battery → worried.
- ✅ **Acceptance:** it spontaneously reacts to a song, the weather, being picked up, and
  the time of day — unprompted, but tastefully (not spammy). Add a global "chattiness" dial.

### Phase 5 — The Tamagotchi Layer (and it must feed the mood)
- `game.py`: stats (e.g. `hunger`, `energy`, `bond`), **XP & levels**, **feeding**.
- **Feeding = two kinds:** *attention is food* (talking to it nourishes it) **+** literal
  treat button/command for dopamine.
- **CRITICAL DESIGN RULE:** the game state must **feed the emotion spine** —
  hungry → grumpy face/voice/clipped replies; just fed or leveled → bouncy & generous.
  If stats are a lonely number nobody feels, you did it wrong.
- **Leveling unlocks things**, not just a bar: new expressions, abilities (jokes, trivia,
  deeper facts), voice options, lil cosmetic accessories for the face.
- **Gentle neglect only:** ignored → sleepy/wistful, never guilt-trippy "you abandoned me"
  dark patterns. A good pet, not a needy app.
- ✅ **Acceptance:** feeding/leveling visibly changes its mood and behavior, and hitting a
  level unlocks something you can actually see or do.

### Phase 6 — Voice Upgrades (pull forward whenever you like!)
- **Orpheus** engine: emotional tags (laugh/whisper) wired so the **same emotion** from the
  brain picks the matching vocal delivery. Mind the roommate problem (small LLM).
- **ElevenLabs** engine: premium voice toggle via `.env` key; used only when online.
- ✅ **Acceptance:** flip `VOICE_ENGINE` (or per-message override) and the voice swaps with
  no other code changes. Orpheus can *snicker* on a `mischievous` reply.

### Phase 7 — The Soul Polish
- **Deeper memory:** it remembers your name, inside jokes, prior chats; injects relevant
  bits into context. (Graduate from flat notes → smarter recall later.)
- **Mood drift:** a slow-changing baseline mood, so some days it just wakes up *feeling
  chaotic* — internal weather you can sense.
- **Mimic mode** 🦜: say something, it repeats it back in a goofy voice. Peak parrot.
- **"Connect other accounts eventually"** = just new sense modules on the bus. Future-proofed.

---

## 6. Design Principles / Guardrails (pin these to the wall)

1. **Never perfectly still.** Idle life is 90% of "alive." Protect the idle loop.
2. **Springy, overshooting easing everywhere.** It's the whole goofy vibe.
3. **One emotion → three channels** (face, voice, animation). Single source of truth.
4. **Everything is an event on the bus.** New feature = new nerve, not new wiring.
5. **Local-first, always.** It must fully work offline. Cloud is a treat, never a crutch.
6. **Tasteful, not spammy.** A chattiness dial; it shouldn't narrate every heartbeat.
7. **Gentle pet psychology.** Happy to see you; never weaponizes your absence.
8. **Pick the brain to fit the voice.** Small LLM so Orpheus has room.

---

## 7. Setup Prerequisites (for the human)

- [ ] **Ollama** installed with a small chat model pulled (3B-class `Q4_K_M` recommended).
      → tell Claude which models you already have so we pick the brain.
- [ ] **Python 3.11+** + a venv.
- [ ] **Kokoro** voice files (`kokoro-onnx`).
- [ ] **faster-whisper** `base`/`small` model (auto-downloads on first run).
- [ ] **Telegram bot token** (create via @BotFather) → into `.env`.
- [ ] **ElevenLabs API key** → into `.env` (optional, for Phase 6).
- [ ] Decide the **fullscreen approach**: pywebview window vs `Edge --kiosk`.

---

## 8. Open Decisions (need your call)

1. **NAME the creature** — it becomes the wake word, so it matters. A few to riff on:
   *Squawk, Pip, Biscuit, Gizmo, Kiwi, Noodle, Waffles, Gort.* Or your own.
2. **Which Ollama model** is the brain? (List what you've got installed.)
3. **Default Kokoro voice** vibe — chill, hyper, deep, squeaky?
4. **Push-to-talk trigger** — keyboard hotkey, or map a physical Legion Go button?

---

## 9. How to Drive Claude Code Through This

- Point Claude Code at this file and say: *"Build Phase 0. Stop when the acceptance check passes."*
- Review/feel it. Then: *"Phase 1."* Repeat.
- Don't let it sprint ahead — the magic is in feeling each layer land.
- When something's off, fix it fully **before** adding the next idea. (House rule. 🛠️)
