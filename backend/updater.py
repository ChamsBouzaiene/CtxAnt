"""updater.py — check for a newer CtxAnt and nudge the user to upgrade.

We ship CtxAnt as an unsigned .app for now (launch-week — no Apple Developer
ID). That means our "push an update to my users" story can't be Sparkle
(which requires a notarized bundle to do automatic, in-place updates). So
we do the simplest thing that keeps early users reachable:

    1. On launch, and every N hours after, fetch a tiny JSON feed at
       ``https://ctxant.com/latest.json`` (Vercel-served alongside the
       landing page, so we fully control the release cadence — no GitHub
       API rate limits, no auth).
    2. Compare its ``version`` against our baked-in ``__version__.VERSION``.
       Using a naïve semver tuple compare is fine: we only ever bump
       numbers, never ship pre-release suffixes from this tree.
    3. If remote > local, surface it: menu-bar notification + a menu item
       ("⬆ Update to vX.Y.Z"). Clicking it opens a Terminal window
       preloaded with the one-line install command so the user watches
       the upgrade happen.

Why not auto-download + swap the bundle? Two reasons:
  - Replacing a running .app's own binary on macOS is fiddly (Sparkle
    uses an external helper process to do it safely). We'd be writing
    Sparkle-lite. Not worth it before we have signing anyway.
  - User consent matters. Auto-updates that surprise the user erode
    trust, especially during launch when bugs are likely.

The update check is best-effort. Any network error is swallowed — a
machine that's offline or behind a corporate proxy shouldn't spam its
user with "can't check for updates" dialogs.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

import db
from __version__ import __version__ as CURRENT_VERSION

logger = logging.getLogger(__name__)

# The feed URL. Served by the Vercel deployment of ``web/latest.json``.
# Overridable via env var for dev/testing (e.g. point at a local server,
# or at a staging Vercel preview URL).
import os

FEED_URL = os.getenv("CTXANT_UPDATE_FEED",
                     "https://ctxant.com/latest.json")

# Don't hammer the feed. The backend ticks regularly; we only actually
# hit the network once per this interval and cache the result in the
# ``kv`` table so a restart doesn't reset the clock.
CHECK_INTERVAL_SECONDS = 6 * 60 * 60  # 6h

# kv keys we own.
_KV_LAST_CHECK = "updater.last_check_ts"
_KV_LATEST_SEEN = "updater.latest_version_seen"
_KV_LATEST_JSON = "updater.latest_payload_json"
_KV_NOTIFIED_FOR = "updater.notified_for_version"


# ── Version compare ──────────────────────────────────────────────────────────

def _parse(v: str) -> tuple[int, ...]:
    """Lenient semver parse. ``"1.2.3"`` → ``(1, 2, 3)``.

    Non-numeric suffixes (``"1.2.3-beta"``) are truncated at the first
    non-digit component — we don't currently ship them, and treating them
    as equal-or-less-than the numeric version is fine for an upgrade gate.
    """
    out: list[int] = []
    for part in v.strip().lstrip("v").split("."):
        num = ""
        for ch in part:
            if ch.isdigit():
                num += ch
            else:
                break
        if not num:
            break
        out.append(int(num))
    return tuple(out) or (0,)


def is_newer(remote: str, local: str = CURRENT_VERSION) -> bool:
    """True iff ``remote`` is strictly greater than ``local``."""
    try:
        return _parse(remote) > _parse(local)
    except Exception:
        return False


# ── Feed fetch ───────────────────────────────────────────────────────────────

@dataclass
class UpdateInfo:
    version: str
    dmg_url: str
    install_script_url: str
    release_notes_url: str
    notes: str


def _fetch_feed(timeout: float = 6.0) -> dict[str, Any] | None:
    """GET the JSON feed. Returns ``None`` on any failure."""
    try:
        req = urllib.request.Request(
            FEED_URL,
            headers={"User-Agent": f"CtxAnt/{CURRENT_VERSION} updater"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError,
            json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.debug("Update check failed (benign): %s", e)
        return None
    except Exception:
        # Defensive: the updater must never crash the app.
        logger.exception("Unexpected failure in update feed fetch")
        return None


def _payload_to_info(payload: dict[str, Any]) -> UpdateInfo | None:
    """Coerce a feed payload into ``UpdateInfo`` or ``None`` if malformed."""
    ver = payload.get("version")
    if not isinstance(ver, str) or not ver.strip():
        return None
    return UpdateInfo(
        version=ver.strip(),
        dmg_url=str(payload.get("dmg_url", "")),
        install_script_url=str(
            payload.get("install_script_url", "https://ctxant.com/install.sh")
        ),
        release_notes_url=str(payload.get("release_notes_url", "")),
        notes=str(payload.get("notes", "")),
    )


# ── Public API ───────────────────────────────────────────────────────────────

def check_now(force: bool = False) -> UpdateInfo | None:
    """Check the feed and return an ``UpdateInfo`` iff remote > local.

    Safe to call from any thread. Returns cached info (from the last
    successful fetch) if the interval hasn't elapsed and ``force`` is
    false — keeps us off the wire when the menu-bar tick fires.
    """
    now = time.time()
    try:
        last_str = db.kv_get(_KV_LAST_CHECK)
        last = float(last_str) if last_str else 0.0
    except Exception:
        last = 0.0

    if not force and (now - last) < CHECK_INTERVAL_SECONDS:
        # Return the cached verdict so the menu can still show a badge.
        return _cached_info_if_newer()

    payload = _fetch_feed()
    try:
        db.kv_set(_KV_LAST_CHECK, str(now))
    except Exception:
        logger.debug("Couldn't persist last-check ts", exc_info=True)

    if not payload:
        return _cached_info_if_newer()

    info = _payload_to_info(payload)
    if info is None:
        logger.warning("Update feed returned malformed payload; ignoring")
        return _cached_info_if_newer()

    try:
        db.kv_set(_KV_LATEST_SEEN, info.version)
        db.kv_set(_KV_LATEST_JSON, json.dumps(payload))
    except Exception:
        logger.debug("Couldn't persist latest seen version", exc_info=True)

    if is_newer(info.version):
        logger.info("Update available: %s (running %s)", info.version,
                    CURRENT_VERSION)
        return info
    return None


def _cached_info_if_newer() -> UpdateInfo | None:
    """Reconstruct a cached ``UpdateInfo`` if the last-seen version is newer
    than what we're running. Used when the network is down or we're within
    the throttle window."""
    try:
        raw = db.kv_get(_KV_LATEST_JSON)
        if not raw:
            return None
        info = _payload_to_info(json.loads(raw))
        if info and is_newer(info.version):
            return info
    except Exception:
        return None
    return None


def mark_notified(version: str) -> None:
    """Record that we've already shown a notification for this version so
    we don't re-prompt every menu-bar tick."""
    try:
        db.kv_set(_KV_NOTIFIED_FOR, version)
    except Exception:
        pass


