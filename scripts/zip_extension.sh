#!/usr/bin/env bash
# zip_extension.sh — package the Chrome extension into a versioned zip.
#
# Output: dist/CtxAnt-extension-v<version>.zip, where <version> is pulled
# straight from extension/manifest.json. Uploaded as a GitHub release
# asset so early users can reinstall the extension without rebuilding
# the whole DMG.
set -euo pipefail

cd "$(dirname "$0")/.."

VER="$(python3 -c 'import json; print(json.load(open("extension/manifest.json"))["version"])')"
mkdir -p dist
OUT="dist/CtxAnt-extension-v${VER}.zip"
rm -f "$OUT"

(
  cd extension
  # Excludes: macOS detritus + anything we use only for store listing art.
  zip -qr "../${OUT}" . \
    -x '*.DS_Store' \
    -x 'store-assets/*' \
    -x '__MACOSX/*'
)

echo "→ $OUT ($(du -h "$OUT" | cut -f1))"
