"""Mac menu-bar app entry point.

Run order:
    1. If `.env` doesn't have the minimum config, launch the pywebview
       onboarding wizard and block on it. When it returns, reload config.
    2. If still unconfigured, show an alert and quit.
    3. Spawn main.main() (the asyncio backend) on a background thread.
    4. Run rumps on the main thread (menu-bar icon + menu + refresh timer).

Why sequential, not concurrent: on macOS only the main thread can drive UI,
and both pywebview and rumps want the main thread. We run pywebview first
(it blocks on its own runloop until the window closes), then hand the main
thread to rumps.

This file is the PyInstaller entry (see installer/ctxant.spec).
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

import config
import crash_reporter
import updater
from __version__ import __version__ as APP_VERSION

logger = logging.getLogger(__name__)


def _asset_path(name: str) -> str | None:
    """Return the path to a bundled asset in both dev and PyInstaller builds.

    PyInstaller unpacks data files into ``sys._MEIPASS`` at launch. In dev we
    read straight from the source tree. We check several candidate layouts
    because the spec has shipped things under both ``assets/`` and
    ``backend/assets/`` historically — future-proofing.
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        candidates += [base / "assets" / name, base / "backend" / "assets" / name]
    candidates.append(Path(__file__).parent / "assets" / name)
    for p in candidates:
        if p.exists():
            return str(p)
    return None


# ── Logging: also tee to a file the menu bar can open ────────────────────────

def _log_path() -> Path:
    d = Path.home() / "Library" / "Logs" / "ctxant"
    d.mkdir(parents=True, exist_ok=True)
    return d / "ctxant.log"


def _init_logging() -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt)
    # Add file handler
    try:
        fh = logging.FileHandler(_log_path(), encoding="utf-8")
        fh.setFormatter(logging.Formatter(fmt))
        logging.getLogger().addHandler(fh)
    except Exception:
        pass


# ── Backend boot (runs in a worker thread) ────────────────────────────────────

_backend_loop: asyncio.AbstractEventLoop | None = None
_backend_error: str | None = None
_backend_thread: threading.Thread | None = None


def _run_backend() -> None:
    """Entry point for the worker thread. Runs main.main() in its own loop."""
    global _backend_loop, _backend_error
    try:
        import main  # noqa: E402 — imported here so config loads first
        loop = asyncio.new_event_loop()
        _backend_loop = loop
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main.main())
    except Exception:
        _backend_error = traceback.format_exc()
        logger.exception("Backend crashed")


def _start_backend_thread_once() -> None:
    """Spawn the backend worker if it isn't running yet. Idempotent.

    Called from two places:
      (a) normally at startup when .env is already configured, and
      (b) from the onboarding wizard's ``save_config`` callback the
          moment the user clicks Finish — this is what lets the hub
          bot start polling Telegram while the user is still looking
          at the "Connected" screen, rather than after they dismiss
          the window.

    The module-level config must be reloaded before boot so the freshly
    written .env values are visible to ``main.main()``.
    """
    global _backend_thread
    if _backend_thread is not None and _backend_thread.is_alive():
        return  # already running — this is a re-entrant safety net

    # Ensure any env vars just written by the wizard are picked up.
    import importlib
    importlib.reload(config)

    _backend_thread = threading.Thread(
        target=_run_backend, name="ctxant-backend", daemon=True
    )
    _backend_thread.start()
    logger.info("Backend thread started")


# ── Menu-bar app ──────────────────────────────────────────────────────────────

