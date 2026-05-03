"""Local HTTP server (aiohttp on 127.0.0.1:8766).

Serves:

  GET /pair                — Chrome extension fetches WS_SECRET here on first
                             run. Localhost-only and origin-gated to the
                             configured chrome-extension:// allowlist.
  GET /health              — trivial "is the backend up" probe.
  GET /dashboard           — HTML dashboard: deployed agents + routines +
                             sidebar of deployable agents. Served to the
                             user's default browser when they click
                             'Open Dashboard' in the menu bar.
  GET /api/state           — JSON blob backing the dashboard (polled every 5s).
  GET /dashboard/agent/{slug}
                           — HTML detail page for a single starter or custom
                              agent inside the localhost dashboard.
  GET /api/agent/{slug}    — Rich JSON manifest for a single agent, used by
                             the detail page so /api/state stays lean.
  GET /assets/appicon.png  — the brand mark, used by the dashboard page.
                             Localhost-only like the rest.
"""

import json
import logging
import secrets
import sys
from pathlib import Path

from aiohttp import web

import config
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


def _manifest_path() -> Path | None:
    """Locate the shared agent manifest JSON for both dev and bundled builds."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        candidates += [
            base / "web" / "templates" / "agent-manifests.json",
            base / "templates" / "agent-manifests.json",
        ]
    candidates.append(Path(__file__).resolve().parent.parent / "web" / "templates" / "agent-manifests.json")
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_manifests() -> dict:
    path = _manifest_path()
    if path is None:
        logger.warning("agent-manifests.json not found")
        return {"flagship": {}, "agents": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read agent-manifests.json")
        return {"flagship": {}, "agents": []}


def _starter_manifest(slug: str) -> dict | None:
    manifests = _load_manifests()
    if manifests.get("flagship", {}).get("slug") == slug:
        return manifests["flagship"]
    return next((a for a in manifests.get("agents", []) if a.get("slug") == slug), None)


def _agent_presentational(slug: str, spec: dict | None = None) -> dict:
    starter = _starter_manifest(slug)
    icon = None
    tagline = ""
    description = ""
    if starter:
        icon = starter.get("icon")
        tagline = starter.get("tagline", "") or ""
        description = starter.get("catalog_blurb", "") or starter.get("long_description", "") or ""
    if spec:
        description = description or (spec.get("description") or "")
        tagline = tagline or (spec.get("description") or "")
    return {
        "icon": icon,
        "tagline": tagline.strip(),
        "description": description.strip(),
    }


def _schedule_preview(schedules: list[dict] | list[str]) -> str:
    if not schedules:
        return "No schedules yet"
    first = schedules[0]
    cron = first.get("cron", "") if isinstance(first, dict) else str(first)
    if len(schedules) == 1:
        return cron
    return f"{cron} +{len(schedules) - 1} more"


def _custom_manifest(slug: str) -> dict | None:
    import agents

    spec = agents.get(slug)
    if not spec:
        return None

    bot_row = db.query_one(
        "SELECT username, owner_chat_id FROM bots WHERE role='agent' AND agent_slug=? ORDER BY id DESC LIMIT 1",
        (slug,),
    )
    chat_id = bot_row["owner_chat_id"] if bot_row and bot_row["owner_chat_id"] is not None else None
    mem = agents.memory_all(chat_id, slug) if chat_id is not None else {}
    schedules = []
    if chat_id is not None:
        schedules = [
            r["cron"] for r in db.query(
                "SELECT cron FROM schedules WHERE chat_id=? AND agent_slug=? ORDER BY id",
                (chat_id, slug),
            )
        ]

    task = mem.get("task", "").strip()
    preferences = mem.get("preferences", "").strip()
    description = (spec.get("description") or "").strip()
    has_schedule = bool(schedules)

    return {
        "slug": slug,
        "icon": "custom_agent",
        "emoji": spec.get("emoji", "🤖"),
        "name": spec.get("display_name", slug),
        "tagline": description or "Custom browser workflow with its own Telegram bot.",
        "chips": ["Custom", "Browser"] + (["Scheduled"] if has_schedule else []),
        "long_description": description or (
            "This is a user-built CtxAnt agent. It follows the same chat model as the starter pack, "
            "but the task and preferences were defined manually instead of coming from a preset."
        ),
        "what_it_does": [
            "Runs a custom browser workflow defined by the standing task saved in this bot's setup.",
            "Uses the same logged-in Chrome session as the rest of CtxAnt.",
            "Can be triggered ad hoc from chat or on a recurring schedule.",
            "Keeps its own history, memory, and Telegram chat separate from other agents."
        ],
        "how_to_use": [
            "Open this agent's Telegram chat and use `/settings` if you want to rewrite the standing task.",
            "Use `/run` to test the saved task with the current browser state.",
            "Send a fresh plain-English message if you want to override the saved task for one run.",
            "Add `/schedule <when>` once the output is stable."
        ],
        "commands": [
            {"cmd": "/settings", "description": "Rewrite the standing task or preferences."},
            {"cmd": "/run", "description": "Run the saved standing task now."},
            {"cmd": "/status", "description": "See what memory and schedules are active."},
            {"cmd": "/schedule <when>", "description": "Turn the current task into a recurring automation."}
        ],
        "examples": [
            {
                "title": "Current standing task",
                "what": "What this custom agent is currently configured to do.",
                "setup": [
                    "Open the bot chat",
                    "Use `/settings` if you want to rewrite the task",
                    "Run `/run` to test the current saved workflow"
                ],
                "prompt": task or "No standing task saved yet.",
                "schedule": schedules[0] if schedules else "",
                "result": "When the task is narrow and concrete, the Telegram result is usually a short structured DM."
            }
        ],
        "tips": [
            "Keep the standing task concrete: URLs, steps, filters, and output format.",
            "If the task spans several sites, specify the order and what to compare.",
            "Test with `/run` before making the schedule more frequent."
        ],
        "limitations": [
            "Custom agents inherit the same browser realities as the starter pack: login walls, CAPTCHAs, and brittle sites still apply.",
            "If the task is vague, the run will drift or burn unnecessary steps.",
            "Very frequent schedules are rarely worth it until the workflow is stable."
        ],
        "task": task,
        "preferences": preferences,
        "username": bot_row["username"] if bot_row else None,
        "schedules": schedules,
        "custom": True,
    }


def _manifest_for_slug(slug: str) -> dict | None:
    import agents

    starter = _starter_manifest(slug)
    if starter:
        return {**starter, "custom": False}
    if agents.is_custom(slug):
        return _custom_manifest(slug)
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

    if peer_ip not in ("127.0.0.1", "::1"):
        return web.Response(status=403, text="localhost only")

    allowed_origins = config.allowed_extension_origins()
    if not allowed_origins and not config.CHROME_EXTENSION_ALLOW_ANY_DEV_ORIGIN:
        logger.error("Refusing /pair because no extension allowlist or dev override is configured")
        return web.Response(status=503, text="extension identity is not configured")
    if not config.is_extension_origin_allowed(origin):
        logger.warning("Rejected /pair from unexpected origin %r", origin)
        return web.Response(status=403, text="extension origin not allowed")

    secret = get_or_create_secret()
    return web.json_response(
        {"secret": secret},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET",
            "Vary": "Origin",
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
      "hub":       {"username": "my_ctxant_bot", "ready": true},
      "summary":   {...},
      "deployed":  [{slug, display_name, icon, emoji, username, schedules:[...]}, ...],
      "deployable":[{slug, display_name, icon, emoji, description}, ...]
    }
    """
    if not _localhost_only(request):
        return web.Response(status=403, text="localhost only")

    # Lazy imports so pairing.py stays lightweight for the extension path
    import agents
    import browser_bridge
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
        present = _agent_presentational(slug, spec)
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
        schedule_count = len(schedules)
        status = "scheduled" if schedule_count else "ready"
        deployed_out.append({
            "slug": slug,
            "display_name": spec.get("display_name", slug),
            "icon": present["icon"] or ("custom_agent" if agents.is_custom(slug) else None),
            "emoji": spec.get("emoji", "🤖"),
            "description": present["description"] or present["tagline"],
            "tagline": present["tagline"] or present["description"],
            "username": r.get("username"),
            "custom": agents.is_custom(slug),
            "schedules": schedules,
            "schedule_count": schedule_count,
            "schedule_preview": _schedule_preview(schedules),
            "status": status,
            "status_label": "Scheduled" if status == "scheduled" else "Ready",
        })

    # Deployable = every agent in the registry NOT already deployed
    all_agents = agents.list_all()
    deployable_out = [
        {
            "slug": a["slug"],
            "display_name": a["display_name"],
            "icon": _agent_presentational(a["slug"], a).get("icon"),
            "emoji": a["emoji"],
            "description": _agent_presentational(a["slug"], a).get("description") or a.get("description", ""),
        }
        for a in all_agents
        if a["slug"] not in deployed_slugs
    ]

    return web.json_response({
        "hub": {"username": hub_username, "ready": bool(hub_username)} if hub_username else {"username": None, "ready": False},
        "summary": {
            "deployed_count": len(deployed_out),
            "scheduled_count": sum(1 for agent in deployed_out if agent["schedule_count"] > 0),
            "deployable_count": len(deployable_out),
            "hub_ready": bool(hub_username),
            "browser_connected": bool(browser_bridge.status_snapshot().get("connected")),
            "browser_message": browser_bridge.status_snapshot().get("message"),
        },
        "deployed": deployed_out,
        "deployable": deployable_out,
    })


