#!/usr/bin/env bash
#
# Build ctxant.app and (optionally) wrap it in a drag-to-Applications .dmg.
#
# Prereqs:
#   python3 -m pip install -r backend/requirements.txt
#   brew install create-dmg       # only for the .dmg step
#
# Usage:
#   ./installer/build_mac.sh              # build .app only
#   ./installer/build_mac.sh --dmg        # also build ctxant.dmg
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "→ cleaning previous build"
rm -rf build dist

# Prefer the repo-local .venv if present, otherwise fall back to system
# python3. Override with `PYTHON=/path/to/bin/python ./installer/build_mac.sh`.
if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
  else
    PYTHON="python3"
  fi
fi
echo "→ running PyInstaller (using $PYTHON)"
"$PYTHON" -m PyInstaller installer/ctxant.spec --noconfirm

if [[ ! -d "dist/CtxAnt.app" ]]; then
  echo "✗ build failed — dist/CtxAnt.app not found"
  exit 1
fi

echo "→ CtxAnt.app built at $(pwd)/dist/CtxAnt.app"

if [[ "${1:-}" == "--dmg" ]]; then
  if ! command -v create-dmg >/dev/null 2>&1; then
    echo "✗ create-dmg not installed. Run: brew install create-dmg"
    exit 1
  fi

  DMG="dist/CtxAnt.dmg"
  rm -f "$DMG"

  echo "→ building $DMG"
  create-dmg \
    --volname "CtxAnt" \
    --window-pos 200 120 \
    --window-size 600 320 \
    --icon-size 96 \
    --icon "CtxAnt.app" 160 120 \
    --app-drop-link 440 120 \
    --no-internet-enable \
    "$DMG" \
    "dist/CtxAnt.app"

  echo "→ done: $DMG"
fi

echo "✓ build complete"
