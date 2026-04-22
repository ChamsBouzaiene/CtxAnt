#!/usr/bin/env bash
# CtxAnt — one-line installer.
#
# Usage:
#   curl -fsSL https://ctxant.com/install.sh | sh
#
# What it does, in plain English:
#   1. Downloads the latest CtxAnt.dmg from our GitHub release.
#   2. Mounts it, copies CtxAnt.app to /Applications, unmounts.
#   3. Strips the quarantine xattr so Gatekeeper doesn't block first launch.
#      (files arriving via curl have no xattr set at all — this is defensive
#      in case a user pipes it through a browser-downloaded shim.)
#   4. Kills any already-running instance and opens the new one.
#
# Why this, not the DMG-drag path?
# macOS Gatekeeper only enforces its "unidentified developer" prompt on files
# that carry the com.apple.quarantine xattr, which Safari/Chrome/Mail attach
# on download. `curl` never sets it. So a scripted install bypasses the
# scary dialog entirely — same end state as a signed+notarized app, without
# the $99/yr Apple tax. Homebrew, Ollama, Bun and Deno all ship this way.

set -euo pipefail

APP_NAME="CtxAnt"
DMG_URL="${CTXANT_DMG_URL:-https://github.com/ChamsBouzaiene/CtxAnt/releases/latest/download/CtxAnt.dmg}"
APPS_DIR="/Applications"

# ── Sanity checks ────────────────────────────────────────────────────────────
if [ "$(uname -s)" != "Darwin" ]; then
  echo "CtxAnt is macOS-only for now. Windows and Linux are on the roadmap."
  echo "Watch the repo: https://github.com/ChamsBouzaiene/CtxAnt"
  exit 1
fi

if ! command -v hdiutil >/dev/null 2>&1; then
  echo "Missing 'hdiutil' — this doesn't look like a normal macOS install." >&2
  exit 1
fi

# ── Download ────────────────────────────────────────────────────────────────
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "→ Downloading $APP_NAME…"
if ! curl -fL --progress-bar -o "$TMP/ctxant.dmg" "$DMG_URL"; then
  echo
  echo "Download failed. If you're on a work VPN, try again off VPN."
  echo "Or grab the DMG manually from:"
  echo "  https://github.com/ChamsBouzaiene/CtxAnt/releases/latest"
  exit 1
fi

# ── Mount ───────────────────────────────────────────────────────────────────
echo "→ Mounting disk image…"
MOUNT_OUT="$(hdiutil attach -nobrowse -readonly -noverify "$TMP/ctxant.dmg")"
MOUNT_POINT="$(echo "$MOUNT_OUT" | tail -1 | awk '{for(i=3;i<=NF;i++) printf "%s%s", $i, (i<NF?" ":"")}')"

if [ -z "$MOUNT_POINT" ] || [ ! -d "$MOUNT_POINT" ]; then
  echo "Couldn't find mount point for the DMG." >&2
  exit 1
fi

cleanup_mount() { hdiutil detach "$MOUNT_POINT" -quiet 2>/dev/null || true; }
trap 'cleanup_mount; rm -rf "$TMP"' EXIT

# ── Install ─────────────────────────────────────────────────────────────────
SRC_APP="$MOUNT_POINT/$APP_NAME.app"
if [ ! -d "$SRC_APP" ]; then
  echo "DMG is missing $APP_NAME.app — probably a corrupted download." >&2
  exit 1
fi

DEST="$APPS_DIR/$APP_NAME.app"

# Stop a running copy before overwriting — a live process locks files.
if pgrep -f "$APPS_DIR/$APP_NAME.app/Contents/MacOS" >/dev/null 2>&1; then
  echo "→ Stopping running $APP_NAME…"
  pkill -f "$APPS_DIR/$APP_NAME.app/Contents/MacOS" 2>/dev/null || true
  sleep 1
fi

if [ -d "$DEST" ]; then
  echo "→ Replacing existing $APP_NAME.app…"
  rm -rf "$DEST"
fi

echo "→ Installing to $APPS_DIR…"
cp -R "$SRC_APP" "$APPS_DIR/"

# Belt-and-braces: strip quarantine in case the user piped this script through
# something that re-tagged it. Harmless if the xattr isn't there.
# Note: macOS `xattr` has no -r flag, so we walk the bundle with `find`.
find "$DEST" -exec xattr -d com.apple.quarantine {} \; 2>/dev/null || true

# ── Launch ──────────────────────────────────────────────────────────────────
echo "→ Launching…"
open "$DEST"

cat <<DONE

✓ $APP_NAME installed.
  Look for the ant icon in your menu bar. First launch opens the setup wizard
  (Telegram bot token + AI key, ~90 seconds total).

Next up: install the Chrome extension → https://ctxant.com/install.html#step-3
DONE
