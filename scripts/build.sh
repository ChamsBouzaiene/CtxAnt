#!/usr/bin/env bash
# build.sh — produce release artifacts in dist/.
#
# Builds:
#   dist/CtxAnt.dmg                  — Mac app bundle, drag-to-Applications
#   dist/CtxAnt-extension-v*.zip     — Chrome MV3 zip (load-unpacked / CWS)
#
# Uses installer/build_mac.sh under the hood (PyInstaller + create-dmg).
# Rename is deliberate: URL consistency — install.sh, latest.json, and the
# GitHub release asset all refer to CtxAnt.dmg (capitalized).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "→ Building .app + .dmg via installer/build_mac.sh"
./installer/build_mac.sh --dmg

if [ ! -f dist/CtxAnt.dmg ]; then
  echo "ERROR: dist/CtxAnt.dmg missing after build — check build_mac.sh output." >&2
  exit 1
fi

echo "→ Zipping extension"
./scripts/zip_extension.sh

echo
echo "✓ Artifacts:"
ls -lh dist/CtxAnt.dmg dist/CtxAnt-extension-v*.zip
