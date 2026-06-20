"""The switchboard.

Phase 0 responsibilities (and *only* these):
  * Serve the frontend (the alive face).
  * Expose a WebSocket hub so emotions can be pushed to the face.
  * Offer a tiny HTTP poke (`POST /api/emotion/{name}`) that broadcasts an
    emotion to every connected face — proves the nerve works end-to-end before
    the brain exists to drive it in Phase 1.

There is deliberately no brain, no voice, and no game here yet. This file is the
spine those later layers plug into: they will all end up calling
`hub.broadcast({"type": "emotion", ...})` and nothing else needs to change.
"""

from __future__ import annotations

import asyncio
import base64
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import brain, config, voice

log = logging.getLogger("companion")


class Hub:
    """The nervous system, in miniature.

    Every connected face is a subscriber. Anything that wants the creature to
    react just calls `broadcast(...)`. In Phase 0 that's the debug HTTP poke; in
    Phase 1 it's the brain; in Phase 4 it's the senses bus. Same door for all.
    """

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        async with self._lock:
            targets = list(self._clients)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    @property
    def count(self) -> int:
        return len(self._clients)


hub = Hub()
app = FastAPI(title=f"{config.CREATURE_NAME} — companion")

# Serialize conversations so replies (and their audio) never overlap on the face.
_speak_lock = asyncio.Lock()


async def converse(text: str) -> dict:
    """The Phase 1 core, streamed for a near-real-time feel.

    1. Push ``thinking`` immediately.
    2. Stream tokens from the brain. The reply begins with ``[emotion]`` — the
       moment we parse it we push the pose (no waiting for the whole reply).
    3. As complete clauses/sentences arrive, hand them to the voice and stream the
       audio chunks to the face, which queues and plays them gaplessly while the
       model is still generating the rest.

    A worker consumes a queue so synthesis overlaps generation; chunks stay in
    order. Voice failures degrade gracefully (face + pose, just silent).
    """
    text = (text or "").strip()
    if not text:
        return {"emotion": "curious", "text": "hm? you didn't say anything.",
                "spoke": False, "voice_error": None}

    async with _speak_lock:
        await hub.broadcast({"type": "emotion", "emotion": "thinking"})

        q: asyncio.Queue = asyncio.Queue()
        state = {"voice_error": None}

        async def consumer() -> None:
            while True:
                item = await q.get()
                if item is None:
                    return
                sentence, emo = item
                if state["voice_error"]:
                    continue  # voice known-bad; drain the rest quietly
                try:
                    wav = await voice.speak(sentence, emo)
                    await hub.broadcast({
                        "type": "speak",
                        "audio": base64.b64encode(wav).decode("ascii"),
                        "mime": "audio/wav",
                    })
                except voice.VoiceUnavailable as e:
                    state["voice_error"] = str(e)
                    log.warning("voice unavailable — speaking silently: %s", e)
                except Exception as e:  # never let TTS take down the reply
                    state["voice_error"] = f"voice error: {e}"
                    log.exception("voice synthesis failed")

        consumer_task = asyncio.create_task(consumer())

        emotion: str | None = None
        buf = ""
        parts: list[str] = []
        first_chunk = True
        try:
            async for delta in brain.stream_tokens(text):
                buf += delta
                if emotion is None:
                    stripped = brain.strip_leading_think(buf)
                    if stripped is None:
                        continue  # a <think> block is open; wait it out
                    emo, rest = brain.split_emotion_prefix(stripped)
                    if emo is not None:
                        emotion = emo
                        await hub.broadcast({"type": "emotion", "emotion": emotion})
                        buf = rest
                    elif len(stripped) >= 40 or any(p in stripped for p in ".!?"):
                        emotion = "neutral"  # model skipped the tag; stop waiting
                        await hub.broadcast({"type": "emotion", "emotion": emotion})
                        buf = stripped
                    else:
                        continue
                while True:
                    chunk, buf = brain.take_chunk(buf, allow_comma=first_chunk)
                    if chunk is None:
                        break
                    if chunk:
                        parts.append(chunk)
                        await q.put((chunk, emotion))
                        first_chunk = False
        except Exception:
            log.exception("brain stream failed")
            if emotion is None:
                emotion = "dizzy"
                await hub.broadcast({"type": "emotion", "emotion": emotion})
            if not parts:
                parts.append(brain.BRAIN_DOWN_TEXT)
                await q.put((brain.BRAIN_DOWN_TEXT, emotion))

        if emotion is None:
            emotion = "neutral"
            await hub.broadcast({"type": "emotion", "emotion": emotion})
        tail = buf.strip()
        if tail:
            parts.append(tail)
            await q.put((tail, emotion))

        await q.put(None)
        await consumer_task

        full = " ".join(p for p in parts if p).strip()
        if full:
            brain.remember(text, full)
        return {
            "emotion": emotion,
            "text": full,
            "spoke": state["voice_error"] is None and bool(full),
            "voice_error": state["voice_error"],
        }


