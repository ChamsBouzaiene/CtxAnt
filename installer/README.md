# CtxAnt Mac installer

Produces `dist/ctxant.app` (a menu-bar-only macOS app) and optionally
`dist/ctxant.dmg` (a drag-to-Applications disk image).

## Quick build

```bash
# from the repo root
pip install -r backend/requirements.txt
./installer/build_mac.sh
open dist/ctxant.app
```

For a distributable `.dmg`:

```bash
brew install create-dmg
./installer/build_mac.sh --dmg
```

## What ends up in the bundle

- `backend/*.py` — frozen into the main executable.
- `extension/` — copied in so users can "Load Unpacked" from the
  menu-bar action after the first launch.
- `Info.plist` — written inline in `ctxant.spec`. Sets `LSUIElement=1`
  so CtxAnt only shows in the menu bar (no Dock icon).

## First-run behaviour

On first launch, `ctxant_app.py` notices there's no configured `.env`
at `~/Library/Application Support/ctxant/.env` and opens the pywebview
onboarding wizard. After the user fills in token + AI key + Telegram
user id, the wizard writes the `.env` and the backend starts.

## Icon

Drop a `.icns` file at `installer/icon.icns` and uncomment the `icon=`
line in `ctxant.spec`. Easiest path: design a 1024×1024 PNG and run
`iconutil -c icns icon.iconset/` after creating the standard iconset
sizes.

## Code signing + notarization (deferred)

For the initial launch we ship unsigned — Gatekeeper will require the
user to right-click → Open on first launch. Signing + notarizing needs
a $99/yr Apple Developer account. Add `codesign_identity` and an
`entitlements_file` to `ctxant.spec` when we're ready to pay for that.
