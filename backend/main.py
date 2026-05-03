import asyncio
import io
import logging
import os

import browser_bridge
import crash_reporter
import db
import pairing
import scheduler
from config import AI_PROVIDER, TELEGRAM_BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Toggle: multi-bot is the new default. Set CTXANT_MULTI_BOT=0 to fall back to
# the legacy single-bot telegram_handler path (useful while iterating).
_MULTI_BOT = os.getenv("CTXANT_MULTI_BOT", "1") != "0"


async def _run_multi_bot():
    """Multi-bot runtime: hub + any deployed agent bots."""
    import agent_handlers
    import agents
    import bots
    import claude_agent
    import hub_handlers

    # Seed the agent registry (idempotent).
    agents.seed_starter_pack()
    # Seed the hub bot from env if the bots table is empty.
    bots.ensure_hub_from_env()

    # Inject handler factories so bots.py can wire each Application.
    bots.register_wiring(hub_handlers.wire, agent_handlers.wire)

    # Scheduler callback: route scheduled runs to the owning agent bot.
    async def _run_on_schedule(chat_id: int, macro_name: str,
                               agent_slug: str | None = None):
        """Fired by APScheduler. Pushes results via the agent bot (not the hub)."""
        if not agent_slug:
            logger.warning(f"Legacy schedule fired without agent_slug: chat={chat_id}")
            return
        app = bots.get_app_for_agent(agent_slug)
        if app is None:
            logger.warning(
                f"Schedule fired for {agent_slug} but its bot isn't running"
            )
            return
        spec = agents.get(agent_slug) or {"emoji": "🤖"}
        system = agents.render_prompt(chat_id, agent_slug)
        try:
            reply, shots = await claude_agent.process_message(
                chat_id=chat_id,
                user_text="[scheduled run] Use my saved settings to do your job now.",
                agent_slug=agent_slug,
                system_prompt=system,
            )
        except Exception as e:
            logger.exception("Scheduled agent run failed")
            try:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=f"{spec['emoji']} scheduled run failed: {e}",
                )
            except Exception:
                pass
            return
        # Push output from the owning agent bot (not the hub).
        try:
            for img in shots:
                await app.bot.send_photo(chat_id=chat_id, photo=io.BytesIO(img))
            if reply:
                await app.bot.send_message(chat_id=chat_id, text=reply)
        except Exception:
            logger.exception("Failed to deliver scheduled output")

    scheduler.init(run_macro_cb=_run_on_schedule)

    # Bring up all enabled bots.
    await bots.start_all()

    if bots.get_hub_app() is None:
        logger.error(
            "No hub bot is running. Paste a TELEGRAM_BOT_TOKEN in .env "
            "(the hub) and re-start."
        )

    logger.info("CtxAnt multi-bot runtime is running. Press Ctrl+C to stop.")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Shutting down multi-bot runtime…")
        scheduler.shutdown()
        await bots.stop_all()


async def _run_single_bot():
    """Legacy single-bot path (pre-multi-bot). Kept behind CTXANT_MULTI_BOT=0."""
    import telegram_handler

    token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        raise RuntimeError(
            "Legacy single-bot mode requires TELEGRAM_BOT_TOKEN in .env. "
            "Use multi-bot mode to boot from the persisted bots table."
        )

    app = telegram_handler.build_application(token)
    scheduler.init(run_macro_cb=telegram_handler.run_macro_for_schedule)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    logger.info("CtxAnt (legacy single-bot) is running. Press Ctrl+C to stop.")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Shutting down legacy bot…")
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


async def main():
    # Route unhandled asyncio task errors through the crash reporter so a
    # dying scheduled run or websocket callback files a crash.log entry and
    # DMs the owner, instead of python-telegram-bot's "Task exception was
    # never retrieved" noise that scrolls past in the log.
    crash_reporter.install_asyncio_handler(asyncio.get_running_loop())

    # Init DB (creates file + schema on first run) and generate WS secret.
    db.conn()
    hub_row = db.query_one("SELECT id FROM bots WHERE role='hub' LIMIT 1")
    env_token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if _MULTI_BOT:
        if not hub_row and not env_token:
            raise RuntimeError(
                "No persisted hub bot was found and TELEGRAM_BOT_TOKEN is not set in .env. "
                "This looks like a first run or a broken install: paste a hub token in .env or rerun onboarding."
            )
    elif not env_token:
        raise RuntimeError(
            "Legacy single-bot mode requires TELEGRAM_BOT_TOKEN in .env. "
            "Use multi-bot mode if you want to boot from the persisted bots table."
        )

    secret = pairing.get_or_create_secret()
    logger.info(f"AI provider: {AI_PROVIDER.upper()}")
    logger.info(f"WS_SECRET ready (auto-paired by extension) — {secret[:6]}…")

    # Always start the extension bridges regardless of bot mode.
    pair_runner = await pairing.start(port=8766)
    ws_server   = await browser_bridge.start_server()

    try:
        if _MULTI_BOT:
            await _run_multi_bot()
        else:
            await _run_single_bot()
    finally:
        ws_server.close()
        await ws_server.wait_closed()
        await pair_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
