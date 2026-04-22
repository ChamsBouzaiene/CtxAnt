"""Handlers attached to each agent bot (@JobHunterBot, @DealFinderBot, …).

An agent bot is bound to one agent_slug at wiring time. All commands on it
operate against *that* agent's memory, prompt template, schedules, and usage.

Commands:
    /start    — in-persona greeting + guided setup (if not complete)
    /run      — execute the agent against current memory (+ any args appended)
    /settings — re-walk the setup flow to update memory
    /status   — last run time + next scheduled fire (+ memory peek)
    /schedule — e.g. `/schedule every day at 9am`
    /schedules — list this agent's schedules
    /cancel   — cancel a schedule by id
    /pause / /resume — toggle this agent's schedules
    /reset    — clear this agent's conversation history (not memory)

Plain text without a command:
    → conversational message routed through this agent's prompt + memory.

Photos (with caption):
    → vision-enabled agent run.
"""

from __future__ import annotations

import asyncio
import io
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import agents
import claude_agent
import scheduler
from config import TELEGRAM_ALLOWED_USERS

logger = logging.getLogger(__name__)

# Bot-level attribute: each Application keeps its agent_slug on bot_data
# so handlers can look up which agent they belong to.
SLUG_KEY = "ctxant_agent_slug"


# ── Auth ──────────────────────────────────────────────────────────────────────

def _is_allowed(update: Update) -> bool:
    if not TELEGRAM_ALLOWED_USERS:
        return True
    user = update.effective_user
    return user.id in TELEGRAM_ALLOWED_USERS if user else False


def _slug(context: ContextTypes.DEFAULT_TYPE) -> str:
    s = context.application.bot_data.get(SLUG_KEY)
    if not s:
        raise RuntimeError("Agent bot wired without SLUG_KEY — check bots.py")
    return s


# ── Output helpers ────────────────────────────────────────────────────────────

def _split(text: str, size: int) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


async def _send_response(bot, chat_id: int, text: str, screenshots: list[bytes]):
    for img in screenshots:
        await bot.send_photo(chat_id=chat_id, photo=io.BytesIO(img))
    if text:
        for chunk in _split(text, 4096):
            await bot.send_message(chat_id=chat_id, text=chunk)
    elif not screenshots:
        await bot.send_message(chat_id=chat_id, text="Done.")


# ── Setup-flow state machine ──────────────────────────────────────────────────

PENDING_KEY = "awaiting_setup_key"  # which question key we're expecting an answer for


def _next_question_or_done(chat_id: int, slug: str) -> dict | None:
    return agents.setup_next_question(chat_id, slug)


async def _ask_next(update_or_chat, context: ContextTypes.DEFAULT_TYPE, slug: str):
    """Ask the next unanswered setup question, or announce completion."""
    chat_id = (
        update_or_chat.effective_chat.id
        if hasattr(update_or_chat, "effective_chat")
        else update_or_chat
    )
    q = _next_question_or_done(chat_id, slug)
    if q is None:
        context.user_data.pop(PENDING_KEY, None)
        a = agents.get(slug)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{a['emoji']} {a['display_name']}: ✅ Setup complete. Try /run now.",
        )
        return

    context.user_data[PENDING_KEY] = q["key"]

    prompt = q["q"]
    if q.get("type") == "choice" and q.get("options"):
        opts = "\n".join(f"  • {o}" for o in q["options"])
        prompt += f"\n\nOptions:\n{opts}\n(Reply with one of the options.)"
    elif q.get("type") == "multi_choice" and q.get("options"):
        opts = ", ".join(q["options"])
        prompt += f"\n\nReply with any combination, comma-separated. Options: {opts}"
    elif q.get("type") == "boolean":
        prompt += "\n\nReply 'yes' or 'no'."
    elif not q.get("required"):
        prompt += "\n\n(Or reply 'skip' to leave this blank.)"

    await context.bot.send_message(chat_id=chat_id, text=prompt)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    slug = _slug(context)
    a = agents.get(slug)
    chat_id = update.effective_chat.id

    greeting = (
        f"{a['emoji']} *{a['display_name']}*\n"
        f"{'─' * 20}\n"
        f"{a['description']}\n\n"
    )

    if agents.is_setup_complete(chat_id, slug):
        greeting += (
            "You're already set up. Tap a command:\n"
            "  /run — do my thing now\n"
            "  /settings — change my settings\n"
            "  /schedule <when> — run me on a schedule\n"
            "  /status — show last / next run"
        )
        await update.message.reply_text(greeting, parse_mode="Markdown")
        return

    greeting += "Let me ask a few quick things to set me up. You can skip optional ones."
    await update.message.reply_text(greeting, parse_mode="Markdown")
    await _ask_next(update, context, slug)


