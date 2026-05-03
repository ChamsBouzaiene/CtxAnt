"""Multi-bot runtime.

One Python process runs N `telegram.ext.Application` instances concurrently
— one per row of the `bots` table. All Applications share the same event loop,
the same Chrome, the same SQLite, and the same AI client.

Roles:
    - hub    : the control/coordination bot. Exactly one row. Uses hub_handlers.
    - agent  : bound to a single agent_slug. 0..N rows. Uses agent_handlers.

Public API:
    start_all()              -> start every enabled bot row. Must be awaited
                                inside an already-running event loop.
    stop_all()               -> graceful shutdown of every running Application.
    spawn_agent_bot(token,
                    agent_slug,
                    owner_chat_id) -> register a new agent bot in DB and boot
                                      its Application immediately.
    remove_agent_bot(bot_id) -> stop + delete. Keeps the agent_memory.
    get_app_for_agent(slug)  -> the Application bound to an agent (for scheduler
                                to DM the user from the right bot).
    get_hub_app()            -> the hub Application (for startup banners, etc.).
    ensure_hub_from_env()    -> insert a hub row from TELEGRAM_BOT_TOKEN if the
                                table is empty. Migration convenience.

Multi-platform note (Phase 5 roadmap — NOT implemented yet):
    This module is deliberately coupled to python-telegram-bot. When Slack /
    WhatsApp support lands, we'll introduce a BotAdapter abstraction and port
    Telegram to be its first implementation. Until then, keep all
    transport-specific code in THIS FILE only — agents.py, scheduler.py,
    claude_agent.py, and db.py stay transport-agnostic, which is what makes
    the eventual refactor tractable rather than a rewrite.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Callable

from telegram import Bot, Update
from telegram.error import InvalidToken, TelegramError
from telegram.ext import Application, ContextTypes

import db
from config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)


# ── Module state ──────────────────────────────────────────────────────────────

# Running applications, keyed by bot_id from the `bots` table.
_running: dict[int, Application] = {}

# Map agent_slug -> bot_id so scheduler / hub can find the right bot quickly.
_slug_to_bot_id: dict[str, int] = {}
_hub_bot_id: int | None = None

# Handler-builder callables, injected by whoever wires this module up
# (typically main.py / ctxant_app.py). Each takes an Application and attaches
# handlers appropriate for its role.
_hub_wire: Callable[[Application], None] | None = None
_agent_wire: Callable[[Application, str], None] | None = None  # (app, agent_slug)


def register_wiring(hub_wire: Callable, agent_wire: Callable) -> None:
    """Inject the handler factories.

    `hub_wire(app)`:          attaches hub handlers (import late to dodge cycles)
    `agent_wire(app, slug)`:  attaches agent handlers bound to `slug`
    """
    global _hub_wire, _agent_wire
    _hub_wire = hub_wire
    _agent_wire = agent_wire


# ── DB helpers ────────────────────────────────────────────────────────────────

def _rows() -> list[dict]:
    return [dict(r) for r in db.query(
        "SELECT * FROM bots WHERE enabled=1 ORDER BY role DESC, id"
    )]


def _insert(token: str, role: str, agent_slug: str | None,
            display_name: str | None, username: str | None,
            owner_chat_id: int | None) -> int:
    cur = db.execute(
        "INSERT INTO bots(token, role, agent_slug, display_name, username, owner_chat_id) "
        "VALUES(?,?,?,?,?,?)",
        (token, role, agent_slug, display_name, username, owner_chat_id),
    )
    return cur.lastrowid


def _update_meta(bot_id: int, display_name: str | None, username: str | None) -> None:
    db.execute(
        "UPDATE bots SET display_name=?, username=? WHERE id=?",
        (display_name, username, bot_id),
    )


def _delete(bot_id: int) -> None:
    db.execute("DELETE FROM bots WHERE id=?", (bot_id,))


def ensure_hub_from_env() -> int | None:
    """If the bots table has no hub row and the env has a token, seed one.

    Called on first launch so existing single-bot installs transition smoothly.
    Returns the hub bot_id or None if nothing was done.
    """
    existing = db.query_one("SELECT id FROM bots WHERE role='hub'")
    if existing:
        return existing["id"]
    token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        return None
    bot_id = _insert(
        token=token, role="hub", agent_slug=None,
        display_name=None, username=None, owner_chat_id=None,
    )
    logger.info(f"Seeded hub bot from env (bot_id={bot_id})")
    return bot_id


# ── Token validation ──────────────────────────────────────────────────────────

async def validate_token(token: str) -> dict:
    """Call the Bot API `getMe` to confirm a token is alive and return meta."""
    try:
        probe = Bot(token)
        me = await probe.get_me()
    except InvalidToken as e:
        raise ValueError(f"Invalid bot token: {e}") from e
    except TelegramError as e:
        raise ValueError(f"Token rejected by Telegram: {e}") from e
    return {
        "id":       me.id,
        "username": me.username or "",
        "name":     me.first_name or me.username or "bot",
    }


# ── Global error handler ──────────────────────────────────────────────────────

async def _on_handler_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Surface unhandled handler exceptions to the user instead of swallowing them.

    Without this, python-telegram-bot just logs errors and the chat goes silent
    — which is exactly the UX failure we hit when an agent's run raised and
    the user thought the bot had ignored them.
    """
    logger.exception("Unhandled bot error", exc_info=context.error)
    # Best-effort reply — if this itself fails we just log.
    try:
        chat_id = None
        if isinstance(update, Update):
            if update.effective_chat:
                chat_id = update.effective_chat.id
        if chat_id is not None:
            err_str = str(context.error) if context.error else "unknown error"
            # Keep the message short; the log has the full traceback.
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "⚠️ I hit an error handling that message:\n"
                    f"`{err_str[:400]}`\n\n"
                    "Try again, or /reset if I'm stuck in a weird state."
                ),
                parse_mode="Markdown",
            )
    except Exception:
        logger.exception("Failed to deliver error message to user")