async def _api_agent_detail(request: web.Request) -> web.Response:
    if not _localhost_only(request):
        return web.Response(status=403, text="localhost only")

    slug = request.match_info.get("slug", "").strip()
    if not slug:
        return web.Response(status=400, text="missing slug")

    import agents

    payload = _manifest_for_slug(slug)
    if payload is None:
        spec = agents.get(slug)
        if spec:
            present = _agent_presentational(slug, spec)
            payload = {
                "slug": slug,
                "icon": present["icon"],
                "emoji": spec.get("emoji", "🤖"),
                "name": spec.get("display_name", slug),
                "tagline": present["tagline"] or spec.get("description", ""),
                "long_description": spec.get("description", "") or "Agent details are not available yet.",
                "what_it_does": [],
                "how_to_use": [],
                "commands": [],
                "examples": [],
                "tips": [],
                "limitations": [],
                "chips": ["Agent"],
                "custom": False,
            }
        else:
            return web.Response(status=404, text="unknown agent")

    bot_row = db.query_one(
        "SELECT username, owner_chat_id FROM bots WHERE role='agent' AND agent_slug=? ORDER BY id DESC LIMIT 1",
        (slug,),
    )
    hub_row = db.query_one("SELECT username FROM bots WHERE role='hub'")
    schedules = []
    if bot_row and bot_row["owner_chat_id"] is not None:
        schedules = [
            {"id": row["id"], "cron": row["cron"]}
            for row in db.query(
                "SELECT id, cron FROM schedules WHERE chat_id=? AND agent_slug=? ORDER BY id",
                (bot_row["owner_chat_id"], slug),
            )
        ]

    payload = {
        **payload,
        "icon": payload.get("icon") or ("custom_agent" if payload.get("custom") else None),
        "username": payload.get("username") or (bot_row["username"] if bot_row else None),
        "schedules": payload.get("schedules") or schedules,
        "schedule_count": len(payload.get("schedules") or schedules),
        "schedule_preview": _schedule_preview(payload.get("schedules") or schedules),
        "deployed": bot_row is not None,
        "hub_username": hub_row["username"] if hub_row and hub_row["username"] else None,
        "deploy_url": (
            f"https://t.me/{hub_row['username']}?start=deploy_{slug}"
            if hub_row and hub_row["username"] and not (bot_row is not None) and not payload.get("custom")
            else None
        ),
    }
    return web.json_response(payload)


