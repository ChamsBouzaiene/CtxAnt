"""crash_reporter.py — the catch-all for ugly surprises.

Three jobs:

  1. Install process-wide hooks so an exception in any thread or asyncio
     task doesn't just vanish into the log. Handler errors from
     python-telegram-bot are already surfaced to the user by
     ``bots._on_handler_error``; this module covers everything *else* —
     backend boot failures, scheduler glitches, websocket server
     explosions, background-thread accidents.

  2. Append every caught crash to ``~/Library/Logs/ctxant/crash.log`` as
     a timestamped block with the full traceback. One file per install,
     newest-at-bottom, independent of the rotating ``ctxant.log`` so users
     can grab it cleanly when filing a bug.

  3. Try to DM the hub bot's owner with a short summary via a blocking
     ``urllib.request`` call to the Telegram Bot API. We can't rely on
     an event loop being alive at the moment of a crash (the crash may
     *be* the event loop dying), so we bypass python-telegram-bot
     entirely and POST the HTTPS request on whatever thread tripped.
     If anything about sending fails, we swallow it — a crash reporter
     that crashes is worse than useless.

Anti-spam: a simple in-memory rate limiter keeps the same error from
being Telegrammed more than once per 5 minutes. The file log still
records every occurrence.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Paths ────────────────────────────────────────────────────────────────────

def _crash_log_path() -> Path:
    d = Path.home() / "Library" / "Logs" / "ctxant"
    d.mkdir(parents=True, exist_ok=True)
    return d / "crash.log"


# ── Dedup / rate-limit state ─────────────────────────────────────────────────

_DEDUP_WINDOW_SECONDS = 300  # 5 minutes
_recent_keys: dict[str, float] = {}
_state_lock = threading.Lock()


def _fingerprint(exc_type: type, tb_text: str) -> str:
    """Stable hash of (type + last stack frame) to collapse repeats."""
    last_frame = tb_text.strip().rsplit("\n", 1)[-1][:200] if tb_text else ""
    key = f"{exc_type.__name__}|{last_frame}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _should_send(key: str) -> bool:
    """True if we haven't Telegrammed this fingerprint in the last window."""
    now = time.time()
    with _state_lock:
        last = _recent_keys.get(key, 0.0)
        if now - last < _DEDUP_WINDOW_SECONDS:
            return False
        _recent_keys[key] = now
        # Trim the map if it's grown unreasonably (defensive; crashes
        # shouldn't produce thousands of distinct fingerprints).
        if len(_recent_keys) > 256:
            cutoff = now - _DEDUP_WINDOW_SECONDS
            for k, t in list(_recent_keys.items()):
                if t < cutoff:
                    _recent_keys.pop(k, None)
        return True


# ── Telegram delivery (blocking, no event loop required) ──────────────────────

