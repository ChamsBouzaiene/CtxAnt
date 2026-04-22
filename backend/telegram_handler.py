import io
import logging
from typing import Optional

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import claude_agent
import macros
import scheduler
import usage
from config import TELEGRAM_ALLOWED_USERS

logger = logging.getLogger(__name__)

# Set at build_application time so the scheduler can push messages back.
_application: Optional[Application] = None


# ── Auth ─────────────────────────────────────────────────────────────────────

def _is_allowed(update: Update) -> bool:
    if not TELEGRAM_ALLOWED_USERS:
        logger.warning(
            "TELEGRAM_ALLOWED_USERS is not set — allowing all users. "
            "Set it in .env to restrict access."
        )
        return True
    user = update.effective_user
    allowed = user.id in TELEGRAM_ALLOWED_USERS
    if not allowed:
        logger.warning(
            "Blocked unauthorized user: id=%s username=%s name=%s",
            user.id, user.username, user.full_name,
        )
    return allowed


# ── Output helpers ───────────────────────────────────────────────────────────

async def _send_response(bot, chat_id: int, text: str, screenshots: list[bytes]):
    for img in screenshots:
        await bot.send_photo(chat_id=chat_id, photo=io.BytesIO(img))
    if text:
        for chunk in _split(text, 4096):
            await bot.send_message(chat_id=chat_id, text=chunk)
    elif not screenshots:
        await bot.send_message(chat_id=chat_id, text="Done.")


def _split(text: str, size: int) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


# ── Slash commands: reserved ─────────────────────────────────────────────────
# These are "built-in" — user-defined macros with the same name won't override them.

RESERVED = {
    "start", "help", "reset", "stop", "usage",
    "macros", "new", "delete", "install",
    "schedule", "schedules", "cancel", "myid",
}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "Hey — I'm CtxAnt. Text me anything and I'll do it in your browser.\n\n"
        "Quick start:\n"
        "• /install — load the starter-pack macros\n"
        "• /morning — a sample macro (after /install)\n"
        "• /help — all commands\n"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "Commands:\n"
        "  /reset — clear conversation history\n"
        "  /stop — cancel the current task\n"
        "  /usage — token & cost summary\n"
        "  /install — import the starter-pack macros\n"
        "\n"
        "Macros:\n"
        "  /macros — list your saved macros\n"
        "  /new <name> <prompt> — save a macro\n"
        "  /delete <name> — delete a macro\n"
        "  /<name> [args] — run a macro\n"
        "\n"
        "Scheduling:\n"
        "  /schedule <macro> <when> — e.g. `/schedule morning every day at 9am`\n"
        "  /schedules — list scheduled jobs\n"
        "  /cancel <id> — cancel a scheduled job\n"
        "\n"
        "Photos work too — send one with a caption.\n"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    claude_agent.clear_history(update.effective_chat.id)
    await update.message.reply_text("Conversation history cleared.")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    claude_agent.cancel(update.effective_chat.id)
    await update.message.reply_text("⏹ Stopping current task…")


async def cmd_usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        usage.format_summary(update.effective_chat.id),
        parse_mode="Markdown",
    )


async def cmd_install(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    n = macros.install_starter_pack(update.effective_chat.id)
    names = ", ".join(f"/{k}" for k in macros.STARTER_PACK.keys())
    await update.message.reply_text(
        f"Installed {n} new macro(s). You now have: {names}\n\n"
        "Try `/morning` or `/summary https://example.com`."
    )


async def cmd_macros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    items = macros.list_all(update.effective_chat.id)
    if not items:
        await update.message.reply_text("No macros yet. Try /install for the starter pack.")
        return
    lines = [f"/{name} — {prompt[:80]}{'…' if len(prompt) > 80 else ''}"
             for name, prompt in items]
    await update.message.reply_text("Your macros:\n\n" + "\n".join(lines))


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text('Usage: /new <name> <prompt>\ne.g. /new morning "summarize my unread emails"')
        return
    name = args[0].lstrip("/").lower()
    if name in RESERVED:
        await update.message.reply_text(f"'{name}' is a reserved command name.")
        return
    prompt = " ".join(args[1:])
    macros.save(update.effective_chat.id, name, prompt)
    await update.message.reply_text(f"Saved /{name}. Run it any time.")


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /delete <name>")
        return
    name = args[0].lstrip("/").lower()
    ok = macros.delete(update.effective_chat.id, name)
    await update.message.reply_text(f"Deleted /{name}." if ok else f"No macro named /{name}.")


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            'Usage: /schedule <macro> <when>\n'
            'Examples:\n'
            '  /schedule morning every day at 9am\n'
            '  /schedule check every 30 minutes\n'
            '  /schedule receipts every friday at 4pm'
        )
        return
    macro_name = args[0].lstrip("/").lower()
    spec = " ".join(args[1:])
    if not macros.get(update.effective_chat.id, macro_name):
        await update.message.reply_text(f"No macro named /{macro_name}. Save it first with /new.")
        return
    try:
        job_id = scheduler.add(update.effective_chat.id, macro_name, spec)
        await update.message.reply_text(f"Scheduled /{macro_name} — {spec} (id {job_id})")
    except Exception as e:
        await update.message.reply_text(f"Couldn't parse schedule: {e}")


