#!/usr/bin/env bash
# release.sh — cut a new CtxAnt release end-to-end.
#
# What it does, in order:
#   1. Prompts for new version + one-line release notes.
#   2. Bumps the version in the three places that matter:
#        backend/__version__.py     (what the running app reports)
#        extension/manifest.json    (Chrome MV3 version)
#        web/latest.json            (what the in-app updater polls)
#   3. Runs ./scripts/build.sh → dist/CtxAnt.dmg + extension zip.
#   4. Commits the bumps, tags vX.Y.Z, pushes main + tag.
#   5. Creates a GitHub Release with both artifacts attached.
#
# After this completes, Vercel auto-deploys the new web/latest.json
# within ~60s (via its GitHub integration), so any running CtxAnt
# polling the feed sees the update on its next tick.
#
# Prereqs: gh CLI authed, clean working tree, install.sh tested via
# ./scripts/test_production_local.sh.
set -euo pipefail

cd "$(dirname "$0")/.."

# Refuse to release with a dirty tree — otherwise the "Release vX.Y.Z"
# commit sweeps up whatever other edits you had open.
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree is dirty. Commit or stash first." >&2
  git status --short
  exit 1
fi

CUR="$(python3 -c 'import re, pathlib; print(re.search(r"\"([^\"]+)\"", pathlib.Path("backend/__version__.py").read_text()).group(1))')"
echo "Current version: $CUR"
read -rp "New version (e.g. $(echo "$CUR" | awk -F. '{printf "%d.%d.%d", $1, $2, $3+1}')): " NEW
[ -n "$NEW" ] || { echo "aborted (no version)"; exit 1; }

# Sanity-check format. Strictly X.Y.Z, no prefixes or suffixes.
if ! echo "$NEW" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "ERROR: version must be X.Y.Z (got '$NEW')" >&2
  exit 1
fi

read -rp "Release notes (one line): " NOTES
[ -n "$NOTES" ] || { echo "aborted (no notes)"; exit 1; }

echo "→ Bumping versions…"

python3 - "$NEW" <<'PY'
import pathlib, re, sys
new = sys.argv[1]
p = pathlib.Path("backend/__version__.py")
p.write_text(re.sub(r'"[^"]+"', f'"{new}"', p.read_text(), count=1))
print(f"  backend/__version__.py → {new}")
PY

python3 - "$NEW" <<'PY'
import json, pathlib, sys
new = sys.argv[1]
p = pathlib.Path("extension/manifest.json")
d = json.loads(p.read_text())
d["version"] = new
p.write_text(json.dumps(d, indent=2) + "\n")
print(f"  extension/manifest.json → {new}")
PY

python3 - "$NEW" "$NOTES" <<'PY'
import json, pathlib, datetime, sys
new, notes = sys.argv[1], sys.argv[2]
p = pathlib.Path("web/latest.json")
d = json.loads(p.read_text())
d["version"] = new
d["published_at"] = datetime.date.today().isoformat()
d["notes"] = notes
d["dmg_url"] = f"https://github.com/ChamsBouzaiene/CtxAnt/releases/latest/download/CtxAnt.dmg"
d["release_notes_url"] = f"https://github.com/ChamsBouzaiene/CtxAnt/releases/tag/v{new}"
p.write_text(json.dumps(d, indent=2) + "\n")
print(f"  web/latest.json → {new}")
PY

echo "→ Building artifacts…"
./scripts/build.sh

EXT_ZIP="dist/CtxAnt-extension-v${NEW}.zip"
DMG="dist/CtxAnt.dmg"
[ -f "$DMG" ] || { echo "ERROR: $DMG missing after build"; exit 1; }
[ -f "$EXT_ZIP" ] || { echo "ERROR: $EXT_ZIP missing after build"; exit 1; }

echo "→ Committing version bump…"
git add backend/__version__.py extension/manifest.json web/latest.json
git commit -m "Release v${NEW}"

echo "→ Tagging v${NEW}…"
git tag -a "v${NEW}" -m "v${NEW} — ${NOTES}"

echo "→ Pushing main + tag…"
git push origin main
git push origin "v${NEW}"

echo "→ Creating GitHub Release…"
gh release create "v${NEW}" "$DMG" "$EXT_ZIP" \
  --title "v${NEW}" \
  --notes "${NOTES}"

echo
echo "✓ Released v${NEW}."
echo "  https://github.com/ChamsBouzaiene/CtxAnt/releases/tag/v${NEW}"
echo "  Vercel will redeploy web/latest.json within ~60s; any running"
echo "  CtxAnt will surface the update on its next menu-bar tick."