# ── /settings (re-walk the flow) ──────────────────────────────────────────────

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    slug = _slug(context)
    # Clear memory and re-run setup
    agents.memory_clear(update.effective_chat.id, slug)
    await update.message.reply_text("Okay, let's redo setup from scratch.")
    await _ask_next(update, context, slug)


# ── Setup answer capture (plain text when PENDING_KEY is set) ────────────────

async def _capture_setup_answer(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                key: str) -> bool:
    """If the user replies while we're awaiting a setup answer, store it.

    Returns True if this message was consumed as a setup answer.
    """
    slug = _slug(context)
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    # Find the question definition to validate the answer.
    flow = agents.setup_flow(slug)
    q = next((x for x in flow if x["key"] == key), None)
    if q is None:
        context.user_data.pop(PENDING_KEY, None)
        return False

    # Skip handling
    if not q.get("required") and text.lower() in ("skip", "/skip"):
        agents.memory_set(chat_id, slug, key, "")
        await _ask_next(update, context, slug)
        return True

    qt = q.get("type", "text")
    if qt == "choice":
        # Accept exact match or case-insensitive match on options
        opts = q.get("options", [])
        match = next((o for o in opts if o.lower() == text.lower()), None)
        if not match:
            await update.message.reply_text(
                f"Please reply with one of: {', '.join(opts)}"
            )
            return True
        agents.memory_set(chat_id, slug, key, match)
    elif qt == "multi_choice":
        opts = q.get("options", [])
        picks = [p.strip() for p in text.split(",") if p.strip()]
        normalized = []
        for p in picks:
            m = next((o for o in opts if o.lower() == p.lower()), None)
            if m:
                normalized.append(m)
        if not normalized:
            await update.message.reply_text(
                f"Please reply with one or more of: {', '.join(opts)}"
            )
            return True
        agents.memory_set(chat_id, slug, key, ",".join(normalized))
    elif qt == "boolean":
        v = text.lower() in ("yes", "y", "true", "on", "1")
        agents.memory_set(chat_id, slug, key, "yes" if v else "no")
    else:
        # text, file — store raw. (file uploads handled elsewhere if we add that.)
        agents.memory_set(chat_id, slug, key, text)

    await _ask_next(update, context, slug)
    return True


# ── /run and conversational text ──────────────────────────────────────────────

async def _keep_typing(bot, chat_id: int):
    """Re-send the typing chat-action every few seconds so the user keeps
    seeing '… is typing' for the full duration of an AI run.

    Telegram auto-expires a chat action after ~5 seconds, so a single
    send_chat_action disappears before a real agent run is done. This task
    refreshes it until cancelled.
    """
    try:
        while True:
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception:
                # Swallow transient network / rate-limit errors — keeping the
                # indicator alive is best-effort, not critical.
                pass
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        # Expected when the parent finishes the run.
        pass


async def _run_agent(chat_id: int, slug: str, extra_text: str,
                     image: bytes | None, context: ContextTypes.DEFAULT_TYPE):
    # Queued feedback if another agent holds the browser
    if claude_agent.browser_busy():
        await context.bot.send_message(
            chat_id=chat_id,
            text="⏳ Queued — the browser is busy with another agent.",
        )

    system = agents.render_prompt(chat_id, slug)
    user_text = extra_text.strip() or "Run the task now using my stored settings."

    # Keep the 'is typing' indicator alive for the duration of the run.
    typing_task = asyncio.create_task(_keep_typing(context.bot, chat_id))
    try:
        reply, shots = await claude_agent.process_message(
            chat_id=chat_id,
            user_text=user_text,
            image=image,
            agent_slug=slug,
            system_prompt=system,
        )
    except Exception as e:
        logger.exception("Agent run failed")
        await context.bot.send_message(chat_id=chat_id, text=f"Error: {e}")
        return
    finally:
        typing_task.cancel()
        # Swallow the CancelledError so we don't pollute the logs.
        try:
            await typing_task
        except asyncio.CancelledError:
            pass
    await _send_response(context.bot, chat_id, reply, shots)


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    slug = _slug(context)
    if not agents.is_setup_complete(update.effective_chat.id, slug):
        await update.message.reply_text(
            "I'm not fully set up yet. Tap /start to finish setup first."
        )
        return
    extra = " ".join(context.args or [])
    await _run_agent(update.effective_chat.id, slug, extra, None, context)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await update.message.reply_text("Unauthorized.")
        return
    slug = _slug(context)
    # Are we mid-setup? Capture answer.
    pending = context.user_data.get(PENDING_KEY)
    if pending:
        if await _capture_setup_answer(update, context, pending):
            return
    # Otherwise treat as conversational command to this agent.
    if not agents.is_setup_complete(update.effective_chat.id, slug):
        await update.message.reply_text("Let me finish setup first — tap /start.")
        return
    await _run_agent(update.effective_chat.id, slug, update.message.text or "", None, context)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    slug = _slug(context)
    msg = update.message
    photo = msg.photo[-1]
    f = await photo.get_file()
    img_bytes = bytes(await f.download_as_bytearray())
    caption = (msg.caption or "").strip()
    await _run_agent(update.effective_chat.id, slug, caption, img_bytes, context)


