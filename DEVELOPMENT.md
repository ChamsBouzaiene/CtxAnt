# Development

How to run CtxAnt from source, test each feature, build the Mac app, and understand the multi-bot runtime. If you just want to use CtxAnt, see the [README](./README.md).

## Contents

- [Quickstart commands](#quickstart-commands)
- [Running from source](#running-from-source)
- [Building locally](#building-locally)
- [Testing the production install locally](#testing-the-production-install-locally)
- [Cutting a release](#cutting-a-release)
- [How the auto-update pipeline works](#how-the-auto-update-pipeline-works)
- [Updating the extension](#updating-the-extension)
- [Where Vercel deploys from](#where-vercel-deploys-from)
- [Architecture at a glance](#architecture-at-a-glance)
- [Test scenarios — what to try in Telegram](#test-scenarios--what-to-try-in-telegram)
- [Mac app: building and iterating](#mac-app-building-and-iterating)
- [Testing the onboarding wizard without a full build](#testing-the-onboarding-wizard-without-a-full-build)
- [Iterating on the Chrome extension](#iterating-on-the-chrome-extension)
- [Releasing](#releasing)
  - [Releasing the Chrome extension](#releasing-the-chrome-extension)
  - [Releasing the Mac app](#releasing-the-mac-app)
- [Environment & file locations](#environment--file-locations)
- [Debugging tips](#debugging-tips)

---

## Quickstart commands

Every workflow is one command. Scripts live in `scripts/` and are safe to read before running.

| What | Command | Output |
|---|---|---|
| Run backend against your local `.env` | `./scripts/dev.sh` | Foreground process + Telegram bots polling |
| Build release artifacts | `./scripts/build.sh` | `dist/CtxAnt.dmg` + `dist/CtxAnt-extension-v*.zip` |
| Rehearse the production `curl \| sh` install offline | `./scripts/test_production_local.sh` | Installs `CtxAnt.app` into `/Applications` from `localhost:8000` |
| Cut a new release end-to-end | `./scripts/release.sh` | Bumps version in 3 files, tags, pushes, creates GitHub Release |

Real secrets live at `~/Library/Application Support/ctxant/.env` and are loaded automatically by `config.py`. The repo's own `.env.example` only ever holds placeholders.

---

## Building locally

```bash
./scripts/build.sh
```

This calls `installer/build_mac.sh --dmg` under the hood (PyInstaller + `create-dmg`), then renames `dist/ctxant.dmg` → `dist/CtxAnt.dmg` so the filename matches everything else (install.sh, `latest.json`, the release asset URL). It also zips the extension at `dist/CtxAnt-extension-v<version>.zip`.

Both artifacts are `.gitignore`d. They're uploaded to GitHub Releases by `scripts/release.sh`, not committed.

---

## Testing the production install locally

`install.sh` is the highest-stakes file on the landing page — if it breaks, the "copy this into Terminal" step does nothing. Rehearse it before every release:

```bash
./scripts/build.sh                  # produce dist/CtxAnt.dmg
./scripts/test_production_local.sh  # serve web/ + the DMG on localhost:8000 and run install.sh against it
```

This uses the same code path prod users hit (`curl -fsSL … | sh`), just pointed at `http://localhost:8000` via `install.sh`'s `CTXANT_DMG_URL` env var. If it installs CtxAnt into `/Applications` and the menu-bar icon appears, you're safe to push.

---

## Cutting a release

```bash
./scripts/release.sh
# Prompts: new version (e.g. 0.2.0), one-line release notes.
```

What it does, in order:

1. Refuses to run with a dirty tree.
2. Bumps the version in the **three** places it lives:
   - `backend/__version__.py` — what the running app reports, what the updater compares against.
   - `extension/manifest.json` — Chrome MV3 version. Intentionally allowed to drift from the backend version: Chrome Web Store expects monotonic bumps, but not every backend release needs an extension rev. The release script still bumps both in lockstep; if you need to break that, edit `release.sh`.
   - `web/latest.json` — what the in-app updater polls. The script sets `published_at` to today and overwrites `notes` with your one-liner.
3. Runs `./scripts/build.sh` to produce the DMG and the extension zip.
4. Commits the bumps as `Release vX.Y.Z`, tags `vX.Y.Z`, pushes `main` + tag.
5. Runs `gh release create vX.Y.Z dist/CtxAnt.dmg dist/CtxAnt-extension-vX.Y.Z.zip`.

Vercel auto-redeploys the site on every push to `main`, so `web/latest.json` goes live at `https://ctxant.com/latest.json` within ~60s. Any running CtxAnt instance polls the feed and surfaces the update via its menu bar.

---

## How the auto-update pipeline works

```
backend/__version__.py         ← canonical version, stamped into CFBundleVersion
        │
        ▼
scripts/release.sh             ← bumps it, builds, tags, pushes
        │
        ├──► git push main ──► Vercel auto-deploy ──► ctxant.com/latest.json
        └──► gh release create ──► GitHub Releases hosts CtxAnt.dmg
                                         ▲
                                         │
backend/updater.py  ◄─── polls latest.json every 6h (throttled via kv table)
        │
        ▼
menu-bar "⬆ Update to vX.Y.Z" ──► rumps.alert ──► osascript opens Terminal
                                                   running curl | sh
                                                         │
                                                         ▼
                                                 install.sh pulls latest DMG
                                                 from GitHub Releases, replaces
                                                 /Applications/CtxAnt.app, relaunches
```

Key invariants:
- `backend/__version__.py` is the single source of truth. The PyInstaller spec reads it via regex (no import), the updater imports `__version__`, and `release.sh` rewrites the `"x.y.z"` literal in place.
- The update URL the app hits is overridable via the `CTXANT_UPDATE_FEED` env var — handy for pointing a dev build at a staging Vercel preview.
- The install URL the app opens is overridable via the `install_script_url` field in `latest.json`, so a bad `install.sh` can be hot-patched without shipping a new DMG.

---

## Updating the extension

The extension ships inside the DMG under `Contents/Resources/extension/`. When a user updates via `install.sh`, they get a fresh extension tree on disk — but **Chrome doesn't reload it automatically**. The in-app update dialog now tells them to click Reload at `chrome://extensions` after install.

For devs on load-unpacked: reload via `chrome://extensions` → ⟳ on CtxAnt after any pull/edit.

For non-devs post-launch-week: once the Chrome Web Store listing is approved, regular users get updates through CWS and never need to touch `chrome://extensions`. Until then, the extension zip from each GitHub Release (`CtxAnt-extension-vX.Y.Z.zip`) is the fallback.

---

## Where Vercel deploys from

- **Project:** `ctxant` (`prj_ceRZNlZiLLAa6cytFs32RUi9qQYx`), linked via GitHub App to `ChamsBouzaiene/CtxAnt`.
- **Branch:** `main`.
- **Output directory:** `web/` (configured in `vercel.json`).
- **Headers:** `/install.sh` is served as `text/x-sh`, `/latest.json` has `Cache-Control: max-age=60`, assets are immutable for a year — all via `vercel.json`.
- **Env vars:** none. The site is fully static.
- **Manual deploy (only needed first time to attach domain):** `vercel --prod` from repo root, then `vercel alias set <prod-url> ctxant.com`.

Every push to `main` triggers a production rebuild automatically. No GitHub Action required.

---

## Running from source

```bash
# 1. install deps
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. create a .env (see .env.example for the full list)
cp ../.env.example ../.env
# edit .env — set TELEGRAM_BOT_TOKEN, your AI key, and TELEGRAM_ALLOWED_USERS

# 3. run
python main.py
```

On first run you'll see:

```
AI provider: GROK
WS_SECRET ready (auto-paired by extension) — xQ9k4s…
Multi-bot runtime: 1 bots online (hub=ok, agents=[])
CtxAnt multi-bot runtime is running. Press Ctrl+C to stop.
```

That means: SQLite initialized, pairing endpoint is up on `http://127.0.0.1:8766/pair`, the WebSocket server is up on `ws://localhost:8765`, the hub bot is polling Telegram, and there are no agent bots yet (you'll deploy those from the hub's `/start`).

### Load the Chrome extension

1. Open `chrome://extensions`.
2. Toggle **Developer mode** on.
3. Click **Load unpacked** and pick the `extension/` folder.
4. The extension auto-fetches the WS secret from `http://127.0.0.1:8766/pair`. You don't need to paste anything.

### Legacy single-bot mode

The multi-bot runtime is the default. To fall back to the old single-bot path (useful while iterating on a specific handler without booting multiple pollers):

```bash
CTXANT_MULTI_BOT=0 python main.py
```

---

## Architecture at a glance

**One Python process, N Telegram bots.** Each bot is its own `telegram.ext.Application` polling Telegram concurrently. They all share:

- **One event loop** (everything is async).
- **One Chrome**, serialized via an `asyncio.Lock` in `claude_agent.py`. If agent B tries to run while agent A holds the lock, B's user immediately sees "⏳ queued behind …".
- **One SQLite DB** at `~/Library/Application Support/ctxant/ctxant.db`.
- **One AI client** (Grok via OpenAI-compatible base URL, or Anthropic).

```
┌─── CtxAnt process ────────────────────────────────────────┐
│                                                          │
│   Hub bot Application ──┐                                │
│                          ├─► shared handler stack        │
│   Job Hunter bot App  ──┤   (but the hub has hub_handlers│
│   Deal Finder bot App ──┤    and agents have             │
│   Researcher bot App  ──┘    agent_handlers)             │
│                                                          │
│   claude_agent.process_message ← global browser Lock     │
│             │                                            │
│             ▼                                            │
│   browser_bridge WebSocket ─────► Chrome extension       │
│                                   (your real Chrome)     │
│                                                          │
│   scheduler (APScheduler) ───► fires per-agent cron      │
│                                callbacks push via the    │
│                                *owning* bot, not the hub │
└──────────────────────────────────────────────────────────┘
```

### Roles

- **Hub** (`role='hub'` in the `bots` table): the control bot. Handles `/deploy`, `/agents`, `/usage`, etc. The token comes from `TELEGRAM_BOT_TOKEN` in `.env` on first run, seeded into the `bots` table by `bots.ensure_hub_from_env()`.
- **Agent** (`role='agent'`): bound to one `agent_slug`. You create one by walking through the `/deploy` wizard in the hub — it prints BotFather instructions, waits for you to paste the new token back, and spins up that bot live.

Agent slug is pinned to each Application's `bot_data[SLUG_KEY]` at wire time, so every handler in that app knows which agent it is.

### Agents

An agent is a row in the `agents` table with:

- `prompt_template` — string with `{placeholders}` like `{role}`, `{cities}`.
- `setup_flow_json` — list of `{key, q, type, required, options}` dicts. The agent bot walks through these on `/start` via `_capture_setup_answer`.
- `agent_memory` — per-`(chat_id, agent_slug)` key-value store filled in by the setup flow.
- `render_prompt(chat_id, slug)` in `agents.py` fills the template from memory (missing keys render as `(not set)` via `_SafeDict`).

The starter pack (6 agents) is seeded by `agents.seed_starter_pack()` on every startup (idempotent).

### Universal behaviours (enforced in `claude_agent.process_message`)

- **Browser Lock** — every run awaits `_get_browser_lock()`. `browser_busy()` is a non-blocking probe used by `agent_handlers._run_agent` to post the queued message *before* awaiting.
- **Blocker guidance** — `BLOCKER_GUIDANCE` is appended to every agent's system prompt. When the AI hits an auth wall, CAPTCHA, or missing info, it must tell the user the exact URL to open, what to do there, and what command to reply with to resume — instead of silently giving up.
- **Universal error handler** — every `Application` has `_on_handler_error` (in `bots.py`) attached. If any handler raises, the user gets a DM'd snippet plus a `/reset` hint. Nothing goes silent.
- **Live typing indicator** — `agent_handlers._keep_typing` re-sends `ChatAction.TYPING` every 4s so Telegram's auto-expiring indicator stays visible for the full run.

---

## Test scenarios — what to try in Telegram

Manual smoke tests for the multi-bot runtime. Run `python main.py` (or launch `ctxant.app`), open your hub bot, and walk through:

### 1. Hub `/start` picker

- Send `/start` to the hub → you should get an intro message with a 2-column inline keyboard listing all 6 starter agents.
- Agents you've already deployed show a ✅; undeployed ones show their emoji.
- Tap an undeployed agent → hub asks you to do the BotFather ritual.

### 2. Deploy an agent

- Tap **🧑‍💼 Job Hunter** (or run `/deploy job_hunter`).
- Follow the BotFather steps.
- Paste the new bot's token as your next message in the hub chat.
- Hub replies: **🧑‍💼 Job Hunter is live as @xxx_bot. Open @xxx_bot and send /start.**
- Open the new bot. It should respond to `/start` with a setup flow.

### 3. Guided setup

- In the Job Hunter bot, send `/start` → it asks the first setup question.
- Answer each. Required fields enforce a value; optional fields accept `skip`.
- `choice` questions reject non-option answers; `multi_choice` accepts comma-separated picks; `boolean` accepts yes/no.
- After the last question, bot says **✅ Setup complete. Try /run now.**

### 4. Run

- `/run` in the agent bot.
- **Expected:** typing indicator stays pinned for the whole run (4s refresh). Screenshots arrive first, then a text reply.
- Try plain text too (no `/run`) — same result, the text is appended to the agent's prompt.

### 5. Blocker guidance

- Trigger a run on Morning Digest or Inbox Triage *before* signing into Gmail/Calendar in the Chrome CtxAnt is driving.
- **Expected:** the agent explicitly names the blocker (e.g. "Gmail wants me to sign in"), gives the URL to open, and tells you what to reply to resume. It does NOT just summarize "unable to retrieve" and stop.
- Reply with a follow-up ("I just signed in") → the agent should re-screenshot and retry, not repeat the failure summary.

### 6. Concurrency

- Trigger `/run` on agent A.
- Within 2s trigger `/run` on agent B.
- **Expected:** agent B's bot posts **⏳ Queued — the browser is busy with another agent** immediately, then runs when A finishes.

### 7. Schedule

- In an agent bot, `/schedule every day at 9am` (or `/schedule in 2 minutes` for a quick test).
- `/schedules` lists it.
- When the schedule fires, the DM should come from the **agent bot** (not the hub).
- `/cancel <id>` removes it.

Supported schedule specs (see `scheduler._parse_trigger`):
- `in N minutes` / `in N hours` (one-shot)
- `every N minutes` / `every N hours`
- `every hour`, `every minute`, `hourly`
- `every day at 9am`, `daily at 14:30`
- `every monday at 9am`
- raw cron `0 9 * * *`

### 8. Usage

- Run a few agents to burn some tokens.
- In the hub: `/usage`.
- **Expected:** a total (input/output tokens, $ estimate) and a per-agent breakdown.

### 9. Stop

- Trigger a long-running `/run`.
- In the hub: `/stop_all`. Or in an agent bot: `/stop`.
- **Expected:** the task cancels within the next tool iteration and the bot posts its current partial state.

### 10. Persistence

- Kill the backend (Ctrl+C or quit ctxant.app).
- Relaunch.
- **Expected:** all previously-deployed agent bots come back online (you should see them in the hub's `/agents` listing) and any schedules still fire. `bots.start_all()` re-polls each row of the `bots` table; `scheduler._restore_jobs()` re-registers cron triggers from the `schedules` table.

### 11. Memory

- `/settings` in an agent bot → re-walk the setup flow, change an answer.
- `/run` again → the new values take effect. `render_prompt` reads live from `agent_memory` each turn.
- `/status` shows the memory peek.

### 12. Error surfacing (regression check)

- Introduce a deliberate bug (e.g. raise at the top of `_run_agent`) and send a message to an agent bot.
- **Expected:** the user sees **⚠️ I hit an error handling that message: `<snippet>`** — not silence. The full traceback is in the log.

### 13. Vision

- Send a photo (with or without caption) to an agent bot.
- **Expected:** the AI receives the image (Grok vision or Claude vision depending on `AI_PROVIDER`) and can reason over it. Example: photo of a CV + Job Hunter → fills an Easy Apply form.

---

## Mac app: building and iterating

### Build

```bash
# from repo root
pip install -r backend/requirements.txt
./installer/build_mac.sh           # builds dist/ctxant.app
open dist/ctxant.app                # try it
```

For the DMG:

```bash
brew install create-dmg
./installer/build_mac.sh --dmg     # builds dist/ctxant.dmg
```

### What's in the .app

- `backend/*.py` frozen into one executable at `Contents/MacOS/ctxant`.
- The `extension/` folder, so first-run users can Load Unpacked it from the menu-bar action.
- `Info.plist` with `LSUIElement=True` (menu-bar only, no Dock icon).
- Bundle id: `com.ctxant.desktop`.

### When you change backend code

Rebuild — PyInstaller embeds the .pyc files into the app. Any edit to `backend/*.py` needs `./installer/build_mac.sh` to take effect in the .app.

**Shortcut for dev:** don't build the .app every time. Run `python backend/ctxant_app.py` directly — that exercises the menu bar + wizard + threaded backend with a live edit/restart loop.

### The rebuild-but-nothing-changed gotcha

macOS LaunchServices is **bundle-id-aware**. When you `open dist/ctxant.app` and a process for the same bundle id (`com.ctxant.desktop`) is already running, macOS does NOT launch the new binary — it just activates the existing process. So rebuilding the `.app` on disk has zero visible effect until you kill the running instance.

Symptom: you edit a handler, rebuild, `open dist/ctxant.app`, and your change doesn't appear. Endpoints that didn't exist in the old build 404, the menu bar shows the old title, etc.

Fix, always:

```bash
# 1. Kill any running instance (from this run OR a stale previous one)
pkill -f "dist/ctxant.app/Contents/MacOS/ctxant" ; sleep 1

# 2. Clean + rebuild (PyInstaller cache bites sometimes)
rm -rf build dist
./installer/build_mac.sh

# 3. Launch the fresh binary
open dist/ctxant.app

# 4. Verify the new code is actually running
ps -o lstart= -p $(pgrep -f "dist/ctxant.app/Contents/MacOS/ctxant")
# This should show a time from just now, not a time from earlier.
```

When debugging "why doesn't my change show up," check the process start time vs. the binary mtime first:

```bash
# Binary mtime:
stat -f "binary:  %Sm" dist/ctxant.app/Contents/MacOS/ctxant
# Process start time:
ps -o lstart= -p $(pgrep -f "dist/ctxant.app/Contents/MacOS/ctxant")
```

If the process started **before** the binary was built, you're looking at stale code.

### First-launch Gatekeeper

Unsigned ctxant.app will get blocked by Gatekeeper. Right-click → **Open** the first time to whitelist it. We'll add code signing + notarization once we're willing to pay Apple's $99/yr fee.

### Icon

Drop an `installer/icon.icns` and uncomment the `icon=` line in `ctxant.spec`. To make an `.icns` from a 1024×1024 PNG:

```bash
mkdir icon.iconset
sips -z 16 16   icon.png --out icon.iconset/icon_16x16.png
sips -z 32 32   icon.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32   icon.png --out icon.iconset/icon_32x32.png
sips -z 64 64   icon.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128 icon.png --out icon.iconset/icon_128x128.png
sips -z 256 256 icon.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256 icon.png --out icon.iconset/icon_256x256.png
sips -z 512 512 icon.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512 icon.png --out icon.iconset/icon_512x512.png
cp icon.png icon.iconset/icon_512x512@2x.png
iconutil -c icns icon.iconset
mv icon.icns installer/
```

---

## Testing the onboarding wizard without a full build

Building ctxant.app with PyInstaller takes 30–60 seconds. When you're iterating on the wizard's HTML or the menu-bar behaviour, skip the build:

```bash
pip install rumps pywebview pyinstaller
cd backend
python ctxant_app.py
```

This is the exact same entry point PyInstaller freezes — same flow, same code path. If `is_configured()` is False (no `.env`), the wizard opens. Otherwise the backend boots directly.

### Forcing the wizard to appear

The wizard only fires when `config.is_configured()` returns False. To test it against a pre-existing setup:

```bash
# temporarily move your .env aside
mv ~/Library/Application\ Support/ctxant/.env ~/Library/Application\ Support/ctxant/.env.bak

# run the app — wizard should open
python backend/ctxant_app.py

# restore when done
mv ~/Library/Application\ Support/ctxant/.env.bak ~/Library/Application\ Support/ctxant/.env
```

Or point the backend at a clean config dir:

```bash
CTXANT_CONFIG_DIR=/tmp/ctxant-test python backend/ctxant_app.py
```

### Tweaking the HTML

The wizard's HTML/JS lives inline in `_HTML` inside `backend/onboarding.py`. No build step — edit, save, relaunch. It supports light/dark via `prefers-color-scheme`, so test both.

### The wizard doesn't block the backend anymore

Before: pywebview's `webview.start()` blocks the main thread, and we only spawned the backend thread after the wizard closed. That meant the user saw "You're connected!" but the hub bot wasn't actually polling Telegram yet — the menu bar icon appeared only after they dismissed the window.

Now: `run_wizard_blocking(on_config_saved=…)` accepts a callback, and `_Api.save_config` fires it the moment the user clicks Finish on step 4. `ctxant_app.main` passes `_start_backend_thread_once`, which reloads the just-written `.env` and spawns the backend thread. By the time the user has read step 5 and clicks Close (or earlier, via the dashboard / "Open hub bot" shortcuts on step 5), the hub has already registered with Telegram.

Step 5's JS then polls `window.pywebview.api.hub_url()` every 1.5s; as soon as `bots._update_meta` fills in the hub's username in the DB, the wizard flips from "Starting CtxAnt…" to "✅ CtxAnt is online" and enables the "Open hub bot" button. No user action required.

Edge case: if the user kills the window *before* step 4 / save, `save_config` never fires so the callback never runs. The existing defensive `importlib.reload(config) + is_configured()` check in `main` handles this by showing the "Setup incomplete" alert.

### Running just the wizard (no backend)

```bash
python backend/onboarding.py
```

It'll show the window, write `.env` on Finish, and print `Saved.` or `Wizard closed without saving.`

---

## Iterating on the Chrome extension

Chrome doesn't hot-reload unpacked extensions for you — every change to `manifest.json`, icons, or the service worker requires a reload. Workflow:

```
# 1. Edit files under extension/
# 2. In Chrome:
#    - Open chrome://extensions
#    - Find "CtxAnt" → click the circular-arrow "Reload" icon
# 3. If you edited popup.html/js: close and reopen the popup
# 4. If you edited the service worker (background.js): click
#    "service worker" under the CtxAnt card to open DevTools and
#    check for errors
```

**When you need a full reinstall** (not just reload):

- You renamed the extension in the manifest (old listing lingers)
- You changed the `key` field, extension ID, or permissions
- Manifest JSON failed to parse (Chrome won't show a reload button)

To reinstall: `chrome://extensions` → Remove → Load unpacked → pick `extension/`.

**Regenerating icons.** Run `.venv/bin/python extension/icons/build_icons.py`. The script writes all sizes (16/32/48/128 for Chrome, 256/512 for the Web Store listing). If you re-brand, edit the colour constants and the wand geometry in that script — it's the source of truth, not the PNGs.

**Testing auto-pair with a fresh secret.** The extension caches the pairing secret in `chrome.storage.session`. To force re-pairing:

```bash
# kill the backend, clear the DB ws_secret, relaunch
sqlite3 ~/Library/Application\ Support/ctxant/ctxant.db "DELETE FROM kv WHERE key='ws_secret'"
```

Then reload the extension — it re-fetches from `http://127.0.0.1:8766/pair`.

---

## Releasing

The ritual for shipping a new version of either component. Both are unsigned today; signing notes are under each section.

### Releasing the Chrome extension

Two distribution channels: the **Chrome Web Store** (users click "Add to Chrome") and **direct Load-Unpacked** (what onboarding uses today, before the Web Store listing is live). The submission kit — copy-paste fields, permission justifications, asset sizes — lives at [`extension/store-assets/README.md`](./extension/store-assets/README.md). The steps below are the meta-flow; that file has the fill-in-the-blanks.

**First-time prep (do once):**

1. Pay the $5 Chrome developer registration fee at https://chrome.google.com/webstore/devconsole.
2. Host [`extension/privacy.html`](./extension/privacy.html) at a public URL (e.g. `https://ctxant.com/privacy`). GitHub Pages or Vercel both work. The URL goes into the dashboard's **Privacy policy** field.
3. Capture 1–5 screenshots at **1280×800** PNG and drop them into `extension/store-assets/` as `screenshot-1.png`, etc. Suggested shots are listed in that folder's README.
4. (Optional but boosts discovery) Produce `promo-tile-440x280.png` and save it next to the screenshots.

**Per-release steps:**

```bash
# 1. Bump version in manifest.json (Chrome REQUIRES a strictly-higher version
#    on every upload — even for rejected submissions).
#    E.g. "1.0.0" → "1.0.1"

# 2. Regenerate icons if the brand changed
.venv/bin/python extension/icons/build_icons.py

# 3. Smoke-test locally before uploading
#    - Reload the unpacked extension in Chrome
#    - Verify the popup shows "Connected to CtxAnt" with the green dot
#    - Run one /run from your hub to make sure the WebSocket still works

# 4. Zip the extension for upload (exclude dev files)
cd extension
VER=$(python3 -c "import json; print(json.load(open('manifest.json'))['version'])")
zip -r ../ctxant-extension-v$VER.zip . \
    -x '*.DS_Store' \
    -x 'store-assets/*' \
    -x 'icons/build_icons.py'
cd ..
echo "Upload: ctxant-extension-v$VER.zip"

# 5. Upload to the Developer Dashboard:
#    https://chrome.google.com/webstore/devconsole
#    - Click the listing → "Package" tab → "Upload new package"
#    - Copy-paste listing + justifications from extension/store-assets/README.md
#    - Submit
#    - Review typically 1–3 business days
```

**After approval:**

1. Swap onboarding's "Load unpacked" step for the Web Store URL. Find the strings in [`backend/onboarding.py`](./backend/onboarding.py) around the step-4 HTML (search for `chrome://extensions`) and replace them with a single "Install from Chrome Web Store" button pointing at the listing.
2. Update the README quick-start.
3. Announce (Twitter, Product Hunt listing if not done).

**If a release is rejected:**

- Read the rejection email carefully — it names the specific policy.
- The most common rejection for CtxAnt's shape is `<all_urls>` justification. The canned answer is already in `store-assets/README.md` — resubmit with the justification pasted into the "Single purpose" and "Host permissions" fields.
- Bump the version again (even a rejected upload consumes the version number).

### Releasing the Mac app

Two things you can distribute: the raw `ctxant.app` bundle (users drag it wherever) and a `ctxant.dmg` (the polished drag-to-Applications experience). Both come from the same PyInstaller spec.

**Per-release steps:**

```bash
# 1. Bump the version you advertise. Right now CtxAnt has no version
#    string in Info.plist — add one if/when you start versioning releases
#    publicly. (For early launches, "v1 date" is fine.)

# 2. Clean old build output (PyInstaller is cache-happy and will
#    sometimes miss changed files otherwise)
rm -rf build dist

# 3. Build
./installer/build_mac.sh          # produces dist/ctxant.app

# 4. Smoke-test the built app (NOT python backend/ctxant_app.py —
#    we're testing the frozen bundle)
open dist/ctxant.app
#    - Menu bar shows "🪄 CtxAnt"
#    - If you had no .env: wizard appears, walk through it end-to-end
#    - If you had a .env: backend boots, the hub bot responds in Telegram
#    - Check ~/Library/Logs/ctxant/ctxant.log for unexpected errors
#    - Quit from the menu bar

# 5. Produce the DMG for distribution
brew install create-dmg           # one-time
./installer/build_mac.sh --dmg    # produces dist/ctxant.dmg

# 6. (Until signed) verify Gatekeeper behaviour on a second Mac or a
#    fresh user: downloading the DMG off the internet makes macOS
#    attach the quarantine attribute. Users must right-click → Open
#    the first time. See the "First-launch Gatekeeper" note below.
```

**Where to host the DMG:**

- **GitHub Releases** is the cheapest path — `gh release create vX.Y.Z dist/ctxant.dmg --title "CtxAnt X.Y.Z" --notes "..."`. Free, versioned, users get a download URL you can drop into the landing page.
- **ctxant.com** (landing page): link the "Install for Mac" button to the GitHub Releases download of the latest DMG.

**Code signing + notarization (when we're ready to pay Apple):**

Today CtxAnt is unsigned. That means every user hits Gatekeeper's "can't be opened because Apple cannot check it for malicious software" dialog on first launch, and has to right-click → Open to whitelist it. That's a meaningful friction hit during a launch week.

Fixing it costs $99/year for an Apple Developer ID. Once enrolled:

```bash
# 1. Sign the .app (inside build_mac.sh or manually)
codesign --deep --force --options runtime --timestamp \
    --sign "Developer ID Application: Your Name (TEAMID)" \
    dist/ctxant.app

# 2. Notarize
ditto -c -k --keepParent dist/ctxant.app CtxAnt.zip
xcrun notarytool submit CtxAnt.zip \
    --apple-id you@example.com \
    --team-id TEAMID \
    --password "@keychain:AC_PASSWORD" \
    --wait

# 3. Staple so notarization works offline
xcrun stapler staple dist/ctxant.app

# 4. Rebuild the DMG from the signed/stapled .app
./installer/build_mac.sh --dmg
```

For signing to actually help, bundle the entitlements CtxAnt needs. The ones that matter:

- `com.apple.security.network.client` — for Telegram/AI API calls
- `com.apple.security.network.server` — for the local pairing HTTP + WebSocket
- `com.apple.security.automation.apple-events` — for `osascript` calls to open Chrome tabs

Add these to an `Entitlements.plist` and pass `--entitlements Entitlements.plist` to `codesign`. (Not needed until we actually sign.)

**Gatekeeper-bypass instructions for unsigned users** (include on the landing page next to the DMG download):

```
First-time users: macOS blocks unsigned apps by default.

1. Open dist/ctxant.app from Finder (not a double-click).
2. Right-click (or Ctrl-click) the app → Open.
3. Click "Open" in the Gatekeeper prompt.
4. macOS remembers this choice — future launches work normally.
```

**Auto-updates (not implemented yet).** The hand-rolled path is a check-for-update call at launch that compares a remote `version.json` to the bundled one. The polished path is [Sparkle](https://sparkle-project.org/) — which requires signing. Defer until v2.

---

## Environment & file locations

| What | Where |
|---|---|
| User config | `~/Library/Application Support/ctxant/.env` (0600 perms) |
| SQLite DB | `~/Library/Application Support/ctxant/ctxant.db` |
| Logs | `~/Library/Logs/ctxant/ctxant.log` (also stdout) |
| Dev override for config dir | `CTXANT_CONFIG_DIR=/path` |
| Dev override for DB path | `CTXANT_DB_PATH=/path/to/db` |
| Toggle legacy single-bot | `CTXANT_MULTI_BOT=0` |
| WebSocket bridge | `ws://localhost:8765` (shared secret in `WS_SECRET`) |
| Extension pairing endpoint | `http://127.0.0.1:8766/pair` |

### The `.env` schema (v1)

```bash
# AI provider
AI_PROVIDER=grok                    # or "claude"
XAI_API_KEY=xai-...                 # if grok
XAI_MODEL=grok-4-1-fast-reasoning
ANTHROPIC_API_KEY=sk-ant-...        # if claude

# Telegram hub bot (agent bots are stored in the `bots` table, not .env)
TELEGRAM_BOT_TOKEN=123:AA...
TELEGRAM_ALLOWED_USERS=123456789    # comma-separated

# WebSocket bridge (auto-paired with the extension on first run)
WS_SECRET=xxxx
WS_PORT=8765
```

### The DB at a glance

Tables relevant to day-to-day dev:

- `bots` — one row per Telegram Application (hub + agents). Unique `(role, agent_slug, owner_chat_id)`.
- `agents` — the registry. Seeded by `agents.seed_starter_pack()`.
- `agent_memory` — `(chat_id, agent_slug, key) → value`.
- `schedules` — cron rows, one per scheduled run. `agent_slug` column is new.
- `usage` — per-call token + $ records with `agent_slug`.
- `conversations` — per-agent chat history (keyed by `(chat_id, agent_slug)` in-memory; DB is additive).
- `kv` — misc, currently holds `ws_secret`.

Quick peek:

```bash
sqlite3 ~/Library/Application\ Support/ctxant/ctxant.db \
    "SELECT role, agent_slug, username FROM bots"
```

---

## Debugging tips

**"Bot doesn't respond in Telegram."**
Check `~/Library/Logs/ctxant/ctxant.log`. With the new error handler, any raised exception in a handler produces both a log entry and a DM to the user — if you see neither, the message never reached python-telegram-bot (likely a polling / network issue).

**"Extension shows 'disconnected'."**
- Is the backend running? `lsof -iTCP:8765 -sTCP:LISTEN` should show Python.
- Is the pairing endpoint reachable? `curl http://127.0.0.1:8766/pair`.
- Did `WS_SECRET` change without the extension re-pairing? Click the extension's icon → "Re-pair" (or just reload the extension).

**"Agent bot never picked up after `/deploy`."**
The hub captured the wrong message as the token. Look for `spawn_agent_bot` in the logs — if it says "Token rejected by Telegram", the pasted string wasn't a live token. Paste the raw BotFather line, not a quoted version.

**"Two agent bots replying to the same command."**
You accidentally deployed the same agent twice under different tokens. Check `SELECT * FROM bots WHERE agent_slug=?;` and `/undeploy <slug>` the stale one.

**Making the scheduler fire sooner for testing.**
`/schedule in 1 minute` is the fastest path. For sub-minute tests, edit the row in `schedules` directly and restart (APScheduler restores jobs from that table on boot).

**Resetting everything** (wipe `.env`, the DB, logs — next launch starts from the wizard as if you just installed):

```bash
# 1. Kill anything running first — both a source launcher and the .app
pkill -f "dist/ctxant.app/Contents/MacOS/ctxant" 2>/dev/null
pkill -f "ctxant_app.py"                        2>/dev/null
pkill -f "backend/main.py"                     2>/dev/null

# 2. Delete user config + local DB + cached pairing secret
rm -rf ~/Library/Application\ Support/ctxant

# 3. Delete logs (optional — makes it easier to see a clean log for
#    the new session)
rm -rf ~/Library/Logs/ctxant

# 4. If you've also been developing from source with a repo-local .env,
#    move it aside so the wizard doesn't skip (config.py looks here too)
mv .env .env.bak 2>/dev/null

# 5. Relaunch — the onboarding wizard should appear
open dist/ctxant.app            # built bundle
# or:
.venv/bin/python backend/ctxant_app.py   # from source
```

**Partial resets** for when you want to keep some state:

```bash
# Only force the onboarding wizard to reappear (keep the DB, agents, schedules):
mv ~/Library/Application\ Support/ctxant/.env \
   ~/Library/Application\ Support/ctxant/.env.bak

# Only reset agent conversation history + usage (keep memory + bots + schedules):
sqlite3 ~/Library/Application\ Support/ctxant/ctxant.db \
    "DELETE FROM conversations; DELETE FROM usage;"

# Only undeploy a specific agent bot (keep everything else):
sqlite3 ~/Library/Application\ Support/ctxant/ctxant.db \
    "DELETE FROM bots WHERE agent_slug='job_hunter';"

# Force the Chrome extension to re-pair (generates a fresh WS_SECRET):
sqlite3 ~/Library/Application\ Support/ctxant/ctxant.db \
    "DELETE FROM kv WHERE key='ws_secret';"
```

**Undo a full reset** (if you did the nuclear wipe but want to go back):

```bash
mv .env.bak .env                                          # repo-local .env
# The ~/Library/Application Support/ctxant folder is gone forever after rm —
# no undo. That's why, for dogfood testing, it's worth tar'ing it up first:
#
#   tar -czf ~/ctxant-backup-$(date +%Y%m%d).tgz \
#       ~/Library/Application\ Support/ctxant
```

---

## What's shipped so far (commit log)

- `a3b07a5` — Initial MVP: Telegram bot drives real Chrome via extension.
- `85d0fff` — Monday: per-agent DB schema + agents registry + per-agent history/usage.
- `a356c72` — Tuesday: multi-bot runtime + hub/agent handler split + deploy wizard.
- `ed3e5d6` — Blocker guidance in system prompt + universal error handler.
- `6477bcb` — Keep typing indicator alive for full run duration.
- `cabe9e3` — Wednesday: Mac menu-bar app + onboarding wizard + PyInstaller bundle.
- `df1449d` — Docs: rewrite README for CtxAnt v1 + add DEVELOPMENT.md.
- `261a42e` — Fix: default to grok-4-1-fast-reasoning (grok-2-1212 was retired).
- `e82036f` — Dashboard at `/dashboard`, "Connected" wizard step, visible menu bar title, `/start deploy_<slug>` deep-link handler.
- `9ca96cc` — Thursday: Chrome Web Store polish — rebrand extension as CtxAnt, icons (16→512), privacy policy, submission kit in `extension/store-assets/`.

Next on the sprint: Friday (landing page + demo GIFs), Saturday (dogfood + fresh-Mac install test), Sun/Mon (launch).
