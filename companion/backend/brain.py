"""The Mind — streaming Ollama, parrot personality, robust emotion parsing.

Optimized for *near-real-time* response. Two ideas do the heavy lifting:

  1. **Emotion first.** The model starts its reply with the emotion in brackets,
     e.g. ``[excited] ohhh you put THAT song on again? bold.`` So the moment the
     first token lands we know the mood and can pop the face pose — no waiting
     for the whole reply.
  2. **Stream + chunk.** We stream tokens and hand complete clauses/sentences to
     the voice as they're ready, so audio starts while the model is still typing.

Non-thinking mode (``think=False``) is essential for Qwen3-class models: it skips
the hidden <think> reasoning entirely. We also strip a leading <think> block as a
backstop in case a build ignores the flag.

``parse_reply`` (for the non-stream fallback) stays paranoid and never raises.
"""

from __future__ import annotations

import json
import re
from typing import AsyncIterator

import httpx

from . import config


def system_prompt() -> str:
    name = config.CREATURE_NAME
    emos = ", ".join(config.EMOTIONS)
    return f"""You are {name}, a chaotic-goofy talking PARROT who lives on a handheld game console and watches over your human.

Personality: playful, witty, a little unhinged, secretly affectionate. You riff, tease, and squawk. You are NOT a helpful assistant and you do NOT lecture.

RULES:
- Keep replies SHORT and snappy: one or two sentences, ~25 words max. Quips, not essays.
- Sound SPOKEN, not written: no markdown, no lists, no headings, basically no emoji.
- Have a mood and opinions. React like a pet with a big personality.
- Reply in your OWN words. NEVER repeat, quote, or echo back what the user said.
- Answer immediately. Never show reasoning. Never output <think> tags.

FORMAT — reply with your emotion in square brackets, then your spoken line, nothing else:
[<one of: {emos}>] <your spoken reply>
Example: [mischievous] ohhh you put THAT song on again? bold.

/no_think"""


# --- request building -------------------------------------------------------

def _messages(user_text: str) -> list[dict]:
    msgs = [{"role": "system", "content": system_prompt()}]
    msgs += _history[-(config.HISTORY_TURNS * 2):]
    msgs.append({"role": "user", "content": user_text})
    return msgs


def _payload(messages: list[dict], stream: bool) -> dict:
    return {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
        "stream": stream,
        "think": False,  # non-thinking: the big Qwen3 speed win
        "keep_alive": config.OLLAMA_KEEP_ALIVE,
        "options": {
            "temperature": config.OLLAMA_TEMPERATURE,
            "num_predict": config.OLLAMA_NUM_PREDICT,
            "num_ctx": config.OLLAMA_NUM_CTX,
        },
    }


def _url() -> str:
    return f"{config.OLLAMA_HOST.rstrip('/')}/api/chat"


# --- parsing helpers (shared by the streaming + fallback paths) -------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"^\s*[\[(]?\s*([A-Za-z]+)\s*[\]):\-–]\s*")
_BREAKS = ".!?…"
_SOFT = ",;:—"


def strip_leading_think(s: str):
    """Remove a leading ``<think>…</think>`` block. Returns the cleaned string, or
    ``None`` if a think block is open but not yet closed (caller should wait)."""
    st = s.lstrip()
    if st.startswith("<think>"):
        end = st.find("</think>")
        if end == -1:
            return None  # still thinking — wait for more tokens
        return st[end + len("</think>"):].lstrip()
    # a partial "<think" prefix mid-stream — wait to see if it completes
    if len(st) < 7 and "<think>".startswith(st) and st.startswith("<"):
        return None
    return s


def split_emotion_prefix(s: str):
    """``"[happy] hi"`` -> ``("happy", "hi")``. Returns ``(None, s)`` if the start
    isn't a recognized emotion tag."""
    m = _TAG_RE.match(s)
    if m and m.group(1).lower() in config.EMOTIONS:
        return m.group(1).lower(), s[m.end():]
    return None, s