# ── /status ───────────────────────────────────────────────────────────────────

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    slug = _slug(context)
    chat_id = update.effective_chat.id
    mem = agents.memory_all(chat_id, slug)
    jobs = scheduler.list_for_chat(chat_id, agent_slug=slug)
    agent = agents.get(slug)

    lines = [
        f"{agent['emoji']} *{agent['display_name']}* status",
        "",
        "*Memory:*",
    ]
    if mem:
        for k, v in mem.items():
            shown = v if len(v) < 80 else v[:77] + "…"
            lines.append(f"  {k}: {shown}")
    else:
        lines.append("  (empty — /settings to fill)")
    lines.append("")
    lines.append("*Schedules:*")
    if jobs:
        for j in jobs:
            lines.append(f"  {j['id']}: {j['cron']}")
    else:
        lines.append("  (none — /schedule <when> to add)")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /schedule, /schedules, /cancel ────────────────────────────────────────────

async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    slug = _slug(context)
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage: /schedule <when>\n"
            "Examples:\n"
            "  /schedule every day at 9am\n"
            "  /schedule every 30 minutes\n"
            "  /schedule every monday at 9am"
        )
        return
    spec = " ".join(args)
    try:
        job_id = scheduler.add(update.effective_chat.id, slug, spec, agent_slug=slug)
        await update.message.reply_text(f"✅ Scheduled ({spec}) — id {job_id}")
    except Exception as e:
        await update.message.reply_text(f"Couldn't parse schedule: {e}")


async def cmd_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    slug = _slug(context)
    jobs = scheduler.list_for_chat(update.effective_chat.id, agent_slug=slug)
    if not jobs:
        await update.message.reply_text("No schedules for me yet.")
        return
    lines = [f"{j['id']}: {j['cron']}" for j in jobs]
    await update.message.reply_text("Schedules:\n" + "\n".join(lines))


async def cmd_cancel_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /cancel <schedule id>")
        return
    try:
        job_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Schedule id must be a number.")
        return
    ok = scheduler.cancel(update.effective_chat.id, job_id)
    await update.message.reply_text("Canceled." if ok else "No such schedule.")


# ── /reset (history) and /stop ────────────────────────────────────────────────

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    slug = _slug(context)
    claude_agent.clear_history(update.effective_chat.id, agent_slug=slug)
    await update.message.reply_text("Conversation history cleared.")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    slug = _slug(context)
    claude_agent.cancel(update.effective_chat.id, agent_slug=slug)
    await update.message.reply_text("⏹ Stopping current task…")


# ── Wiring ────────────────────────────────────────────────────────────────────

def wire(app: Application, agent_slug: str) -> None:
    """Attach agent handlers to an Application and pin the slug on bot_data."""
    if not agents.get(agent_slug):
        raise ValueError(f"Unknown agent: {agent_slug}")
    app.bot_data[SLUG_KEY] = agent_slug

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("run",       cmd_run))
    app.add_handler(CommandHandler("settings",  cmd_settings))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(CommandHandler("schedule",  cmd_schedule))
    app.add_handler(CommandHandler("schedules", cmd_schedules))
    app.add_handler(CommandHandler("cancel",    cmd_cancel_schedule))
    app.add_handler(CommandHandler("reset",     cmd_reset))
    app.add_handler(CommandHandler("stop",      cmd_stop))

    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
