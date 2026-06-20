"""The Mind — Ollama call, parrot personality, robust JSON emotion parsing.

Contract (the emotion spine): given the user's text, return
``{"emotion": <one of the 12>, "text": "<spoken reply>"}``. The switchboard
pushes ``emotion`` down the Phase 0 WebSocket so the face reacts, and hands
``text`` to the voice engine.

Design notes:
  * We ask Ollama for **structured output** (a JSON schema) so the model is
    constrained to valid JSON. But models lie, so ``parse_reply`` is paranoid:
    it strips <think> blocks and code fences, digs the first JSON object out of
    noise, validates the emotion, and *never raises*. Worst case it speaks the
    raw prose with a neutral face.
  * **Non-thinking mode:** we send ``think=False`` and also belt-and-suspenders
    strip any ``<think>...</think>`` the model emits anyway.
"""

from __future__ import annotations

import json
import re

import httpx

from . import config

# Build the personality once.
_EMO_LIST = ", ".join(config.EMOTIONS)


def system_prompt() -> str:
    name = config.CREATURE_NAME
    return f"""You are {name}, a chaotic-goofy talking PARROT who lives on a handheld game console and watches over your human.

Personality: playful, witty, a little unhinged, secretly affectionate. You riff, tease, and squawk. You are NOT a helpful assistant and you do NOT lecture.

RULES:
- Keep replies SHORT and snappy: one or two sentences, ~30 words max. Quips, not essays.
- Sound SPOKEN, not written: no markdown, no bullet lists, no headings. Emoji almost never.
- Have a mood and opinions. React like a pet with a big personality.
- Answer immediately. Never show your reasoning. Never output <think> tags.

You MUST reply with ONE JSON object and nothing else, in this exact shape:
{{"emotion": "<one of: {_EMO_LIST}>", "text": "<your spoken reply>"}}
Choose the emotion that matches how your reply feels."""


# JSON schema for Ollama structured outputs — constrains the model to our shape.
_FORMAT_SCHEMA = {
    "type": "object",
    "properties": {
        "emotion": {"type": "string", "enum": config.EMOTIONS},
        "text": {"type": "string"},
    },
    "required": ["emotion", "text"],
}

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

# In-character fallbacks so a glitch still feels like the creature, not a stack trace.
_BRAIN_DOWN = {
    "emotion": "dizzy",
    "text": "squa—wk, I can't reach my brain. is Ollama actually running?",
}


def _first_json_object(s: str) -> dict | None:
    """Pull the first balanced {...} out of arbitrary text and parse it."""
    start = s.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        chunk = s[start : i + 1]
                        try:
                            obj = json.loads(chunk)
                            if isinstance(obj, dict):
                                return obj
                        except json.JSONDecodeError:
                            break  # try the next '{'
        start = s.find("{", start + 1)
    return None


def parse_reply(content: str) -> dict:
    """Turn whatever the model said into a safe ``{emotion, text}``. Never raises."""
    if not content or not content.strip():
        return {"emotion": "neutral", "text": "...", "_fallback": True}

    clean = _THINK_RE.sub("", content).strip()
    fence = _FENCE_RE.search(clean)
    if fence:
        clean = fence.group(1).strip()

    obj = None
    try:
        cand = json.loads(clean)
        obj = cand if isinstance(cand, dict) else None
    except json.JSONDecodeError:
        obj = _first_json_object(clean)

    if obj is not None:
        emotion = obj.get("emotion")
        text = obj.get("text")
        if not isinstance(emotion, str) or emotion not in config.EMOTIONS:
            emotion = "neutral"
        if isinstance(text, str) and text.strip():
            return {"emotion": emotion, "text": text.strip()}
        # Structured but textless — keep the emotion, don't echo raw JSON.
        return {"emotion": emotion, "text": "…", "_fallback": True}

    # No JSON at all: speak the prose with a neutral face.
    prose = _THINK_RE.sub("", content)
    prose = _FENCE_RE.sub(r"\1", prose).strip()
    prose = re.sub(r"\s+", " ", prose)
    if not prose:
        return {"emotion": "neutral", "text": "...", "_fallback": True}
    return {"emotion": "neutral", "text": prose, "_fallback": True}


async def _chat(messages: list[dict]) -> str:
    """Call Ollama /api/chat and return the raw assistant content string.

    Tolerant of older/newer Ollama: retries without ``think`` or with a looser
    ``format`` if the server rejects those. Raises on transport failure so the
    caller can hand back an in-character fallback.
    """
    url = f"{config.OLLAMA_HOST.rstrip('/')}/api/chat"
    base = {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,  # non-thinking mode
        "format": _FORMAT_SCHEMA,
        "keep_alive": config.OLLAMA_KEEP_ALIVE,
        "options": {
            "temperature": config.OLLAMA_TEMPERATURE,
            "num_predict": config.OLLAMA_NUM_PREDICT,
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(3):
            payload = dict(base)
            if attempt >= 1:
                payload.pop("think", None)      # some builds reject think on non-thinking models
            if attempt >= 2:
                payload["format"] = "json"      # fall back from schema to plain json mode
            resp = await client.post(url, json=payload)
            if resp.status_code == 400 and attempt < 2:
                continue                        # try a more conservative payload
            resp.raise_for_status()
            data = resp.json()
            return (data.get("message") or {}).get("content", "") or ""
    return ""


# Light, RAM-only rolling history so multi-turn chat feels coherent.
# (Persisted memory is Phase 7.)
_history: list[dict] = []


def reset_history() -> None:
    _history.clear()


async def respond(user_text: str) -> dict:
    """Main entry: user text in, ``{emotion, text}`` out. Never raises."""
    user_text = (user_text or "").strip()
    if not user_text:
        return {"emotion": "curious", "text": "hm? you didn't say anything."}

    messages = [{"role": "system", "content": system_prompt()}]
    messages += _history[-(config.HISTORY_TURNS * 2):]
    messages.append({"role": "user", "content": user_text})

    try:
        content = await _chat(messages)
    except Exception:
        return dict(_BRAIN_DOWN)

    reply = parse_reply(content)
    # Remember the turn (store the clean spoken text, not the raw JSON).
    _history.append({"role": "user", "content": user_text})
    _history.append({"role": "assistant", "content": reply["text"]})
    del _history[: max(0, len(_history) - config.HISTORY_TURNS * 2)]
    return {"emotion": reply["emotion"], "text": reply["text"]}