def already_notified(version: str) -> bool:
    try:
        return db.kv_get(_KV_NOTIFIED_FOR) == version
    except Exception:
        return False


# ── Upgrade action ───────────────────────────────────────────────────────────

def open_terminal_install(install_script_url: str | None = None) -> None:
    """Open a new Terminal window running the one-line install.

    We use ``osascript`` rather than ``subprocess.run('open', '-a', 'Terminal')``
    so we can preload the command in a visible window — the user sees what's
    happening, can ctrl-C if they change their mind, and ends up with a log
    of the install in their Terminal scrollback.

    Falls back to opening the install page in a browser if AppleScript
    fails for any reason (e.g. Terminal.app disabled by MDM).
    """
    import subprocess
    import webbrowser

    url = install_script_url or "https://ctxant.com/install.sh"
    # Single-quote the URL inside the shell command, escape it for AppleScript.
    shell_cmd = f'curl -fsSL {url} | sh'
    # AppleScript needs every " in the embedded script quoted.
    applescript = (
        'tell application "Terminal"\n'
        '  activate\n'
        f'  do script "{shell_cmd}"\n'
        'end tell'
    )
    try:
        subprocess.run(["osascript", "-e", applescript], check=False)
        return
    except Exception:
        logger.exception("Couldn't open Terminal; falling back to browser")
    try:
        webbrowser.open("https://ctxant.com/install.html")
    except Exception:
        pass
