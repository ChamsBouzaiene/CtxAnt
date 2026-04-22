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


def is_configured() -> bool:
    """True if the minimum viable env is in place to boot the backend.

    Used by ctxant_app.py to decide whether to launch the onboarding wizard.
    """
    has_token = bool(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    provider = os.getenv("AI_PROVIDER", "grok").lower()
    if provider == "claude":
        has_key = bool(os.getenv("ANTHROPIC_API_KEY", ""))
    else:
        has_key = bool(os.getenv("XAI_API_KEY", ""))
    return has_token and has_key


def env_path() -> Path:
    """Canonical path where the onboarding wizard should write the .env."""
    d = _config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / ".env"