async def cmd_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    jobs = scheduler.list_for_chat(update.effective_chat.id)
    if not jobs:
        await update.message.reply_text("No scheduled jobs.")
        return
    lines = [f"{j['id']}: /{j['macro_name']} — {j['cron']}" for j in jobs]
    await update.message.reply_text("Scheduled:\n" + "\n".join(lines))


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /cancel <id>")
        return
    try:
        job_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Job id must be a number.")
        return
    ok = scheduler.cancel(update.effective_chat.id, job_id)
    await update.message.reply_text("Canceled." if ok else "No such job.")


# ── Unknown-slash dispatcher: run macro if the name matches ──────────────────

async def on_any_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    msg = update.message
    if not msg or not msg.text:
        return
    cmd = msg.text.split()[0][1:].lower()  # drop leading '/'
    if cmd in RESERVED:
        return  # real handlers will pick it up; this is a fallback anyway

    prompt = macros.get(update.effective_chat.id, cmd)
    if not prompt:
        await msg.reply_text(f"Unknown command /{cmd}. Try /help or /macros.")
        return

    # Pass the remaining args as context to the AI
    extra = " ".join(context.args or []).strip()
    full = f"{prompt}\n\nUser arg: {extra}" if extra else prompt
    await _run_agent(update.effective_chat.id, full, None, context)


# ── Text + photo handler ─────────────────────────────────────────────────────

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        await update.message.reply_text("Unauthorized.")
        return
    await _run_agent(
        update.effective_chat.id,
        update.message.text or "",
        None,
        context,
    )


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    msg = update.message
    # Grab the highest-resolution photo
    photo = msg.photo[-1]
    file = await photo.get_file()
    img_bytes = bytes(await file.download_as_bytearray())
    caption = (msg.caption or "").strip()
    await _run_agent(update.effective_chat.id, caption, img_bytes, context)


# ── Core loop ────────────────────────────────────────────────────────────────

async def _run_agent(
    chat_id: int,
    text: str,
    image: bytes | None,
    context: ContextTypes.DEFAULT_TYPE,
):
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    try:
        reply, shots = await claude_agent.process_message(chat_id, text, image)
    except Exception as e:
        logger.exception("Error in agent")
        await context.bot.send_message(chat_id=chat_id, text=f"Error: {e}")
        return
    await _send_response(context.bot, chat_id, reply, shots)


# ── Scheduler callback: run a macro and push output to Telegram ──────────────

async def run_macro_for_schedule(chat_id: int, macro_name: str):
    if _application is None:
        logger.warning("Scheduler fired but Telegram app not ready")
        return
    prompt = macros.get(chat_id, macro_name)
    if not prompt:
        logger.warning(f"Scheduled macro /{macro_name} no longer exists for chat {chat_id}")
        return
    try:
        reply, shots = await claude_agent.process_message(
            chat_id,
            f"[scheduled run: /{macro_name}]\n{prompt}",
        )
        await _send_response(_application.bot, chat_id, reply, shots)
    except Exception as e:
        logger.exception("Scheduled macro failed")
        await _application.bot.send_message(chat_id=chat_id, text=f"Scheduled /{macro_name} failed: {e}")


# ── Build ────────────────────────────────────────────────────────────────────

def build_application(token: str) -> Application:
    global _application
    app = Application.builder().token(token).build()
    _application = app

    # Reserved commands first
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("reset",     cmd_reset))
    app.add_handler(CommandHandler("stop",      cmd_stop))
    app.add_handler(CommandHandler("usage",     cmd_usage))
    app.add_handler(CommandHandler("install",   cmd_install))
    app.add_handler(CommandHandler("macros",    cmd_macros))
    app.add_handler(CommandHandler("new",       cmd_new))
    app.add_handler(CommandHandler("delete",    cmd_delete))
    app.add_handler(CommandHandler("schedule",  cmd_schedule))
    app.add_handler(CommandHandler("schedules", cmd_schedules))
    app.add_handler(CommandHandler("cancel",    cmd_cancel))

    # Everything else that starts with / → macro dispatcher
    app.add_handler(MessageHandler(filters.COMMAND, on_any_command))

    # Photos and plain text
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    return app
