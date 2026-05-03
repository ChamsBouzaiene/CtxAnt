"""Handlers for the hub bot (the control/coordination Telegram bot).

The hub is where users:
    - pick which agents to deploy (`/start` shows an inline keyboard)
    - walk through the BotFather ritual to create a new agent bot (`/deploy <slug>`)
    - paste back the new token (the next text message after /deploy triggers the spawn)
    - see aggregate + per-agent usage (`/usage`)
    - stop everything globally (`/stop_all`)
    - list deployed agents (`/agents`)

Agent-specific operations (`/run`, `/settings`, `/schedule`, …) live in the
agent bot and are handled by agent_handlers.py.
"""

from __future__ import annotations

import io
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import agents
import bots
import claude_agent
import usage
from config import TELEGRAM_ALLOWED_USERS

logger = logging.getLogger(__name__)


# ── Auth ──────────────────────────────────────────────────────────────────────

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


# ── /start and agent picker ──────────────────────────────────────────────────

def _agent_picker_keyboard() -> InlineKeyboardMarkup:
    """Two-column inline keyboard listing every agent in the registry.

    The first row is always "➕ Build your own" — the custom-agent factory —
    so it reads as a primary CTA, not a footnote at the bottom of the list.
    """
    all_agents = agents.list_all()
    deployed = set(bots.deployed_agent_slugs())
    rows: list[list[InlineKeyboardButton]] = []

    # "Build your own" on its own row so it doesn't get lost next to a starter.
    rows.append([InlineKeyboardButton(
        "➕ Build your own agent",
        callback_data="build:start",
    )])

    cur: list[InlineKeyboardButton] = []
    for a in all_agents:
        marker = "✅" if a["slug"] in deployed else a["emoji"]
        label = f"{marker} {a['display_name']}"
        cur.append(InlineKeyboardButton(label, callback_data=f"deploy:{a['slug']}"))
        if len(cur) == 2:
            rows.append(cur); cur = []
    if cur:
        rows.append(cur)
    return InlineKeyboardMarkup(rows)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return

    # Deep-link payload: https://t.me/<hubbot>?start=deploy_<slug> jumps
    # straight into the deploy wizard for that slug. The dashboard's
    # 'Deploy' buttons use this so one click goes from dashboard → hub chat
    # → agent setup, without the user having to re-find the picker.
    args = context.args or []
    if args:
        payload = args[0]
        if payload.startswith("deploy_"):
            slug = payload[len("deploy_"):].lower()
            agent = agents.get(slug)
            if not agent:
                await update.message.reply_text(
                    f"Hmm — I don't have an agent called '{slug}'. "
                    f"Tap /start with no args to see the list."
                )
                return
            if slug in bots.deployed_agent_slugs():
                await update.message.reply_text(
                    f"{agent['emoji']} {agent['display_name']} is already deployed. "
                    f"Open its chat instead — see /agents."
                )
                return
            await _begin_deploy(update.effective_chat.id, slug, context)
            return

    deployed = bots.deployed_agent_slugs()
    intro = (
        "Hey — I'm CtxAnt. I run a little team of AI agents for you, each with "
        "its own Telegram bot.\n\n"
        "Tap ➕ to *build your own* (HubSpot, LinkedIn, Instagram — whatever you "
        "need), or pick a starter agent below. ✅ = already deployed."
    )
    if deployed:
        intro += f"\n\nDeployed: {', '.join('/'+s for s in deployed)}"
    await update.message.reply_text(intro, reply_markup=_agent_picker_keyboard())