async def _dashboard(request: web.Request) -> web.Response:
    if not _localhost_only(request):
        return web.Response(status=403, text="localhost only")
    return web.Response(text=_DASHBOARD_HTML, content_type="text/html")


async def _dashboard_agent_detail(request: web.Request) -> web.Response:
    if not _localhost_only(request):
        return web.Response(status=403, text="localhost only")
    slug = request.match_info.get("slug", "").strip()
    if not slug:
        return web.Response(status=400, text="missing slug")
    return web.Response(text=_dashboard_agent_page(slug), content_type="text/html")


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


async def _dashboard_asset(request: web.Request) -> web.Response:
    if not _localhost_only(request):
        return web.Response(status=403, text="localhost only")
    name = request.match_info.get("name", "").strip()
    if not name or "/" in name or "\\" in name:
        return web.Response(status=404, text="missing asset")
    path = _bundled_asset(name)
    if path is None:
        return web.Response(status=404, text=f"{name} missing from bundle")
    return web.FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>CtxAnt Dashboard</title>
<link rel="icon" type="image/png" href="/assets/appicon.png" />
<link rel="stylesheet" href="/dashboard/assets/dashboard.css" />
</head>
<body data-page="dashboard">
  <div class="dashboard-backdrop" aria-hidden="true">
    <div class="dashboard-glow glow-a"></div>
    <div class="dashboard-glow glow-b"></div>
  </div>
  <div class="dashboard-shell">
    <header class="dashboard-header">
      <div class="shell dashboard-header-inner">
        <a class="dashboard-brand" href="/dashboard" aria-label="CtxAnt dashboard home">
          <img src="/assets/appicon.png" alt="" width="38" height="38" />
          <span>
            <strong>CtxAnt</strong>
            <small>Local dashboard</small>
          </span>
        </a>
        <div class="dashboard-header-status" id="hubInfo">Loading hub status…</div>
        <div class="dashboard-header-actions">
          <a class="btn btn-secondary" href="https://ctxant.com/templates/" target="_blank" rel="noopener">Agents catalog</a>
          <a class="btn btn-primary" id="hubAction" href="#" target="_blank" rel="noopener" aria-disabled="true">Open hub bot</a>
        </div>
      </div>
    </header>

    <main class="shell dashboard-main">
      <section class="dashboard-hero" id="dashboardHero">
        <div>
          <div class="eyebrow">Signed-in control surface</div>
          <h1>Monitor deployed agents, schedules, and what to launch next.</h1>
          <p class="lede">The same CtxAnt system, but oriented around what is live on this machine right now.</p>
        </div>
        <div class="refresh-meta" id="updatedAt">Waiting for first refresh…</div>
      </section>

      <section class="dashboard-summary" id="summaryStrip">
        <div class="summary-card loading">Loading summary…</div>
      </section>

      <section class="dashboard-layout">
        <div class="dashboard-primary">
          <div class="section-head">
            <div>
              <div class="eyebrow">Deployed agents</div>
              <h2>Live workflows on this machine</h2>
            </div>
          </div>
          <div id="deployedList">
            <div class="empty-state">Loading deployed agents…</div>
          </div>
        </div>

        <aside class="dashboard-rail">
          <div class="section-head compact">
            <div>
              <div class="eyebrow">Quick deploy</div>
              <h2>Add another starter agent</h2>
            </div>
          </div>
          <div id="deployableList">
            <div class="empty-state compact">Loading starter agents…</div>
          </div>
        </aside>
      </section>
    </main>
  </div>
  <script src="/dashboard/assets/dashboard.js"></script>
