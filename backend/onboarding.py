"""First-run onboarding wizard.

Shows a native window (pywebview) with a 4-step flow:
    1. Paste the hub bot's Telegram token.
    2. Pick AI provider + paste its API key.
    3. Paste your Telegram user id (for the allowlist).
    4. Install the Chrome extension.

On "Finish" we write ~/Library/Application Support/ctxant/.env so the
next backend boot sees a fully configured environment.

This module is imported only on demand (when config is missing), so
pywebview staying a Mac-only install is fine — `python main.py` never
touches this file.

Usage:
    python -m onboarding
    # or from ctxant_app.py:
    import onboarding; onboarding.run_wizard_blocking()
"""

from __future__ import annotations

import json
import logging
import secrets
from pathlib import Path
from typing import Callable, Optional

import config

logger = logging.getLogger(__name__)


# ── HTML/JS for the wizard ────────────────────────────────────────────────────

_HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>Welcome to CtxAnt</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #ffffff;
    --fg: #111;
    --muted: #666;
    --accent: #4f46e5;
    --accent-hover: #4338ca;
    --card: #f7f7f9;
    --border: #e4e4e7;
    --danger: #dc2626;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #111;
      --fg: #f5f5f5;
      --muted: #a1a1aa;
      --card: #1f1f23;
      --border: #2e2e33;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro", "Helvetica Neue", sans-serif;
    background: var(--bg);
    color: var(--fg);
    margin: 0;
    padding: 32px 40px;
    -webkit-font-smoothing: antialiased;
  }
  h1 { font-size: 28px; margin: 0 0 4px; }
  h2 { font-size: 18px; margin: 24px 0 8px; }
  .muted { color: var(--muted); font-size: 13px; }
  .step { display: none; }
  .step.active { display: block; }
  .progress {
    display: flex; gap: 4px; margin-bottom: 24px;
  }
  .progress .dot {
    flex: 1; height: 4px; background: var(--border); border-radius: 2px;
    transition: background .2s;
  }
  .progress .dot.done { background: var(--accent); }
  label { display: block; margin: 12px 0 6px; font-size: 13px; font-weight: 600; }
  input[type=text], input[type=password], textarea, select {
    width: 100%; padding: 10px 12px; font-size: 14px; border: 1px solid var(--border);
    border-radius: 6px; background: var(--card); color: var(--fg);
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  input:focus, select:focus, textarea:focus { outline: 2px solid var(--accent); border-color: transparent; }
  .hint { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .nav { display: flex; justify-content: space-between; margin-top: 32px; gap: 8px; }
  button {
    padding: 10px 20px; font-size: 14px; border: 0; border-radius: 6px;
    background: var(--accent); color: white; cursor: pointer; font-weight: 600;
  }
  button:hover { background: var(--accent-hover); }
  button.secondary { background: transparent; color: var(--fg); border: 1px solid var(--border); }
  button[disabled] { opacity: .4; cursor: not-allowed; }
  .error { color: var(--danger); font-size: 13px; margin-top: 8px; }
  .success { color: #16a34a; font-size: 14px; }
  pre.code {
    background: var(--card); padding: 10px 12px; border-radius: 6px; border: 1px solid var(--border);
    font-size: 12px; white-space: pre-wrap; margin: 8px 0;
  }
  ol { padding-left: 18px; }
  ol li { margin: 6px 0; }
  a { color: var(--accent); }
</style>
</head>
<body>

<div class="progress">
  <div class="dot" id="d1"></div>
  <div class="dot" id="d2"></div>
  <div class="dot" id="d3"></div>
  <div class="dot" id="d4"></div>
  <div class="dot" id="d5"></div>
</div>

<!-- Step 1: Hub bot token ------------------------------------------------- -->
<div class="step active" id="step1">
  <h1>Welcome to CtxAnt 👋</h1>
  <p class="muted">Your Chrome's AI sidekick — text it from Telegram. Let's get you set up in under 2 minutes.</p>

  <h2>1. Create your hub bot</h2>
  <ol>
    <li>Open <b>@BotFather</b> in Telegram.</li>
    <li>Send <b>/newbot</b>. Name it something like <code>My CtxAnt</code>.</li>
    <li>Pick a username ending in <code>bot</code>, e.g. <code>myctxant_hub_bot</code>.</li>
    <li>BotFather replies with a token — paste it below.</li>
  </ol>

  <label for="token">Hub bot token</label>
  <input type="text" id="token" placeholder="123456789:AA..." autocomplete="off" />
  <div class="hint">We store it locally in <code>~/Library/Application Support/ctxant/.env</code>. It never leaves your Mac.</div>

  <div class="nav">
    <span></span>
    <button onclick="nextStep(1)">Next →</button>
  </div>
</div>

<!-- Step 2: AI provider ---------------------------------------------------- -->
<div class="step" id="step2">
  <h1>Pick your AI</h1>
  <p class="muted">CtxAnt uses <i>your</i> API key, so you pay the AI provider directly. Typical cost: &lt;$2/month.</p>

  <label for="provider">Provider</label>
  <select id="provider" onchange="onProviderChange()">
    <option value="grok">xAI Grok (cheaper, recommended)</option>
    <option value="claude">Anthropic Claude (stronger reasoning)</option>
  </select>
  <div class="hint" id="providerHint">Get a key at <a href="https://console.x.ai" target="_blank">console.x.ai</a>.</div>

  <label for="apiKey">API key</label>
  <input type="password" id="apiKey" placeholder="xai-... or sk-ant-..." autocomplete="off" />

  <div class="nav">
    <button class="secondary" onclick="prevStep(2)">← Back</button>
    <button onclick="nextStep(2)">Next →</button>
  </div>
</div>

<!-- Step 3: Telegram user id ---------------------------------------------- -->
<div class="step" id="step3">
  <h1>Lock it down</h1>
  <p class="muted">Only your Telegram account will be able to talk to your bot. No one else can run commands on your browser.</p>

  <h2>Find your Telegram user id</h2>
  <ol>
    <li>Open <b>@userinfobot</b> in Telegram and send it <code>/start</code>.</li>
    <li>It replies with a numeric id — paste it below.</li>
  </ol>

  <label for="userId">Your Telegram user id</label>
  <input type="text" id="userId" placeholder="123456789" autocomplete="off" />
  <div class="hint">You can add more ids later by editing the .env file.</div>

  <div class="nav">
    <button class="secondary" onclick="prevStep(3)">← Back</button>
    <button onclick="nextStep(3)">Next →</button>
  </div>
</div>

<!-- Step 4: Install extension --------------------------------------------- -->
<div class="step" id="step4">
  <h1>Almost done 🎉</h1>
  <p class="muted">Last step: install the Chrome extension so your bot can drive your browser.</p>

  __EXTENSION_INSTALL_BLOCK__

  <p class="muted">Once the extension is loaded, open your hub bot in Telegram and send <code>/start</code>. It'll walk you through deploying your first agent.</p>

  <div class="nav">
    <button class="secondary" onclick="prevStep(4)">← Back</button>
    <button id="finishBtn" onclick="finish()">Finish &amp; start CtxAnt</button>
  </div>
  <div id="finishMsg"></div>
</div>

<!-- Step 5: Connected! ---------------------------------------------------- -->
<div class="step" id="step5">
  <h1 style="font-size: 36px;">🎉 You're set up!</h1>
  <p class="muted" style="font-size: 15px;">CtxAnt is booting in the background — you don't need to wait here, you can close this window whenever.</p>

  <div style="background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin: 20px 0;">
    <h2 style="margin-top: 0;">
      <span id="hubStatusIcon">⏳</span>
      <span id="hubStatusText">Starting CtxAnt…</span>
    </h2>
    <p class="muted" id="hubStatusDetail">Registering your bot with Telegram (this usually takes 2–5 seconds).</p>
  </div>

  <div style="background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin: 20px 0;">
    <h2 style="margin-top: 0;">📬 Open your hub bot</h2>
    <p class="muted">Send it <code>/start</code> in Telegram and it'll walk you through deploying your first agent.</p>
    <p><button id="openHubBtn" onclick="openHub()" disabled>Open hub bot in Telegram →</button></p>

    <h2>📊 Or open the dashboard</h2>
    <p class="muted">See your deployed agents and routines in a local web page.</p>
    <p><button class="secondary" onclick="openDashboard()">Open dashboard</button></p>
  </div>

  <div class="nav">
    <span></span>
    <button onclick="window.pywebview.api.close()">Close</button>
  </div>
</div>

<script>
  let step = 1;
  const totalSteps = 5;

  function show(n) {
    for (let i = 1; i <= totalSteps; i++) {
      document.getElementById('step' + i).classList.toggle('active', i === n);
      document.getElementById('d' + i).classList.toggle('done', i <= n);
    }
    step = n;
  }

  function nextStep(from) {
    if (from === 1) {
      const t = document.getElementById('token').value.trim();
      if (!t.includes(':') || t.length < 35) {
        alert('That doesn\'t look like a bot token. Paste the whole thing from BotFather.');
        return;
      }
    }
    if (from === 2) {
      const k = document.getElementById('apiKey').value.trim();
      if (k.length < 10) {
        alert('Please paste your API key.');
        return;
      }
    }
    if (from === 3) {
      const u = document.getElementById('userId').value.trim();
      if (!/^\d+$/.test(u)) {
        alert('User id should be all digits (e.g. 123456789).');
        return;
      }
    }
    show(from + 1);
  }

  function prevStep(from) { show(from - 1); }

  function onProviderChange() {
    const p = document.getElementById('provider').value;
    const hint = document.getElementById('providerHint');
    if (p === 'grok') {
      hint.innerHTML = 'Get a key at <a href="https://console.x.ai" target="_blank">console.x.ai</a>.';
      document.getElementById('apiKey').placeholder = 'xai-...';
    } else {
      hint.innerHTML = 'Get a key at <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a>.';
      document.getElementById('apiKey').placeholder = 'sk-ant-...';
    }
  }

  async function finish() {
    const btn = document.getElementById('finishBtn');
    const msg = document.getElementById('finishMsg');
    btn.disabled = true;
    msg.innerHTML = '';

    const payload = {
      token: document.getElementById('token').value.trim(),
      provider: document.getElementById('provider').value,
      api_key: document.getElementById('apiKey').value.trim(),
      user_id: document.getElementById('userId').value.trim(),
    };

    try {
      const result = await window.pywebview.api.save_config(payload);
      if (result && result.ok) {
        // Jump to the success screen right away. The Python side has
        // already kicked off the backend thread inside save_config, so
        // by the time we land on step 5 the hub bot is already
        // registering with Telegram. pollHubStatus() below watches for
        // completion and lights up the "Open hub bot" button.
        show(5);
        pollHubStatus();
      } else {
        msg.innerHTML = '<p class="error">' + (result && result.error || 'Something went wrong.') + '</p>';
        btn.disabled = false;
      }
    } catch (e) {
      msg.innerHTML = '<p class="error">' + e + '</p>';
      btn.disabled = false;
    }
  }

  let _hubUrl = "";

  // Poll the Python side for the hub bot's live t.me URL. It becomes
  // non-empty once bots.py's first get_me() succeeds (usually within
  // 2–5s of the backend starting). On success we flip step 5 from
  // "Starting…" to "Online" and enable the button.
  async function pollHubStatus() {
    const icon = document.getElementById('hubStatusIcon');
    const textEl = document.getElementById('hubStatusText');
    const detail = document.getElementById('hubStatusDetail');
    const btn = document.getElementById('openHubBtn');

    const deadline = Date.now() + 60_000;  // give up after a minute, user can still click

    while (Date.now() < deadline) {
      try {
        const url = await window.pywebview.api.hub_url();
        if (url) {
          _hubUrl = url;
          icon.textContent = '✅';
          textEl.textContent = 'CtxAnt is online';
          detail.innerHTML = 'Hub bot is live at <code>' + url.replace('https://t.me/', '@') + '</code>.';
          btn.disabled = false;
          return;
        }
      } catch (e) { /* swallow; try again */ }
      await new Promise(r => setTimeout(r, 1500));
    }

    // Timed out — leave the button clickable anyway; the user can retry.
    icon.textContent = '⚠️';
    textEl.textContent = 'Taking longer than expected';
    detail.textContent = "CtxAnt is still booting — if this stays stuck, check the logs from the menu bar.";
    btn.disabled = false;
  }

  async function openHub() {
    try {
      // Prefer the cached URL from the poll; fall back to a fresh lookup
      // for the "disabled-button-got-clicked-anyway" edge cases.
      const url = _hubUrl || await window.pywebview.api.hub_url();
      if (url) {
        window.pywebview.api.open_external(url);
      } else {
        alert("The hub bot hasn't finished checking in with Telegram yet. Give it a few more seconds.");
      }
    } catch (e) { alert(e); }
  }

  function openDashboard() {
    window.pywebview.api.open_external("http://127.0.0.1:8766/dashboard");
  }
</script>

</body>
</html>
"""


def _extension_install_block() -> str:
    if config.CHROME_WEB_STORE_URL:
        return f"""
  <h2>Install from the Chrome Web Store</h2>
  <ol>
    <li>Open the Chrome Web Store listing.</li>
    <li>Click <b>Add to Chrome</b>.</li>
    <li>Keep Chrome open while the extension pairs with the local backend on <code>127.0.0.1</code>.</li>
  </ol>
  <p><a href="{config.CHROME_WEB_STORE_URL}" target="_blank" rel="noreferrer">Open the Chrome Web Store listing →</a></p>
  <p class="hint">Developer fallback: if you're testing before the listing is live, you can still load the bundled <code>extension/</code> folder unpacked from <code>chrome://extensions</code>.</p>
"""
    return """
  <h2>Install the extension</h2>
  <ol>
    <li>Open <b>chrome://extensions</b> in Chrome.</li>
    <li>Toggle <b>Developer mode</b> (top right) ON.</li>
    <li>Click <b>Load unpacked</b>.</li>
    <li>Select the <code>extension/</code> folder from the CtxAnt install.</li>
    <li>The extension will auto-pair with the backend on localhost — no config needed.</li>
  </ol>
  <p class="hint">This unpacked path is the pre-approval and developer fallback. Once the Chrome Web Store listing is live, production installs should use that instead.</p>
"""


_HTML = _HTML_TEMPLATE.replace("__EXTENSION_INSTALL_BLOCK__", _extension_install_block())


# ── Python-side API exposed to the JS ─────────────────────────────────────────

class _Api:
    """Methods callable from JS via window.pywebview.api.<name>(...)."""

    def __init__(self, on_saved: Optional[Callable[[], None]] = None) -> None:
        self._window = None  # set by run_wizard_blocking before show()
        self._saved = False
        self._on_saved = on_saved

    def save_config(self, payload: dict) -> dict:
        try:
            token = (payload.get("token") or "").strip()
            provider = (payload.get("provider") or "grok").strip().lower()
            api_key = (payload.get("api_key") or "").strip()
            user_id = (payload.get("user_id") or "").strip()

            if ":" not in token or len(token) < 35:
                return {"ok": False, "error": "Invalid bot token format."}
            if provider not in ("grok", "claude"):
                return {"ok": False, "error": "Unknown provider."}
            if len(api_key) < 10:
                return {"ok": False, "error": "API key is empty."}
            if not user_id.isdigit():
                return {"ok": False, "error": "User id must be numeric."}

            _write_env(token=token, provider=provider, api_key=api_key, user_id=user_id)
            self._saved = True

            # Kick off whatever caller wanted us to run the moment .env is
            # written — typically this is ctxant_app spawning the backend
            # thread. By the time the user clicks "Close" on step 5, the
            # hub has already been polling Telegram for several seconds
            # and appears online in their chat list.
            if self._on_saved is not None:
                try:
                    self._on_saved()
                except Exception:
                    # Never let a broken callback fail the save — the .env
                    # is safely written either way, and the user can
                    # always close the wizard and relaunch manually.
                    logger.exception("on_saved callback raised")

            return {"ok": True}
        except Exception as e:
            logger.exception("Failed to save onboarding config")
            return {"ok": False, "error": str(e)}

    def close(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                logger.exception("Failed to close onboarding window")

    def hub_url(self) -> str:
        """Return the t.me link for the hub bot, or '' if we don't know it yet.

        The hub's username is filled into the bots table by
        bots._update_meta after the Application's first get_me() succeeds.
        On the very first launch the backend hasn't booted yet (we're still
        in the wizard) — in that case return an empty string and the JS
        will nudge the user to try again in a few seconds.
        """
        try:
            # Import lazily so the wizard still loads on a fresh install
            # where these modules might not yet have imported cleanly.
            import db
            row = db.query_one("SELECT username FROM bots WHERE role='hub'")
            if row and row["username"]:
                return f"https://t.me/{row['username']}"
        except Exception:
            logger.exception("Failed to look up hub bot username")
        return ""

    def open_external(self, url: str) -> None:
        """Open a URL in the user's default browser from the JS side."""
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception:
            logger.exception(f"Failed to open external url: {url}")


def _write_env(*, token: str, provider: str, api_key: str, user_id: str) -> None:
    """Write a fresh .env to config.env_path(). Idempotent per-run."""
    path = config.env_path()

    ws_secret = secrets.token_urlsafe(32)
    if provider == "claude":
        ai_lines = [
            "AI_PROVIDER=claude",
            f"ANTHROPIC_API_KEY={api_key}",
            "# XAI_API_KEY= (unused — provider is claude)",
        ]
    else:
        ai_lines = [
            "AI_PROVIDER=grok",
            f"XAI_API_KEY={api_key}",
            # grok-4-1-fast-reasoning: fast + cheap + tool-use capable, and
            # the model we're standardising on for CtxAnt agents.
            "XAI_MODEL=grok-4-1-fast-reasoning",
            "# ANTHROPIC_API_KEY= (unused — provider is grok)",
        ]

    lines = [
        "# Generated by the CtxAnt onboarding wizard. Edit by hand if you need to.",
        "",
        "# ── AI provider ─────────────────────────────────────────────────────",
        *ai_lines,
        "",
        "# ── Telegram hub bot ───────────────────────────────────────────────",
        f"TELEGRAM_BOT_TOKEN={token}",
        f"TELEGRAM_ALLOWED_USERS={user_id}",
        "",
        "# ── WebSocket bridge (auto-paired with the Chrome extension) ───────",
        f"WS_SECRET={ws_secret}",
        "WS_PORT=8765",
        f"CHROME_EXTENSION_ID={config.CHROME_EXTENSION_ID}",
        f"CHROME_EXTENSION_DEV_IDS={','.join(config.CHROME_EXTENSION_DEV_IDS)}",
        (
            f"CHROME_EXTENSION_ALLOW_ANY_DEV_ORIGIN="
            f"{'1' if (config.CHROME_EXTENSION_ALLOW_ANY_DEV_ORIGIN or (not config.CHROME_EXTENSION_ID and not config.CHROME_EXTENSION_DEV_IDS and not config.CHROME_WEB_STORE_URL)) else '0'}"
        ),
        f"CHROME_WEB_STORE_URL={config.CHROME_WEB_STORE_URL}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    # Restrict to owner — the file contains live credentials.
    try:
        path.chmod(0o600)
    except Exception:
        pass
    logger.info(f"Wrote onboarding config to {path}")


# ── Public entry ──────────────────────────────────────────────────────────────

def run_wizard_blocking(on_config_saved: Optional[Callable[[], None]] = None) -> bool:
    """Show the wizard and block until the user closes it.

    Returns True if the user completed it (.env was written), False otherwise.
    pywebview must be installed — we import lazily so the rest of the backend
    doesn't take a hard dependency on the Mac-only GUI stack.

    ``on_config_saved`` is invoked synchronously inside ``_Api.save_config``
    the moment the user clicks "Finish" on step 4 — *not* when the window
    closes. That lets ``ctxant_app`` spawn the backend thread while the user
    is still reading step 5, so Telegram polling has ~5–10 seconds of head
    start and the "Open hub bot" button can light up on its own.
    """
    try:
        import webview  # type: ignore
    except ImportError:
        logger.error(
            "pywebview isn't installed. Install it with `pip install pywebview` "
            "or run `python main.py` after editing .env by hand."
        )
        return False

    api = _Api(on_saved=on_config_saved)
    window = webview.create_window(
        title="Welcome to CtxAnt",
        html=_HTML,
        js_api=api,
        width=640,
        height=720,
        resizable=False,
        on_top=False,
    )
    api._window = window
    webview.start()  # blocks until window is closed
    return api._saved


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ok = run_wizard_blocking()
    print("Saved." if ok else "Wizard closed without saving.")