async def on_picker_tap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tapped an agent button from /start."""
    query = update.callback_query
    await query.answer()
    if not query.data or not query.data.startswith("deploy:"):
        return
    slug = query.data.split(":", 1)[1]
    # Already deployed? Just nudge them to use that bot.
    if slug in bots.deployed_agent_slugs():
        row = next((r for r in bots.deployed_rows() if r["agent_slug"] == slug), None)
        uname = f"@{row['username']}" if row and row.get("username") else "its own chat"
        await query.edit_message_text(
            f"{slug} is already deployed. Go talk to it in {uname}."
        )
        return
    await _begin_deploy(update.effective_chat.id, slug, context)


# ── "Build your own agent" wizard ────────────────────────────────────────────
#
# Five questions, one at a time. State lives on context.user_data under a
# private namespace (BUILD_STEP_KEY, BUILD_ANSWERS_KEY) so it can't clash with
# the BotFather-token capture state ("awaiting_token_for") later in the flow.
#
# This is deliberately unabstracted: no BotAdapter, no generic wizard engine.
# When multi-platform lands (Phase 5), we'll generalize. For now the goal is
# the minimum surface area that works.

BUILD_STEP_KEY = "build_step"          # which question index we're awaiting
BUILD_ANSWERS_KEY = "build_answers"    # dict of question_key → user answer

# Each entry: (memory_key, question_text, required?)
BUILD_QUESTIONS: list[tuple[str, str, bool]] = [
    ("nickname",
     "What should I call this agent?\n"
     "(e.g. 'HubSpot', 'LinkedIn', 'Content Scheduler'). "
     "This becomes its display name in the picker and its prompt.",
     True),
    ("emoji",
     "Pick an emoji for it (a single character).\n"
     "Reply 'skip' to use 🤖.",
     False),
    ("description",
     "In one line, what does it do?\n"
     "(e.g. 'Follows up on warm HubSpot leads and logs notes'). "
     "Used in the agent list. Reply 'skip' to leave blank.",
     False),
    ("task",
     "Describe the standing task in detail.\n"
     "This is what runs on a bare /run or on a schedule. Be specific — URLs, "
     "steps, constraints, output format. You can always override it per-run "
     "by typing a different instruction to the agent bot.",
     True),
    ("preferences",
     "Any standing preferences?\n"
     "Tone, language, 'always cite URLs', 'pause if you hit a login wall', etc. "
     "Reply 'skip' for none.",
     False),
]


def _build_reset(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(BUILD_STEP_KEY, None)
    context.user_data.pop(BUILD_ANSWERS_KEY, None)


async def _ask_build_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send the current pending question, or finalize if we're done."""
    step = context.user_data.get(BUILD_STEP_KEY, 0)
    if step >= len(BUILD_QUESTIONS):
        await _finalize_build(chat_id, context)
        return
    key, question, required = BUILD_QUESTIONS[step]
    suffix = "" if required else "\n\n(Reply 'skip' to leave blank.)"
    await context.bot.send_message(chat_id=chat_id, text=question + suffix)


async def _start_build(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for the 'Build your own agent' wizard."""
    # Any half-finished deploy or build state starts fresh here.
    context.user_data.pop("awaiting_token_for", None)
    context.user_data[BUILD_STEP_KEY] = 0
    context.user_data[BUILD_ANSWERS_KEY] = {}
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "Let's build a custom agent. I'll ask you 5 quick things — "
            "nickname, emoji, description, task, preferences — then I'll "
            "help you pair it with a new Telegram bot."
        ),
    )
    await _ask_build_question(chat_id, context)


def _is_skip(text: str, required: bool) -> bool:
    return (not required) and text.strip().lower() in ("skip", "/skip", "-")


async def _capture_build_answer(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 text: str) -> bool:
    """If we're mid-wizard, consume this message as the current answer.

    Returns True if the message was consumed (no further handling needed).
    """
    step = context.user_data.get(BUILD_STEP_KEY)
    if step is None:
        return False
    if step >= len(BUILD_QUESTIONS):
        # Shouldn't happen — bail to a clean state.
        _build_reset(context)
        return False

    key, _q, required = BUILD_QUESTIONS[step]
    answer = text.strip()

    if _is_skip(answer, required):
        answer = ""
    elif required and not answer:
        await update.message.reply_text(
            "That one's required — please give me a short answer."
        )
        return True

    # Store.
    context.user_data.setdefault(BUILD_ANSWERS_KEY, {})[key] = answer
    context.user_data[BUILD_STEP_KEY] = step + 1
    await _ask_build_question(update.effective_chat.id, context)
    return True


async def _finalize_build(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Turn the captured answers into an agents row, then start the deploy flow."""
    answers = context.user_data.get(BUILD_ANSWERS_KEY, {})
    _build_reset(context)

    try:
        slug = agents.create_custom_agent(
            chat_id=chat_id,
            nickname=answers.get("nickname", ""),
            emoji=answers.get("emoji", ""),
            description=answers.get("description", ""),
            task=answers.get("task", ""),
            preferences=answers.get("preferences", ""),
        )
    except Exception as e:
        logger.exception("create_custom_agent failed")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Something went wrong creating the agent: {e}",
        )
        return

    a = agents.get(slug)
    emoji = (a or {}).get("emoji", "🤖")
    display_name = (a or {}).get("display_name", answers.get("nickname", "Agent"))

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🎉 *{display_name}* {emoji} is ready to deploy.\n\n"
            f"Now let's pair it with its own Telegram bot."
        ),
        parse_mode="Markdown",
    )
    # Hand off to the same BotFather ritual the starter-pack agents use.
    await _begin_deploy(chat_id, slug, context)