# ── Application lifecycle ─────────────────────────────────────────────────────

async def _build_and_start(row: dict) -> Application | None:
    """Build a telegram.ext.Application from a DB row, wire handlers, start polling."""
    if _hub_wire is None or _agent_wire is None:
        raise RuntimeError("bots.register_wiring() must be called before start_all()")

    try:
        app = Application.builder().token(row["token"]).build()
    except InvalidToken:
        logger.warning(f"Invalid token for bot_id={row['id']} (role={row['role']}); skipping")
        return None

    if row["role"] == "hub":
        _hub_wire(app)
    else:
        if not row["agent_slug"]:
            logger.warning(f"Agent bot_id={row['id']} has no agent_slug; skipping")
            return None
        _agent_wire(app, row["agent_slug"])

    # Always attach the universal error handler so nothing goes silent on a crash.
    app.add_error_handler(_on_handler_error)

    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
    except TelegramError as e:
        logger.warning(f"Bot {row['id']} failed to start: {e}")
        try:
            await app.shutdown()
        except Exception:
            pass
        return None

    # Refresh cached metadata from the running bot
    try:
        me = await app.bot.get_me()
        _update_meta(row["id"], display_name=me.first_name, username=me.username)
    except Exception:
        pass

    return app


async def start_all() -> None:
    """Spawn pollers for every enabled row in the bots table."""
    global _hub_bot_id
    _running.clear()
    _slug_to_bot_id.clear()
    _hub_bot_id = None

    for row in _rows():
        app = await _build_and_start(row)
        if app is None:
            continue
        _running[row["id"]] = app
        if row["role"] == "hub":
            _hub_bot_id = row["id"]
        elif row["agent_slug"]:
            _slug_to_bot_id[row["agent_slug"]] = row["id"]

    logger.info(
        f"Multi-bot runtime: {len(_running)} bots online "
        f"(hub={'ok' if _hub_bot_id else 'missing'}, "
        f"agents={list(_slug_to_bot_id.keys())})"
    )


async def stop_all() -> None:
    """Gracefully shut down every running Application."""
    for bot_id, app in list(_running.items()):
        try:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        except Exception as e:
            logger.warning(f"Shutdown error on bot_id={bot_id}: {e}")
    _running.clear()
    _slug_to_bot_id.clear()


# ── Runtime mutation (used by /deploy wizard) ─────────────────────────────────

async def spawn_agent_bot(token: str, agent_slug: str,
                          owner_chat_id: int | None = None) -> dict:
    """Validate token, persist to DB, start the Application. Returns the row dict.

    Raises ValueError if the token is bad or an agent bot for that slug is
    already running for this owner.
    """
    # Sanity check: agent exists in registry
    if not db.query_one("SELECT 1 FROM agents WHERE slug=?", (agent_slug,)):
        raise ValueError(f"Unknown agent slug: {agent_slug}")

    # Enforce one agent bot per (slug, owner) — matches the bots table UNIQUE.
    if agent_slug in _slug_to_bot_id:
        raise ValueError(f"An agent bot for '{agent_slug}' is already running")

    meta = await validate_token(token)

    bot_id = _insert(
        token=token, role="agent", agent_slug=agent_slug,
        display_name=meta["name"], username=meta["username"],
        owner_chat_id=owner_chat_id,
    )
    row = dict(db.query_one("SELECT * FROM bots WHERE id=?", (bot_id,)))

    app = await _build_and_start(row)
    if app is None:
        _delete(bot_id)
        raise ValueError("Token validated but Application failed to start")

    _running[bot_id] = app
    _slug_to_bot_id[agent_slug] = bot_id
    logger.info(f"Spawned agent bot @{meta['username']} for slug={agent_slug}")
    return row


async def remove_agent_bot(bot_id: int) -> bool:
    """Stop + delete the agent bot row. Agent memory is preserved."""
    app = _running.pop(bot_id, None)
    # Drop reverse index
    for slug, bid in list(_slug_to_bot_id.items()):
        if bid == bot_id:
            _slug_to_bot_id.pop(slug, None)
    if app is not None:
        try:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        except Exception as e:
            logger.warning(f"Stop error while removing bot_id={bot_id}: {e}")
    _delete(bot_id)
    return True


# ── Lookups ───────────────────────────────────────────────────────────────────

def get_hub_app() -> Application | None:
    return _running.get(_hub_bot_id) if _hub_bot_id is not None else None


def get_app_for_agent(agent_slug: str) -> Application | None:
    bot_id = _slug_to_bot_id.get(agent_slug)
    return _running.get(bot_id) if bot_id is not None else None


def deployed_agent_slugs() -> list[str]:
    return list(_slug_to_bot_id.keys())


def deployed_rows() -> list[dict]:
    """Fresh read of all enabled bots, for the hub's /agents listing."""
    return _rows()