def _build_menu_app():
    """Construct the rumps.App subclass. Import rumps lazily so unit tests
    don't require it and so the non-Mac dev path stays clean."""
    import rumps  # type: ignore

    class ctxantApp(rumps.App):
        def __init__(self) -> None:
            # We ship a proper template PNG instead of an emoji/text title:
            # emoji glyphs in the menu bar render small, and a text title
            # ("🪄 CtxAnt") bloats the width on already-crowded notched
            # MacBooks. A 44×44 template image — solid black on transparent,
            # which macOS auto-tints for light/dark menu bars — reads
            # instantly and doesn't compete for horizontal space.
            icon = _asset_path("menubar.png")
            if icon:
                super().__init__("CtxAnt", title=None, icon=icon, template=True)
            else:
                # Fallback if the asset didn't bundle — better than crashing.
                logger.warning("menubar.png missing; falling back to emoji title")
                super().__init__("CtxAnt", title="🪄 CtxAnt")
            self.menu = [
                rumps.MenuItem("Status: starting…", callback=None),
                None,  # separator
                rumps.MenuItem("Open Dashboard", callback=self.open_dashboard),
                rumps.MenuItem("Open hub bot in Telegram", callback=self.open_hub),
                rumps.MenuItem("Deployed bots", callback=None),  # replaced by submenu below
                None,
                rumps.MenuItem("Open Chrome extensions page", callback=self.open_extensions),
                rumps.MenuItem("Open config folder", callback=self.open_config_dir),
                rumps.MenuItem("View logs", callback=self.open_logs),
                None,
                # "Check for updates" morphs into "⬆ Update to vX.Y.Z" when the
                # updater finds a newer release — same slot, different label +
                # callback. Keeps the menu layout stable.
                rumps.MenuItem(f"Check for updates… (v{APP_VERSION})",
                               callback=self.check_updates),
                rumps.MenuItem("Restart CtxAnt", callback=self.restart),
            ]
            # Cache: UpdateInfo currently surfaced in the menu, or None.
            self._update_available: updater.UpdateInfo | None = None
            self._last_update_poll: float = 0.0
            self._refresh_menu()

        # ── Menu builders ────────────────────────────────────────────────────

        def _status_line(self) -> str:
            if _backend_error:
                return "Status: ❌ crashed (see logs)"
            if _backend_loop is None:
                return "Status: starting…"
            return "Status: ✅ running"

        def _refresh_menu(self) -> None:
            """Update the status line and the 'Deployed bots' submenu."""
            import rumps  # local to keep import lazy
            self.menu["Status: starting…"].title = self._status_line()  # title of first row

            # Rebuild deployed-bots submenu
            submenu = rumps.MenuItem("Deployed bots")
            rows = self._safe_deployed_rows()
            if not rows:
                submenu.add(rumps.MenuItem("— none yet —", callback=None))
            else:
                for r in rows:
                    role = r.get("role")
                    if role == "hub":
                        label = f"🏠 hub — @{r.get('username') or '?'}"
                    else:
                        slug = r.get("agent_slug") or "?"
                        uname = r.get("username") or "?"
                        label = f"🤖 {slug} — @{uname}"
                    item = rumps.MenuItem(label, callback=None)
                    submenu.add(item)

            # Replace existing submenu in-place
            try:
                self.menu["Deployed bots"].clear()
                # rumps doesn't expose a clean "replace submenu". Simplest: pop + reinsert.
                # The pop API is positional; easier to set individual items.
                for key in list(self.menu["Deployed bots"].keys()):
                    del self.menu["Deployed bots"][key]
                for key, val in submenu.items():
                    self.menu["Deployed bots"][key] = val
            except Exception:
                # If we can't refresh in-place, ignore; next tick will try again.
                logger.debug("Deployed bots submenu refresh failed", exc_info=True)

        def _safe_deployed_rows(self) -> list[dict]:
            """Pull the bot list without crashing if the backend isn't up yet."""
            try:
                import bots
                return bots.deployed_rows()
            except Exception:
                return []

        # ── Timer: tick every 5s to refresh status + bot list ────────────────

        @rumps.timer(5)
        def _tick(self, _) -> None:
            self._refresh_menu()
            # Surface a crash exactly once with a notification
            if _backend_error and not getattr(self, "_notified_crash", False):
                self._notified_crash = True
                try:
                    rumps.notification(
                        title="CtxAnt crashed",
                        subtitle="Click 'View logs' in the menu for details.",
                        message=_backend_error.splitlines()[-1][:180],
                    )
                except Exception:
                    pass

            # Poll the updater at most once a minute. updater.check_now()
            # itself has a 6h throttle before it touches the network, so
            # this is cheap — the per-minute gate here just keeps us from
            # hitting sqlite twelve times a minute for no reason.
            import time as _time
            now = _time.time()
            if now - self._last_update_poll > 60:
                self._last_update_poll = now
                try:
                    self._poll_update()
                except Exception:
                    logger.debug("update poll errored", exc_info=True)

        def _poll_update(self) -> None:
            info = updater.check_now()
            if info is None:
                return
            if (self._update_available
                    and self._update_available.version == info.version):
                # Already showing the badge for this version.
                return
            self._update_available = info

            # Morph the "Check for updates…" slot into an actionable item.
            try:
                # rumps indexes menu items by their current title, so we have
                # to look up by whatever the slot currently shows.
                for key in list(self.menu.keys()):
                    if key.startswith("Check for updates") or key.startswith("⬆ Update"):
                        item = self.menu[key]
                        del self.menu[key]
                        new_title = f"⬆ Update to v{info.version}"
                        new_item = rumps.MenuItem(
                            new_title, callback=self.install_update
                        )
                        # Reinsert in the same spot (above "Restart CtxAnt").
                        self.menu.insert_before("Restart CtxAnt", new_item)
                        break
            except Exception:
                logger.debug("Couldn't morph update menu item", exc_info=True)

            # One-shot macOS notification — don't re-fire every minute.
            if not updater.already_notified(info.version):
                updater.mark_notified(info.version)
                try:
                    rumps.notification(
                        title=f"CtxAnt v{info.version} is available",
                        subtitle="Click the menu bar to update.",
                        message=(info.notes or
                                 "Open CtxAnt in the menu bar and click "
                                 "“Update to v" + info.version + "”."),
                    )
                except Exception:
                    pass

        # ── Menu actions ─────────────────────────────────────────────────────

        def open_dashboard(self, _) -> None:
            """Open the localhost dashboard in the user's default browser.
            Served by pairing.py on :8766 so we piggyback the already-running
            aiohttp app; no new port, no pywebview-inside-rumps conflicts."""
            webbrowser.open("http://127.0.0.1:8766/dashboard")

        def open_hub(self, _) -> None:
            # Deep-link to the hub bot if we know its username
            row = next((r for r in self._safe_deployed_rows() if r.get("role") == "hub"), None)
            if row and row.get("username"):
                webbrowser.open(f"https://t.me/{row['username']}")
            else:
                rumps.alert(
                    title="Hub bot isn't ready yet",
                    message=(
                        "Either the backend is still starting or the hub bot hasn't "
                        "checked in with Telegram yet. Try again in a few seconds."
                    ),
                )

        def open_extensions(self, _) -> None:
            # chrome://extensions can't be opened via webbrowser — nudge via AppleScript
            try:
                subprocess.run(
                    ["open", "-a", "Google Chrome", "chrome://extensions"],
                    check=False,
                )
            except Exception:
                logger.exception("Failed to open chrome://extensions")

        def open_config_dir(self, _) -> None:
            path = config.env_path().parent
            path.mkdir(parents=True, exist_ok=True)
            subprocess.run(["open", str(path)], check=False)

        def open_logs(self, _) -> None:
            p = _log_path()
            if p.exists():
                subprocess.run(["open", str(p)], check=False)
            else:
                rumps.alert("No logs yet.")

        def check_updates(self, _) -> None:
            """Force an immediate check, bypassing the 6h throttle.

            Used when the user clicks "Check for updates…" — they want
            an answer now, not at the next scheduled poll.
            """
            info = updater.check_now(force=True)
            if info is None:
                rumps.alert(
                    title="You're up to date",
                    message=f"CtxAnt v{APP_VERSION} is the latest release.",
                )
                return
            # Morph the menu item and ask the user if they want to install.
            self._update_available = info
            try:
                for key in list(self.menu.keys()):
                    if key.startswith("Check for updates") or key.startswith("⬆ Update"):
                        del self.menu[key]
                        self.menu.insert_before(
                            "Restart CtxAnt",
                            rumps.MenuItem(
                                f"⬆ Update to v{info.version}",
                                callback=self.install_update,
                            ),
                        )
                        break
            except Exception:
                logger.debug("Couldn't morph update menu item", exc_info=True)
            self.install_update(None)

        def install_update(self, _) -> None:
            """Run the curl installer in Terminal after a confirmation prompt.

            We don't auto-exec without asking: unsigned-app updates involve
            the user's /Applications directory and we'd rather be explicit
            than surprising. The curl installer itself handles stopping
            the running CtxAnt before overwriting.
            """
            info = self._update_available
            if info is None:
                rumps.alert("No update is queued. Click 'Check for updates…' first.")
                return
            resp = rumps.alert(
                title=f"Install CtxAnt v{info.version}?",
                message=(
                    "A Terminal window will open and run the official "
                    "install script. CtxAnt will restart when it's done.\n\n"
                    "After install: open chrome://extensions and click "
                    "Reload on CtxAnt so Chrome picks up the new extension.\n\n"
                    f"Release notes: {info.notes[:240] or '(none provided)'}"
                ),
                ok="Install",
                cancel="Not now",
            )
            if resp != 1:  # 1 == OK
                return
            try:
                updater.open_terminal_install(info.install_script_url)
            except Exception:
                logger.exception("Failed to launch Terminal install")
                rumps.alert(
                    "Couldn't open Terminal automatically.",
                    "Run this manually:\n\ncurl -fsSL "
                    "https://ctxant.com/install.sh | sh",
                )

        def restart(self, _) -> None:
            # Easiest restart: relaunch ourselves and exit.
            # PyInstaller: sys.executable is the bundled binary.
            try:
                subprocess.Popen([sys.executable, *sys.argv])
            finally:
                os._exit(0)

    return ctxantApp


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    _init_logging()
    # Install crash hooks as early as possible — we want to catch failures
    # from anywhere, including onboarding or menu-bar init. The sys + thread
    # hooks are global; the asyncio one gets installed separately inside
    # the backend worker because it's loop-bound.
    crash_reporter.install()
    logger.info("Starting CtxAnt menu-bar app")

    # 1. First-run? Launch onboarding.
    #
    # Boot ordering subtlety: the wizard runs on the main thread (pywebview
    # needs the Cocoa runloop), so we can't race ahead of it. But we don't
    # have to wait for the *window* to close either — we pass a callback
    # that fires the instant .env is written, so the backend starts in a
    # worker thread while the user is still on step 5 ("You're set up"),
    # instead of only after they dismiss the window. That's the difference
    # between "app appears frozen until I close this" and "backend already
    # running by the time I alt-tab to Telegram".
    if not config.is_configured():
        logger.info("No config found — launching onboarding wizard")
        try:
            import onboarding
            onboarding.run_wizard_blocking(
                on_config_saved=_start_backend_thread_once,
            )
        except Exception:
            logger.exception("Onboarding wizard failed to run")

        # Defensive reload in case the wizard was dismissed without firing
        # the callback (dev paths, crashes). _start_backend_thread_once
        # also reloads config, but it's cheap and idempotent.
        import importlib
        importlib.reload(config)
        if not config.is_configured():
            logger.error("Still not configured after wizard — aborting")
            try:
                import rumps
                rumps.alert(
                    title="Setup incomplete",
                    message="CtxAnt needs a bot token and an AI key to run. "
                            "Re-launch CtxAnt to try again.",
                )
            except Exception:
                pass
            return

    # 2. Start the backend (no-op if the wizard callback already did it).
    _start_backend_thread_once()

    # 3. Run menu bar on the main thread
    ctxantApp = _build_menu_app()
    ctxantApp().run()


if __name__ == "__main__":
    main()