async def on_build_tap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tapped '➕ Build your own agent' from the picker."""
    query = update.callback_query
    await query.answer()
    if not query.data or not query.data.startswith("build:"):
        return
    await _start_build(update.effective_chat.id, context)


# ── /agents ───────────────────────────────────────────────────────────────────

async def cmd_agents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    rows = bots.deployed_rows()
    if not rows:
        await update.message.reply_text(
            "No agent bots deployed yet. Tap /start to pick one."
        )
        return
    lines = ["*Deployed bots:*"]
    for r in rows:
        if r["role"] == "hub":
            lines.append(f"  🏠 hub — @{r['username']}" if r.get("username") else "  🏠 hub")
            continue
        agent = agents.get(r["agent_slug"]) or {}
        emoji = agent.get("emoji", "🤖")
        uname = f"@{r['username']}" if r.get("username") else "(no username)"
        lines.append(f"  {emoji} {r['agent_slug']} — {uname}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /deploy flow ──────────────────────────────────────────────────────────────

DEPLOY_INSTRUCTIONS = (
    "To deploy *{display_name}* as its own Telegram bot, do this — it takes ~90 seconds:\n\n"
    "1. Open @BotFather in Telegram.\n"
    "2. Send `/newbot` to it.\n"
    "3. When it asks for a name, reply:\n"
    "   `{suggested_name}`\n"
    "4. When it asks for a username, reply with something ending in *bot*, e.g.:\n"
    "   `{suggested_username}`\n"
    "5. BotFather replies with a line starting with `HTTP API: <token>`.\n"
    "6. *Paste the token back here* as your next message.\n\n"
    "I'll wire it up and walk you through setup."
)


async def cmd_deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage: /deploy <agent_slug>\nTry /start for the picker."
        )
        return
    slug = args[0].lstrip("/").lower()
    if not agents.get(slug):
        await update.message.reply_text(
            f"No agent named '{slug}'. Known: {', '.join(a['slug'] for a in agents.list_all())}"
        )
        return
    if slug in bots.deployed_agent_slugs():
        await update.message.reply_text(
            f"{slug} is already deployed — go talk to it in its own chat."
        )
        return
    await _begin_deploy(update.effective_chat.id, slug, context)


async def _begin_deploy(chat_id: int, slug: str, context: ContextTypes.DEFAULT_TYPE):
    agent = agents.get(slug)
    if not agent:
        await context.bot.send_message(chat_id=chat_id, text=f"Unknown agent: {slug}")
        return
    # Remember we're expecting a token paste from this user next.
    context.user_data["awaiting_token_for"] = slug

    txt = DEPLOY_INSTRUCTIONS.format(
        display_name=agent["display_name"],
        suggested_name=f"My {agent['display_name']}",
        suggested_username=f"my_{slug}_bot",
    )
    await context.bot.send_message(chat_id=chat_id, text=txt, parse_mode="Markdown")


async def on_hub_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captures the pasted bot token if we're mid-/deploy.

    Otherwise it's free-form chat with the hub — currently a gentle nudge
    toward using /start to pick an agent.
    """
    if not _is_allowed(update):
        return
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.strip()

    # Are we mid-"Build your own"? Capture the answer and move to the next Q.
    if BUILD_STEP_KEY in context.user_data:
        if await _capture_build_answer(update, context, text):
            return

    # Are we expecting a bot token?
    slug = context.user_data.get("awaiting_token_for")
    if slug:
        # Telegram bot tokens look like `123456:AAABBBCCC...` (number:alphanumeric)
        if ":" in text and len(text) >= 35 and all(c.isprintable() for c in text):
            await _complete_deploy(update, context, slug, text)
            return
        await msg.reply_text(
            "That doesn't look like a bot token. Paste the full token from "
            "BotFather (it has a `:` in it)."
        )
        return

    # Default: hub free-form. Nudge the user to /start.
    await msg.reply_text(
        "Tap /start to pick a starter agent or build your own, "
        "or /agents to see what's already running."
    )