</body>
</html>
"""


def _dashboard_agent_page(slug: str) -> str:
    safe_slug = json.dumps(slug)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>CtxAnt Agent Details</title>
<link rel="icon" type="image/png" href="/assets/appicon.png" />
<link rel="stylesheet" href="/dashboard/assets/dashboard.css" />
</head>
<body data-page="agent-detail" data-slug={safe_slug}>
  <div class="dashboard-backdrop" aria-hidden="true">
    <div class="dashboard-glow glow-a"></div>
    <div class="dashboard-glow glow-b"></div>
  </div>
  <div class="dashboard-shell">
    <header class="dashboard-header">
      <div class="shell dashboard-header-inner">
        <a class="dashboard-brand" href="/dashboard" aria-label="Back to dashboard">
          <img src="/assets/appicon.png" alt="" width="38" height="38" />
          <span>
            <strong>CtxAnt</strong>
            <small>Agent details</small>
          </span>
        </a>
        <div class="dashboard-header-status">Manifest and live setup</div>
        <div class="dashboard-header-actions">
          <a class="btn btn-secondary" href="/dashboard">Back to dashboard</a>
        </div>
      </div>
    </header>

    <main class="shell dashboard-detail-shell">
      <div id="agentDetailApp" class="empty-state">Loading agent details…</div>
    </main>
  </div>
  <script src="/dashboard/assets/dashboard.js"></script>
</body>
</html>"""


async def start(port: int = 8766) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/pair", _pair)
    app.router.add_get("/health", _health)
    app.router.add_get("/dashboard", _dashboard)
    app.router.add_get("/dashboard/agent/{slug}", _dashboard_agent_detail)
    app.router.add_get("/dashboard/assets/{name}", _dashboard_asset)
    app.router.add_get("/api/state", _api_state)
    app.router.add_get("/api/agent/{slug}", _api_agent_detail)
    app.router.add_get("/assets/appicon.png", _appicon)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    logger.info(f"Pairing + dashboard HTTP on http://127.0.0.1:{port}/")
    return runner
