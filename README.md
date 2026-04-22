# CtxAnt

> **Text your browser anything.** CtxAnt is an AI sidekick that lives in *your* Chrome and takes orders from Telegram — logged into your accounts, reading your tabs, doing the boring things.

Unlike cloud agents that open a sandboxed, cookie-free browser that knows nothing about you, CtxAnt drives the Chrome you're already signed into. You chat with it from Telegram. Everything runs on your Mac; the only data that leaves your machine is the prompt you send to your AI provider.

---

## What you get in v1

A Mac menu-bar app that runs:

- **One hub bot** (your control bot in Telegram) and **N agent bots** — each a separate Telegram bot bound to one specific job.
- A **starter pack of 6 guided agents**: Job Hunter, Deal Finder, Inbox Triage, Social Poster, Researcher, Morning Digest. Each one walks you through a setup flow (no prompt engineering needed) and remembers your answers.
- **Schedules** — any agent can run on a cron you define in its chat (`/schedule every day at 9am`). Scheduled runs DM you from the agent bot that owns the job.
- **Queued UX** — one Chrome, one queue. If agent B wants the browser while agent A is using it, B's bot immediately tells you "⏳ queued behind Job Hunter" and runs when the lock frees.
- **Usage tracking** — `/usage` in the hub shows tokens and $ spent per agent.
- **BYOK** — you pay xAI or Anthropic directly. Typical cost: <$2/month.

## Install (Mac)

**Recommended path — the `.app` bundle:**

1. Download `CtxAnt.dmg` from [releases](https://github.com/ChamsBouzaiene/CtxAnt/releases) (or build it yourself, see [DEVELOPMENT.md](./DEVELOPMENT.md)).
2. Drag **CtxAnt** to **Applications**.
3. Launch it. A setup window opens and walks you through:
   - Creating your hub bot in [@BotFather](https://t.me/BotFather) and pasting the token.
   - Picking your AI provider (Grok or Claude) and pasting the API key.
   - Installing the Chrome extension (Load Unpacked from `chrome://extensions`).
4. A 🪄 icon appears in your menu bar. Open your hub bot in Telegram and send `/start`.

The wizard writes everything to `~/Library/Application Support/ctxant/.env` (owner-only permissions). You never touch a config file.

**Running from source** — see [DEVELOPMENT.md](./DEVELOPMENT.md).

## First run in Telegram

Once the app is running and Chrome is loaded:

1. In your hub bot, send `/start`. You get an inline keyboard with the 6 starter agents.
2. Tap one (e.g. **🧑‍💼 Job Hunter**). The hub walks you through the BotFather ritual for that specific agent — creating a second bot that *is* the Job Hunter.
3. Paste the new bot's token back into the hub chat. The hub spins up the agent bot live.
4. Open the new agent bot in Telegram. Send `/start`. It asks 3–5 guided setup questions (role, cities, CV, cadence…) and stores your answers.
5. Send `/run` in that agent's chat. It does the thing.

Deploy as many agents as you want — each gets its own Telegram bot, its own chat, its own memory.

## Commands

### Hub bot

| Command | What it does |
|---|---|
| `/start` | Pick an agent to deploy |
| `/agents` | List your deployed bots |
| `/deploy <slug>` | Start the deploy wizard for an agent |
| `/undeploy <slug>` | Stop and remove an agent bot (memory preserved) |
| `/usage` | Tokens + $ across all agents, with per-agent breakdown |
| `/stop_all` | Cancel every running task |
| `/help` | Command reference |

### Agent bot

Short commands — the agent *is* the context.

| Command | What it does |
|---|---|
| `/start` | Greet + run setup flow if not set up |
| `/run [args]` | Execute the agent against current memory |
| `/settings` | Re-walk the setup flow to update memory |
| `/status` | Memory + schedule peek |
| `/schedule <when>` | e.g. `every day at 9am`, `every 30 minutes`, `in 5 minutes` |
| `/schedules` | List this agent's schedules |
| `/cancel <id>` | Cancel a schedule |
| `/reset` | Clear conversation history (keeps memory) |
| `/stop` | Cancel the current run |

Plain text → conversational message routed through this agent's prompt + memory.
Photo with a caption → vision-enabled run.

## Privacy & cost

- **Runs locally.** The Telegram bot, the backend, and your Chrome are all on your Mac. Nothing persists in the cloud.
- **BYOK.** Your AI key goes directly from your Mac to xAI or Anthropic. We never see it, and there's no shared CtxAnt account.
- **Your logins stay yours.** CtxAnt drives your real Chrome — it doesn't copy your cookies anywhere, it just controls the window you already have open.
- **Typical cost:** <$2/month for 5 macros a day on Grok. `/usage` in the hub shows real-time spend so there are no surprises.

## Project structure

```
ctxant/
├── backend/
│   ├── main.py              Entry: boots pairing + ws + multi-bot runtime
│   ├── ctxant_app.py         Mac menu-bar entry (rumps + threaded main.py)
│   ├── onboarding.py        pywebview first-run wizard
│   ├── config.py            .env loader (app-support > cwd)
│   ├── bots.py              Multi-bot runtime (hub + N agent Applications)
│   ├── hub_handlers.py      Hub bot commands (/deploy, /agents, /usage…)
│   ├── agent_handlers.py    Agent bot commands (/run, /settings, /schedule…)
│   ├── agents.py            Agent registry, starter pack, memory, prompt render
│   ├── claude_agent.py      AI tool-use loop (Grok + Claude) + browser Lock
│   ├── browser_bridge.py    WebSocket server for the extension
│   ├── scheduler.py         APScheduler, per-agent cron
│   ├── usage.py             Token + $ accounting
│   ├── db.py                SQLite schema + queries
│   ├── pairing.py           Localhost /pair endpoint for the extension
│   ├── machine_tools.py     Local shell / fs tools
│   └── requirements.txt
├── extension/               Chrome MV3 extension
├── installer/
│   ├── ctxant.spec           PyInstaller spec for ctxant.app
│   ├── build_mac.sh         Build .app and optionally .dmg
│   └── README.md            Packaging notes
└── DEVELOPMENT.md           Running from source, testing, architecture deep-dive
```

## Available tools (what the AI can do)

| Category | Tools |
|---|---|
| **Browser** | screenshot · navigate · click · type · scroll · get_page_content · evaluate_js · list_tabs · switch_tab · new_tab · close_tab |
| **Machine** | run_command · read_file · write_file · list_directory · get_working_directory |

Vision input: send an agent a photo and it'll reason over the image (e.g. CV photo → Job Hunter fills an application).

## Contributing

See [DEVELOPMENT.md](./DEVELOPMENT.md) for running from source, testing each scenario, and the multi-bot architecture walkthrough.

## License

MIT — see [LICENSE](./LICENSE).

---

Built by [Chams Bouzaiene](https://github.com/ChamsBouzaiene).
