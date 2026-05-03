"""Config loader. Reads from .env in one of:

  1. $CTXANT_CONFIG_DIR/.env                              (override for dev/tests)
  2. ~/Library/Application Support/ctxant/.env            (Mac install location)
  3. ./.env relative to the process cwd                  (legacy / project-local)

The first file that exists wins. This lets a PyInstaller-bundled ctxant.app read
user-editable config from a writable location while local `python main.py`
development keeps using the repo's .env.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _config_dir() -> Path:
    """Directory where CtxAnt stores user-editable config. Matches db.py."""
    env = os.getenv("CTXANT_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ctxant"
    return Path.home() / ".ctxant"


def _load_env() -> None:
    """Load .env from the first candidate path that exists."""
    candidates = [
        _config_dir() / ".env",
        Path.cwd() / ".env",
    ]
    for p in candidates:
        if p.exists():
            load_dotenv(p)
            return
    # No .env anywhere — that's fine for the first-run onboarding case;
    # the wizard will create one before the bot actually tries to start.


_load_env()


AI_PROVIDER = os.getenv("AI_PROVIDER", "grok").lower()  # "grok" or "claude"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4-1-fast-reasoning")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_USERS = [
    int(uid.strip())
    for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")
    if uid.strip()
]

WS_SECRET = os.getenv("WS_SECRET", "change-me")
WS_PORT = int(os.getenv("WS_PORT", "8765"))
CHROME_EXTENSION_ID = os.getenv("CHROME_EXTENSION_ID", "").strip()
CHROME_EXTENSION_DEV_IDS = [
    ext_id.strip()
    for ext_id in os.getenv("CHROME_EXTENSION_DEV_IDS", "").split(",")
    if ext_id.strip()
]
CHROME_EXTENSION_ALLOW_ANY_DEV_ORIGIN = os.getenv("CHROME_EXTENSION_ALLOW_ANY_DEV_ORIGIN", "0") == "1"
CHROME_WEB_STORE_URL = os.getenv("CHROME_WEB_STORE_URL", "").strip()


def allowed_extension_origins() -> set[str]:
    ids = set(CHROME_EXTENSION_DEV_IDS)
    if CHROME_EXTENSION_ID:
        ids.add(CHROME_EXTENSION_ID)
    return {f"chrome-extension://{ext_id}" for ext_id in ids}


def is_extension_origin_allowed(origin: str) -> bool:
    if origin in allowed_extension_origins():
        return True
    if CHROME_EXTENSION_ALLOW_ANY_DEV_ORIGIN and origin.startswith("chrome-extension://"):
        return True
    return False


def is_configured() -> bool:
    """True if the minimum viable env is in place to boot the backend.

    Used by ctxant_app.py to decide whether to launch the onboarding wizard.
    """
    provider = os.getenv("AI_PROVIDER", "grok").lower()
    if provider == "claude":
        has_key = bool(os.getenv("ANTHROPIC_API_KEY", ""))
    else:
        has_key = bool(os.getenv("XAI_API_KEY", ""))
    if not has_key:
        return False

    has_token = bool(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    if has_token:
        return True

    try:
        import db

        db.conn()
        row = db.query_one("SELECT id FROM bots WHERE role='hub' LIMIT 1")
        return row is not None
    except Exception:
        return False


def env_path() -> Path:
    """Canonical path where the onboarding wizard should write the .env."""
    d = _config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / ".env"