async def _complete_deploy(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           slug: str, token: str):
    chat_id = update.effective_chat.id
    agent = agents.get(slug)

    try:
        row = await bots.spawn_agent_bot(token, slug, owner_chat_id=chat_id)
    except ValueError as e:
        await update.message.reply_text(f"Couldn't deploy: {e}")
        return
    except Exception as e:
        logger.exception("spawn_agent_bot failed")
        await update.message.reply_text(f"Couldn't deploy: {e}")
        return

    # Clear the expect-token state.
    context.user_data.pop("awaiting_token_for", None)

    uname = f"@{row['username']}" if row.get("username") else "your new bot"
    await update.message.reply_text(
        f"{agent['emoji']} *{agent['display_name']}* is live as {uname}.\n\n"
        f"Open {uname} in Telegram and send /start there — it'll walk you through setup.",
        parse_mode="Markdown",
    )


# ── /usage ────────────────────────────────────────────────────────────────────

async def cmd_usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        usage.format_summary(update.effective_chat.id),
        parse_mode="Markdown",
    )


# ── /stop_all ─────────────────────────────────────────────────────────────────

async def cmd_stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    n = claude_agent.cancel_all(update.effective_chat.id)
    await update.message.reply_text(f"⏹ Stop signal sent to {n} active run(s).")


# ── /undeploy ─────────────────────────────────────────────────────────────────

async def cmd_undeploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /undeploy <slug>")
        return
    slug = args[0].lstrip("/").lower()
    rows = [r for r in bots.deployed_rows()
            if r["role"] == "agent" and r["agent_slug"] == slug]
    if not rows:
        await update.message.reply_text(f"No deployed bot for '{slug}'.")
        return
    await bots.remove_agent_bot(rows[0]["id"])
    await update.message.reply_text(
        f"Stopped and removed the {slug} bot. Memory preserved — /deploy again later to reuse it."
    )


# ── /help ─────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "I'm the CtxAnt hub. I deploy agent bots that each do one job.\n\n"
        "Commands:\n"
        "  /start — pick a starter agent or build your own\n"
        "  /agents — list deployed bots\n"
        "  /deploy <slug> — deploy an agent as its own bot\n"
        "  /undeploy <slug> — stop and remove an agent bot\n"
        "  /usage — tokens + cost across all agents\n"
        "  /stop_all — cancel every running task\n"
        "  /help — this message"
    )


# ── Wiring ────────────────────────────────────────────────────────────────────

def wire(app: Application) -> None:
    """Attach all hub handlers to an Application. Called by bots.py."""
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("agents",   cmd_agents))
    app.add_handler(CommandHandler("deploy",   cmd_deploy))
    app.add_handler(CommandHandler("undeploy", cmd_undeploy))
    app.add_handler(CommandHandler("usage",    cmd_usage))
    app.add_handler(CommandHandler("stop_all", cmd_stop_all))
    app.add_handler(CallbackQueryHandler(on_picker_tap, pattern=r"^deploy:"))
    app.add_handler(CallbackQueryHandler(on_build_tap,  pattern=r"^build:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_hub_text))
