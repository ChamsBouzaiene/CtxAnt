#!/usr/bin/env bash
# dev.sh — run the CtxAnt backend against your local .env.
#
# Picks up the repo's .venv if present (set up once with
# `python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt`),
# otherwise falls back to system python3. Your real secrets live in
# ~/Library/Application Support/ctxant/.env and config.py loads them
# automatically — nothing in this repo ever needs them.
#
# Reminder: if the Chrome extension isn't already loaded, open
# chrome://extensions → Developer mode → Load Unpacked → pick the
# repo's extension/ folder.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3 || true)"
  if [ -z "$PY" ]; then
    echo "python3 not found and no .venv — install Python 3.10+ or create .venv first." >&2
    exit 1
  fi
  echo "(no .venv found — falling back to system python3 at $PY)"
fi

echo "→ Starting CtxAnt backend with $PY"
echo "  Load the extension at chrome://extensions if you haven't already."
echo
cd backend
exec "$PY" -u main.py