def _send_telegram_alert(short_msg: str) -> None:
    """POST to the Telegram Bot API directly. Never raises."""
    try:
        # Read config lazily so we see the latest values even if the wizard
        # just wrote them; and so that importing this module at the top of
        # ctxant_app.py doesn't force config.py to load before .env exists.
        import config  # noqa: WPS433 — intentional late import
        token = os.getenv("TELEGRAM_BOT_TOKEN", config.TELEGRAM_BOT_TOKEN)
        allowed = config.TELEGRAM_ALLOWED_USERS
        if not token or not allowed:
            return
        owner_id = allowed[0]

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({
            "chat_id": owner_id,
            "text": short_msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # Timeout is deliberately tight — we're already in a crash path,
        # we don't want to block shutdown if Telegram is slow.
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.warning("Could not deliver crash alert to Telegram: %s", e)
    except Exception:
        # Never let the crash reporter itself become a crash.
        logger.exception("Unexpected failure while sending crash alert")


# ── Public entry point: record one crash ─────────────────────────────────────

def report(
    exc_type: type,
    exc_value: BaseException,
    exc_tb: Any,
    *,
    where: str = "unknown",
    extra: dict[str, Any] | None = None,
) -> None:
    """Handle one unhandled exception: log it, file it, ping the user.

    ``where`` is a short tag ("sys.excepthook", "thread:ctxant-backend",
    "asyncio:Task-5") so a user filing a bug can tell us which arm of
    the process died.
    """
    # Ignore KeyboardInterrupt / SystemExit — users expect those to be quiet.
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        return

    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 1. Regular log stream (so it's tail-able in dev too).
    logger.error("Unhandled exception in %s:\n%s", where, tb_text)

    # 2. Dedicated crash.log for easy grab-and-send.
    try:
        with _crash_log_path().open("a", encoding="utf-8") as fh:
            fh.write(f"── {ts}  [{where}] ──\n")
            if extra:
                fh.write(f"context: {extra}\n")
            fh.write(tb_text)
            fh.write("\n")
    except Exception:
        logger.exception("Failed to append to crash.log")

    # 3. Telegram alert — rate-limited so a crash loop doesn't DM-spam.
    key = _fingerprint(exc_type, tb_text)
    if not _should_send(key):
        logger.debug("Skipping Telegram alert: fingerprint %s is cooling down", key)
        return

    # Short message: last line is usually the most diagnostic; full stack
    # stays in the log. Keep under Telegram's 4096-char limit, with room
    # for Markdown overhead.
    last_line = tb_text.strip().splitlines()[-1] if tb_text.strip() else "(no traceback)"
    short = (
        "🚨 *CtxAnt crashed*\n"
        f"*Where:* `{where}`\n"
        f"*Error:* `{exc_type.__name__}: {last_line[:300]}`\n"
        "\nFull traceback in `~/Library/Logs/ctxant/crash.log`.\n"
        "Click *View logs* in the menu bar, or `tail -n 80` that file."
    )
    _send_telegram_alert(short)


# ── Hooks ────────────────────────────────────────────────────────────────────

def _sys_excepthook(exc_type, exc_value, exc_tb):
    report(exc_type, exc_value, exc_tb, where="sys.excepthook")
    # Chain to the default handler so the traceback still goes to stderr.
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    thread_name = args.thread.name if args.thread else "?"
    report(
        args.exc_type,
        args.exc_value or args.exc_type("<no value>"),
        args.exc_traceback,
        where=f"thread:{thread_name}",
    )


def install_asyncio_handler(loop) -> None:
    """Install our handler on the given asyncio loop.

    Called from inside the backend worker thread once the loop is up,
    since loop-creation and this install step must happen on the same
    thread (the loop is thread-bound).
    """
    def _asyncio_handler(_loop, context: dict) -> None:
        exc = context.get("exception")
        if exc is None:
            # Non-exception asyncio warnings (e.g. "task was destroyed but
            # it is pending"). Log but don't Telegram — too noisy.
            logger.warning("asyncio: %s", context.get("message", context))
            return
        task = context.get("task") or context.get("future")
        task_name = getattr(task, "get_name", lambda: "?")() if task else "?"
        report(
            type(exc),
            exc,
            exc.__traceback__,
            where=f"asyncio:{task_name}",
            extra={"context_message": context.get("message")},
        )

    loop.set_exception_handler(_asyncio_handler)


_installed = False


def install() -> None:
    """Install the global sys + threading hooks. Idempotent.

    Call this once, as early as possible in the process lifecycle.
    The asyncio hook is set up separately via ``install_asyncio_handler``
    because it's loop-scoped.
    """
    global _installed
    if _installed:
        return
    sys.excepthook = _sys_excepthook
    # threading.excepthook exists from Python 3.8 onward. We depend on 3.10+,
    # so this is unconditional.
    threading.excepthook = _thread_excepthook
    _installed = True
    logger.info("Crash reporter installed (crash.log: %s)", _crash_log_path())