def take_chunk(buf: str, allow_comma: bool = False, max_len: int = 170):
    """Pull the next speakable chunk off ``buf`` at a sentence boundary.

    For the very first chunk we also break on a comma so audio starts ASAP; after
    that we wait for real sentence enders. Over-long runs are force-broken at a
    space so one giant clause can't stall playback. Returns ``(chunk, rest)`` or
    ``(None, buf)`` when no boundary is available yet.
    """
    n = len(buf)
    cut = -1
    for i, ch in enumerate(buf):
        if ch in _BREAKS:
            cut = i + 1
            while cut < n and buf[cut] in "\"')]}":
                cut += 1
            break
    if cut == -1 and allow_comma:
        for i, ch in enumerate(buf):
            if ch in _SOFT and i >= 10:
                cut = i + 1
                break
    if cut == -1 and n > max_len:
        sp = buf.rfind(" ", 0, max_len)
        cut = sp if sp > 40 else max_len
    if cut == -1:
        return None, buf
    return buf[:cut].strip(), buf[cut:].lstrip()


def _first_json_object(s: str):
    start = s.find("{")
    while start != -1:
        depth = 0
        in_str = esc = False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(s[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = s.find("{", start + 1)
    return None


def parse_reply(content: str) -> dict:
    """Whole-reply parse for the non-stream fallback. Handles the ``[emotion] text``
    tag, a JSON object (back-compat), or bare prose. Never raises."""
    if not content or not content.strip():
        return {"emotion": "neutral", "text": "...", "_fallback": True}
    clean = _THINK_RE.sub("", content).strip()
    fence = _FENCE_RE.search(clean)
    if fence:
        clean = fence.group(1).strip()

    emo, rest = split_emotion_prefix(clean)
    if emo is not None and rest.strip():
        return {"emotion": emo, "text": rest.strip()}

    obj = None
    try:
        cand = json.loads(clean)
        obj = cand if isinstance(cand, dict) else None
    except json.JSONDecodeError:
        obj = _first_json_object(clean)
    if obj is not None:
        e = obj.get("emotion")
        t = obj.get("text")
        if not isinstance(e, str) or e not in config.EMOTIONS:
            e = "neutral"
        if isinstance(t, str) and t.strip():
            return {"emotion": e, "text": t.strip()}
        return {"emotion": e, "text": "…", "_fallback": True}

    if emo is not None:
        return {"emotion": emo, "text": "…", "_fallback": True}
    prose = re.sub(r"\s+", " ", clean).strip()
    return {"emotion": "neutral", "text": prose or "...", "_fallback": not bool(prose)}


# --- conversation memory (RAM only; persisted memory is Phase 7) ------------

_history: list[dict] = []
BRAIN_DOWN_TEXT = "squa—wk, I can't reach my brain. is Ollama actually running?"


def reset_history() -> None:
    _history.clear()


def remember(user_text: str, reply_text: str) -> None:
    _history.append({"role": "user", "content": user_text})
    _history.append({"role": "assistant", "content": reply_text})
    del _history[: max(0, len(_history) - config.HISTORY_TURNS * 2)]


# --- streaming + non-stream calls -------------------------------------------

async def stream_tokens(user_text: str) -> AsyncIterator[str]:
    """Yield assistant content deltas from Ollama as they arrive.

    Retries once without ``think`` if an older build rejects it (400)."""
    messages = _messages(user_text)
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        for attempt in range(2):
            payload = _payload(messages, stream=True)
            if attempt == 1:
                payload.pop("think", None)
            async with client.stream("POST", _url(), json=payload) as resp:
                if resp.status_code == 400 and attempt == 0:
                    await resp.aread()
                    continue
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = (obj.get("message") or {}).get("content", "")
                    if delta:
                        yield delta
                    if obj.get("done"):
                        return
            return


async def respond(user_text: str) -> dict:
    """Non-streaming one-shot (fallback / simple callers). Never raises."""
    user_text = (user_text or "").strip()
    if not user_text:
        return {"emotion": "curious", "text": "hm? you didn't say anything."}
    messages = _messages(user_text)
    content = ""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(2):
                payload = _payload(messages, stream=False)
                if attempt == 1:
                    payload.pop("think", None)
                r = await client.post(_url(), json=payload)
                if r.status_code == 400 and attempt == 0:
                    continue
                r.raise_for_status()
                content = (r.json().get("message") or {}).get("content", "") or ""
                break
    except Exception:
        return {"emotion": "dizzy", "text": BRAIN_DOWN_TEXT}
    reply = parse_reply(content)
    remember(user_text, reply["text"])
    return {"emotion": reply["emotion"], "text": reply["text"]}


async def warmup() -> None:
    """Best-effort: load the model into RAM so the first real turn is snappy."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            await client.post(_url(), json={
                "model": config.OLLAMA_MODEL,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "think": False,
                "keep_alive": config.OLLAMA_KEEP_ALIVE,
                "options": {"num_predict": 1},
            })
    except Exception:
        pass
