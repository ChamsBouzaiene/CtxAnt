"""Local HTTP server (aiohttp on 127.0.0.1:8766).

Serves:

  GET /pair                — Chrome extension fetches WS_SECRET here on first
                             run. Localhost-only; CORS-gated to
                             chrome-extension:// origins.
  GET /health              — trivial "is the backend up" probe.
  GET /dashboard           — HTML dashboard: deployed agents + routines +
                             sidebar of deployable agents. Served to the
                             user's default browser when they click
                             'Open Dashboard' in the menu bar.
  GET /api/state           — JSON blob backing the dashboard (polled every 5s).
  GET /assets/appicon.png  — the brand mark, used by the dashboard page.
                             Localhost-only like the rest.
"""

import logging
import secrets
import sys
from pathlib import Path

from aiohttp import web

import db

logger = logging.getLogger(__name__)


def _bundled_asset(name: str) -> Path | None:
    """Locate a file from backend/assets/ in both dev and PyInstaller builds.

    Mirrors the resolution in ctxant_app._asset_path — kept local so pairing.py
    stays importable from ``python backend/main.py`` without pulling in the
    menu-bar module.
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        candidates += [base / "assets" / name, base / "backend" / "assets" / name]
    candidates.append(Path(__file__).parent / "assets" / name)
    for p in candidates:
        if p.exists():
            return p
    return None


def get_or_create_secret() -> str:
    existing = db.kv_get("ws_secret")
    if existing:
        return existing
    s = secrets.token_urlsafe(24)
    db.kv_set("ws_secret", s)
    return s


async def _pair(request: web.Request) -> web.Response:
    origin = request.headers.get("Origin", "")
    peer = request.transport.get_extra_info("peername") if request.transport else None
    peer_ip = peer[0] if peer else "?"
    logger.info(f"/pair hit from {peer_ip} origin={origin!r}")

    # Only localhost peers are allowed at all. Origin is logged for observability
    # but not enforced — the WS_SECRET itself is the real security, and bundling
    # a strict origin check here was blocking legitimate extension requests.
    if peer_ip not in ("127.0.0.1", "::1"):
        return web.Response(status=403, text="localhost only")

    secret = get_or_create_secret()
    return web.json_response(
        {"secret": secret},
        headers={
            "Access-Control-Allow-Origin": origin or "*",
            "Access-Control-Allow-Methods": "GET",
        },
    )


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


# ── Dashboard ────────────────────────────────────────────────────────────────

def _localhost_only(request: web.Request) -> bool:
    peer = request.transport.get_extra_info("peername") if request.transport else None
    ip = peer[0] if peer else ""
    return ip in ("127.0.0.1", "::1")


async def _api_state(request: web.Request) -> web.Response:
    """JSON blob the dashboard polls. Shape:

    {
      "hub":       {"username": "my_ctxant_bot"} | null,
      "deployed":  [{slug, display_name, emoji, username, schedules:[...]}, ...],
      "deployable":[{slug, display_name, emoji, description}, ...]
    }
    """
    if not _localhost_only(request):
        return web.Response(status=403, text="localhost only")

    # Lazy imports so pairing.py stays lightweight for the extension path
    import agents
    import bots

    # Hub row (for the t.me deep-link)
    hub_row = db.query_one("SELECT username FROM bots WHERE role='hub'")
    hub_username = hub_row["username"] if hub_row and hub_row["username"] else None

    # Deployed agent bots
    deployed_rows = [r for r in bots.deployed_rows() if r.get("role") == "agent"]
    deployed_slugs = {r["agent_slug"] for r in deployed_rows if r.get("agent_slug")}

    deployed_out = []
    for r in deployed_rows:
        slug = r["agent_slug"]
        spec = agents.get(slug) or {}
        chat_id = r.get("owner_chat_id")
        schedules = []
        if chat_id is not None:
            sch_rows = db.query(
                "SELECT id, macro_name, cron FROM schedules "
                "WHERE chat_id=? AND agent_slug=? ORDER BY id",
                (chat_id, slug),
            )
            schedules = [
                {"id": s["id"], "cron": s["cron"], "name": s["macro_name"]}
                for s in sch_rows
            ]
        deployed_out.append({
            "slug": slug,
            "display_name": spec.get("display_name", slug),
            "emoji": spec.get("emoji", "🤖"),
            "username": r.get("username"),
            "schedules": schedules,
        })

    # Deployable = every agent in the registry NOT already deployed
    all_agents = agents.list_all()
    deployable_out = [
        {
            "slug": a["slug"],
            "display_name": a["display_name"],
            "emoji": a["emoji"],
            "description": a.get("description", ""),
        }
        for a in all_agents
        if a["slug"] not in deployed_slugs
    ]

    return web.json_response({
        "hub": {"username": hub_username} if hub_username else None,
        "deployed": deployed_out,
        "deployable": deployable_out,
    })


async def _dashboard(request: web.Request) -> web.Response:
    if not _localhost_only(request):
        return web.Response(status=403, text="localhost only")
    return web.Response(text=_DASHBOARD_HTML, content_type="text/html")


async def _appicon(request: web.Request) -> web.Response:
    """Serve the app icon so the dashboard can show + use it as its favicon.

    The file lives at ``backend/assets/appicon.png`` in dev and under the
    PyInstaller ``_MEIPASS`` tree in the bundled app.
    """
    if not _localhost_only(request):
        return web.Response(status=403, text="localhost only")
    path = _bundled_asset("appicon.png")
    if path is None:
        return web.Response(status=404, text="appicon.png missing from bundle")
    return web.FileResponse(
        path,
        headers={
            # The asset ships with the app, so a long cache is safe — it only
            # changes at release time, and the browser will re-fetch when the
            # user reloads. Avoids the dashboard re-downloading on every
            # 5-second poll of /api/state.
            "Cache-Control": "public, max-age=86400",
        },
    )


_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>CtxAnt Dashboard</title>
<link rel="icon" type="image/png" href="/assets/appicon.png" />
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
    --green: #16a34a;
    --sidebar-bg: #fafafa;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f0f10;
      --fg: #f5f5f5;
      --muted: #a1a1aa;
      --card: #1c1c20;
      --border: #2e2e33;
      --sidebar-bg: #151517;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro", "Helvetica Neue", sans-serif;
    margin: 0; background: var(--bg); color: var(--fg);
    -webkit-font-smoothing: antialiased;
  }
  header {
    padding: 16px 24px; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
    background: var(--bg); position: sticky; top: 0; z-index: 10;
  }
  header h1 { margin: 0; font-size: 20px; }
  header .hub { font-size: 13px; color: var(--muted); }
  header .hub a { color: var(--accent); text-decoration: none; }
  .layout { display: grid; grid-template-columns: 280px 1fr; min-height: calc(100vh - 57px); }
  .sidebar {
    background: var(--sidebar-bg); border-right: 1px solid var(--border);
    padding: 20px 18px; overflow-y: auto;
  }
  .sidebar h2 { font-size: 12px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--muted); margin: 0 0 12px; }
  .sidebar .item {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; padding: 12px; margin-bottom: 10px;
  }
  .sidebar .title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
  .sidebar .desc { font-size: 12px; color: var(--muted); margin-bottom: 10px;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; }
  .sidebar button {
    width: 100%; padding: 6px 10px; font-size: 12px; font-weight: 600;
    background: var(--accent); color: white; border: 0; border-radius: 6px;
    cursor: pointer;
  }
  .sidebar button:hover { background: var(--accent-hover); }
  .sidebar button[disabled] { opacity: .5; cursor: not-allowed; }
  main { padding: 24px 28px; overflow-y: auto; }
  main h2 { margin: 0 0 16px; font-size: 16px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
  .agent-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px 20px; margin-bottom: 14px;
  }
  .agent-card .head { display: flex; justify-content: space-between; align-items: flex-start; }
  .agent-card .name { font-size: 17px; font-weight: 700; margin-bottom: 2px; }
  .agent-card .meta { font-size: 13px; color: var(--muted); }
  .status-pill {
    display: inline-block; padding: 2px 10px; border-radius: 10px;
    font-size: 11px; font-weight: 600; background: var(--green); color: white;
  }
  .schedules {
    margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);
    font-size: 13px;
  }
  .schedules .sch {
    display: flex; justify-content: space-between; padding: 3px 0;
  }
  .schedules .muted { color: var(--muted); }
  .agent-card .actions {
    margin-top: 10px; display: flex; gap: 8px;
  }
  .agent-card .actions button {
    padding: 5px 12px; font-size: 12px; border-radius: 6px; border: 1px solid var(--border);
    background: transparent; color: var(--fg); cursor: pointer;
  }
  .agent-card .actions button:hover { background: var(--card); border-color: var(--accent); }
  .empty {
    padding: 40px 20px; text-align: center; color: var(--muted);
    background: var(--card); border-radius: 10px; border: 1px dashed var(--border);
  }
  .updated { font-size: 11px; color: var(--muted); }
</style>
</head>
<body>

<header>
  <h1>
    <img src="/assets/appicon.png" alt="" width="28" height="28"
         style="vertical-align: -6px; margin-right: 8px; border-radius: 6px;">
    CtxAnt Dashboard
  </h1>
  <div class="hub" id="hubInfo">loading…</div>
</header>

<div class="layout">

  <aside class="sidebar">
    <h2>Deploy a new agent</h2>
    <div id="deployableList">
      <div class="empty" style="padding: 20px 12px; font-size: 12px;">loading…</div>
    </div>
  </aside>

  <main>
    <h2>Deployed agents</h2>
    <div id="deployedList">
      <div class="empty">loading…</div>
    </div>
    <p class="updated" id="updatedAt"></p>
  </main>

</div>

<script>
async function refresh() {
  try {
    const r = await fetch('/api/state');
    const state = await r.json();
    render(state);
    document.getElementById('updatedAt').textContent =
      'Last refreshed ' + new Date().toLocaleTimeString();
  } catch (e) {
    document.getElementById('updatedAt').textContent =
      'Error refreshing — is the backend running?';
  }
}

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function render(state) {
  // Hub info
  const hub = document.getElementById('hubInfo');
  if (state.hub && state.hub.username) {
    hub.innerHTML = 'Hub: <a href="https://t.me/' + esc(state.hub.username) +
                    '" target="_blank">@' + esc(state.hub.username) + '</a>';
  } else {
    hub.textContent = 'Hub: (checking in…)';
  }

  // Deployed agents
  const deployed = document.getElementById('deployedList');
  if (!state.deployed || state.deployed.length === 0) {
    deployed.innerHTML =
      '<div class="empty">No agents deployed yet. Tap <b>Deploy</b> on an agent in the sidebar to get started.</div>';
  } else {
    deployed.innerHTML = state.deployed.map(a => {
      const schedules = (a.schedules || []).length ? `
        <div class="schedules">
          <b>Schedules</b>
          ${a.schedules.map(s => `
            <div class="sch">
              <span>${esc(s.cron)}</span>
              <span class="muted">#${esc(s.id)}</span>
            </div>`).join('')}
        </div>` : `
        <div class="schedules muted">No schedules. Set one with <code>/schedule &lt;when&gt;</code> in the agent's chat.</div>`;

      const tmeUrl = a.username ? 'https://t.me/' + a.username : '';
      return `
        <div class="agent-card">
          <div class="head">
            <div>
              <div class="name">${esc(a.emoji)} ${esc(a.display_name)}</div>
              <div class="meta">${a.username ? '@' + esc(a.username) : '(no username yet)'} · <code>${esc(a.slug)}</code></div>
            </div>
            <span class="status-pill">● running</span>
          </div>
          ${schedules}
          <div class="actions">
            ${tmeUrl ? `<button onclick="window.open('${tmeUrl}', '_blank')">Open in Telegram</button>` : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  // Deployable sidebar
  const sidebar = document.getElementById('deployableList');
  if (!state.deployable || state.deployable.length === 0) {
    sidebar.innerHTML =
      '<div class="empty" style="padding:16px 10px; font-size:12px;">All starter agents deployed 🎉</div>';
  } else {
    const hubUsername = state.hub && state.hub.username;
    sidebar.innerHTML = state.deployable.map(a => {
      const deployUrl = hubUsername
        ? `https://t.me/${hubUsername}?start=deploy_${encodeURIComponent(a.slug)}`
        : '';
      const attr = deployUrl
        ? `onclick="window.open('${deployUrl}', '_blank')"`
        : 'disabled title="Hub bot not ready yet"';
      return `
        <div class="item">
          <div class="title">${esc(a.emoji)} ${esc(a.display_name)}</div>
          <div class="desc">${esc(a.description || '')}</div>
          <button ${attr}>Deploy</button>
        </div>`;
    }).join('');
  }
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


async def start(port: int = 8766) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/pair", _pair)
    app.router.add_get("/health", _health)
    app.router.add_get("/dashboard", _dashboard)
    app.router.add_get("/api/state", _api_state)
    app.router.add_get("/assets/appicon.png", _appicon)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    logger.info(f"Pairing + dashboard HTTP on http://127.0.0.1:{port}/")
    return runner
