"""Channels — Telegram (Phase 3).

Text the creature from anywhere. Telegram relays the messages, so there's no
port-forwarding and nothing exposed on your home network. An incoming message
runs the *same* conversation as the keyboard/voice: the creature speaks on the Go
**and** replies to you in the chat — optionally as a spoken voice note.

python-telegram-bot is imported lazily, so the server runs fine without it; the
bot only starts when ``TELEGRAM_TOKEN`` is set.
"""

from __future__ import annotations

import asyncio
import io
import logging

from .. import config, voice

log = logging.getLogger("companion.telegram")

# Injected at start(): async (text) -> {"emotion", "text", ...}. This is the same
# start_conversation() the rest of the app uses, so a text drives the face too.
_converse = None


def _allowed(update) -> bool:
    if not config.TELEGRAM_ALLOWED_IDS:
        return True
    uid = str(update.effective_user.id) if update.effective_user else ""
    return uid in config.TELEGRAM_ALLOWED_IDS


async def _voice_note(text: str, emotion: str):
    """Synthesize the reply and transcode WAV -> OGG/Opus (a real voice note).

    Returns a file-like, or ``None`` if voice or ffmpeg isn't available — in which
    case the text reply still went out.
    """
    try:
        wav = await voice.speak(text, emotion)
    except Exception:
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", "pipe:0", "-c:a", "libopus", "-b:a", "48k", "-f", "ogg", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return None  # no ffmpeg on PATH
    out, _ = await proc.communicate(wav)
    if proc.returncode == 0 and out:
        buf = io.BytesIO(out)
        buf.name = "reply.ogg"
        return buf
    return None


async def _on_start(update, _context):
    if not _allowed(update):
        return
    await update.message.reply_text(f"hi, I'm {config.CREATURE_NAME}. talk to me 🦜")


async def _on_text(update, context):
    if not _allowed(update):
        await update.message.reply_text("we haven't met — your Telegram id isn't on the allow-list.")
        return
    text = (update.message.text or "").strip()
    if not text or _converse is None:
        return
    try:
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
    except Exception:
        pass
    reply = await _converse(text)            # also speaks on the Go
    out = (reply.get("text") or "").strip() or "…"
    await update.message.reply_text(out)
    if config.TELEGRAM_VOICE:
        note = await _voice_note(out, reply.get("emotion") or "neutral")
        if note is not None:
            try:
                await update.message.reply_voice(voice=note)
            except Exception:
                log.exception("sending voice note failed")


async def start(converse_fn):
    """Start long-polling if a token is set. Returns the Application, or None."""
    global _converse
    if not config.TELEGRAM_TOKEN:
        return None
    try:
        from telegram.ext import Application, CommandHandler, MessageHandler, filters
    except ImportError:
        log.warning("python-telegram-bot not installed; Telegram channel disabled.")
        return None

    _converse = converse_fn
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", _on_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_text))
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    log.info("Telegram channel live.")
    return application


async def stop(application) -> None:
    if application is None:
        return
    try:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
    except Exception:
        log.exception("error stopping Telegram channel")