async def _warmup() -> None:
    """Load the model + voice into memory so the first real turn is snappy."""
    await brain.warmup()
    try:
        await voice.speak("ready", "neutral")  # forces Kokoro to load its ONNX
    except Exception:
        pass


@app.on_event("startup")
async def _on_startup() -> None:
    if config.WARMUP:
        asyncio.create_task(_warmup())


class SayIn(BaseModel):
    text: str


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(config.FRONTEND_DIR / "face.html")


@app.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "name": config.CREATURE_NAME,
            "faces_connected": hub.count,
        }
    )


@app.get("/api/emotions")
async def emotions() -> JSONResponse:
    """The canonical emotion set. The frontend fetches this so the face and the
    backend can never disagree about what poses exist."""
    return JSONResponse({"emotions": config.EMOTIONS, "name": config.CREATURE_NAME})


@app.post("/api/emotion/{name}")
async def set_emotion(name: str) -> JSONResponse:
    """Broadcast an emotion to every connected face.

    The Phase 0 way to drive the creature from outside the browser (curl, the
    forthcoming phone page, etc.). Unknown emotions are rejected so typos don't
    silently no-op.
    """
    if name not in config.EMOTIONS:
        return JSONResponse(
            {"ok": False, "error": f"unknown emotion: {name}", "known": config.EMOTIONS},
            status_code=400,
        )
    await hub.broadcast({"type": "emotion", "emotion": name})
    return JSONResponse({"ok": True, "emotion": name, "faces": hub.count})


@app.get("/control")
async def control_page() -> FileResponse:
    """The phone/desktop control page: a text box to message the creature.
    Point any device on the same wi-fi at http://<this-machine>:PORT/control ."""
    return FileResponse(config.FRONTEND_DIR / "control.html")


@app.post("/api/say")
async def api_say(body: SayIn) -> JSONResponse:
    """Message the creature. It thinks, replies out loud on the face, and we
    return the reply text so the sender (phone page) can show it too."""
    return JSONResponse(await converse(body.text))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    """A face connects here. Two-way, but it mostly *listens*.

    - ``emotion`` messages are relayed to all faces (Phase 0 debug seam).
    - ``say`` messages run a full conversation turn (handy for the phone page /
      debug); the spoken reply is broadcast to every face.
    """
    await hub.connect(ws)
    try:
        await ws.send_json({"type": "hello", "name": config.CREATURE_NAME})
        while True:
            data = await ws.receive_json()
            if not isinstance(data, dict):
                continue
            kind = data.get("type")
            if kind == "emotion":
                emo = data.get("emotion")
                if emo in config.EMOTIONS:
                    await hub.broadcast({"type": "emotion", "emotion": emo})
            elif kind == "say":
                text = data.get("text", "")
                if isinstance(text, str) and text.strip():
                    # don't block this socket's read loop while generating
                    asyncio.create_task(converse(text))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await hub.disconnect(ws)


# Serve the rest of the frontend (face.js, face.css, assets) as static files.
# Mounted last so it never shadows the API routes above.
app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")


def _run_server() -> None:
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


def main() -> None:
    """Entry point.

    Default: just run the server; open http://HOST:PORT in a browser (or, on the
    Legion Go, `msedge --kiosk --app=...`).

    With USE_WEBVIEW=true: spin the server on a background thread and open a
    chrome-less fullscreen pywebview window — the real on-device experience.
    pywebview is an optional dependency so headless/dev boxes don't need it.
    """
    url = f"http://{config.HOST}:{config.PORT}"
    if not config.USE_WEBVIEW:
        print(f"  {config.CREATURE_NAME} is waking up at {url}")
        print("  (set USE_WEBVIEW=true for the fullscreen desktop window)")
        _run_server()
        return

    try:
        import threading

        import webview  # type: ignore
    except ImportError:
        print("pywebview not installed; falling back to plain server.")
        print("  pip install pywebview   # then set USE_WEBVIEW=true")
        _run_server()
        return

    threading.Thread(target=_run_server, daemon=True).start()
    webview.create_window(
        config.CREATURE_NAME,
        url,
        fullscreen=True,
        background_color="#0d0d1a",
    )
    webview.start()


if __name__ == "__main__":
    main()
