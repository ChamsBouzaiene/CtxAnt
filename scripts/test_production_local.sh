#!/usr/bin/env bash
# test_production_local.sh — rehearse the curl | sh install flow offline.
#
# Why this exists: install.sh running against ctxant.com is the hottest
# path in the whole product — if it breaks, the landing page does nothing.
# This script serves web/ (including install.sh) + dist/CtxAnt.dmg on
# localhost, then pipes install.sh through sh exactly like a real user
# would, but against http://localhost:8000 instead of https://ctxant.com.
# If it installs CtxAnt.app into /Applications and launches, you know the
# production flow works before you push.
#
# Uses install.sh's existing CTXANT_DMG_URL env-var escape hatch to point
# at the localhost DMG.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

if [ ! -f "$ROOT/dist/CtxAnt.dmg" ]; then
  echo "ERROR: dist/CtxAnt.dmg missing. Run ./scripts/build.sh first." >&2
  exit 1
fi

# Symlink the DMG into web/ so the static server can serve it at /CtxAnt.dmg.
ln -sfn "$ROOT/dist/CtxAnt.dmg" "$ROOT/web/CtxAnt.dmg"

PORT=8000

# Start a throwaway HTTP server in web/. The cleanup trap kills it and
# removes the symlink even if install.sh fails halfway.
( cd "$ROOT/web" && python3 -m http.server "$PORT" >/dev/null 2>&1 ) &
SERVER_PID=$!
cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
  rm -f "$ROOT/web/CtxAnt.dmg"
}
trap cleanup EXIT INT TERM

# Give the server a moment to bind.
sleep 1

# Sanity: the endpoints the installer will touch.
echo "→ Checking localhost endpoints…"
curl -fsS "http://localhost:$PORT/install.sh" >/dev/null
curl -fsSI "http://localhost:$PORT/CtxAnt.dmg" | head -1

echo
echo "→ Running install.sh against http://localhost:$PORT"
echo "  (CTXANT_DMG_URL overrides the default GitHub URL)"
echo
CTXANT_DMG_URL="http://localhost:$PORT/CtxAnt.dmg" \
  sh -c "$(curl -fsSL http://localhost:$PORT/install.sh)"

echo
echo "✓ End-to-end install succeeded from localhost. Safe to push & release."
