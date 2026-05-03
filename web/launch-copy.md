# CtxAnt — Launch Copy

Ready-to-paste copy for each channel. All variants say the same thing in the voice of that channel. Don't get cute — the product speaks for itself once someone presses Install.

**Core positioning sentence (reuse everywhere):**
> Other AI agents open a fresh browser that doesn't know you. CtxAnt drives *your* Chrome — logged into *your* accounts, looking at *your* tabs — and you message it from Telegram. Build a custom agent for any workflow in 30 seconds: describe the task, pair a bot, done.

**Where to link:** always to `ctxant.com`. Never straight to the DMG unless you're in a reply explaining the install.

**When:** Tuesday. Product Hunt goes live at 12:01am PST. Show HN at 8am PST (peak front-page window). Twitter thread pinned from the same time. Reddit / Indie Hackers / BetaList stagger across the day so replies don't pile up on one channel.

---

## Product Hunt

**Tagline (60 char max):**
> Text any agent. Or build your own in 30 seconds.

**Alternative tagline:**
> The AI agent that uses your browser, not its own

**Topics:** Artificial Intelligence, Productivity, Chrome Extensions, macOS, Telegram Bots

**Description (first paragraph is the hook shown in the feed):**
> CtxAnt is an AI sidekick that lives in your Chrome and takes orders from Telegram. Unlike cloud agents that open a fresh browser, CtxAnt uses *your* real Chrome — logged into your accounts, looking at your tabs, with access to the sites you explicitly ask it to operate on behind the login wall.
>
> **Build your own agents in 30 seconds.** Need a HubSpot agent that follows up on warm leads every morning? A LinkedIn agent that saves new Sales Navigator hits to a sheet? An Instagram agent that reposts your best tweets? Tap ➕ Build your own, describe the task, pair a Telegram bot. Each custom agent has its own memory, schedule, and chat bubble.
>
> Or start from 12 ready-made starters (Job Hunter, Deal Finder, Inbox Triage, Morning Digest, Researcher, Social Poster, Lead Tracker, Meeting Prep, Support Triage, Invoice Collector, Marketplace Monitor, Web Runner). Either way, answer a few questions and you get a dedicated Telegram bot that works for you. Scheduled runs DM you when the work is done.
>
> Everything runs locally. BYOK (xAI or Anthropic), no CtxAnt server, no analytics. Your `.env` never leaves your machine. Typical cost: under $2/month.
>
> Free and open-source. Mac today, Windows and Linux in the next few weeks.

**First comment (Product Hunt norm — post right after the maker comment):**
> Builder here. Quick backstory: I spent a summer evaluating every browser agent framework out there and they all had the same limitation — they open a sandboxed Chromium that doesn't know you. Your LinkedIn session isn't there. Your Amazon Prime isn't there. Your Gmail is locked behind 2FA the agent can't pass. The actual useful tasks live behind your logged-in wall, and no cloud agent can cross it.
>
> CtxAnt flips it: the agent runs in *your* Chrome, driven by a local Python daemon you install as a Mac app. The only interface is a Telegram chat you already have open. It feels less like "using an AI product" and more like having a coworker who happens to be good at browsers.
>
> Happy to answer questions about architecture, privacy tradeoffs, or why multi-bot vs. one mega-bot. Code is MIT and linked below.

---

## Show HN

**Title (80 char max — HN rewards plain descriptions):**
> Show HN: CtxAnt – AI agent that drives your real Chrome, controlled from Telegram

**Body:**
> Hi HN. I got tired of cloud browser agents opening a fresh sandboxed Chromium that doesn't know me — no cookies, no 2FA-passed sessions, no Prime membership, no LinkedIn login. The tasks I actually want automated all live behind my logged-in wall.
>
> CtxAnt is the opposite approach: a Chrome extension plus a local Python daemon (packaged as a Mac app) that drive *your* real Chrome. You message it from Telegram. It reads the DOM, screenshots tabs, clicks, types, navigates — all in the browser you were already using, authenticated as you, with your tabs visible.
>
> Some technical choices worth explaining:
>
> - **WebSocket on 127.0.0.1:8765** between the extension and the local app. No CtxAnt server exists. The pairing secret is generated on first run and fetched by the extension from a localhost HTTP endpoint, so users never touch a config file.
> - **Multi-bot runtime.** One Python process runs N `telegram.ext.Application` pollers — a hub bot and one per deployed agent. They share one Chrome, one SQLite DB, and one global `asyncio.Lock` on the browser. Each agent (Job Hunter, Deal Finder, etc.) gets its own Telegram chat bubble and its own per-user memory (CV, target role, watchlist…). The "team of AI employees" feeling is just... having several bots in your Telegram sidebar.
> - **BYOK, by design.** You paste your own xAI or Anthropic key during onboarding. The app talks to the provider directly. No relay, no analytics, no account system. Typical usage runs under $2/month.
> - **Mac bundle** is PyInstaller + rumps (menu bar). First-run wizard is pywebview. DMG is ~45MB. macOS codesigning + notarization is still pending — there's a one-time right-click-Open Gatekeeper step for launch week.
>
> Source is MIT on GitHub. Windows/Linux are next — the backend already runs headless, only the Mac bundling is platform-specific. Would love feedback on the multi-bot model vs. one personality-switching bot (we built both, shipped multi-bot, open to being wrong).
>
> Landing page with demo GIFs: https://ctxant.com
> Code: https://github.com/ChamsBouzaiene/CtxAnt

**Reply-ready answers for the expected HN questions:**

- *"Why Telegram and not a native chat UI?"* — every chat UI I've used with AI agents is a tab I eventually close. Telegram is a tab I'll never close because my friends are there. Agents messaging me alongside humans makes their output feel like part of my day, not a product I have to open. Also: cross-device for free, push notifications for free, voice input for free (eventually).
- *"Isn't `<all_urls>` permission scary?"* — yes if it's an extension that phones home. The CtxAnt extension only acts on a site when you send a command from your own Telegram bot, and the only network it talks to is `ws://127.0.0.1`. Source is auditable. I'd rather have one transparent extension than the "this site can read your data" prompt on every click.
- *"What stops it from burning $100 of API credits in a loop?"* — hard cap at 6 tool calls per task by default, then asks the user to confirm continuation. History trimmed to last 20 turns. `/usage` shows live $ across all agents. A runaway CtxAnt is capped at single-digit cents.
- *"Windows?"* — the backend is platform-agnostic Python; it's just the Mac bundle (rumps, PyInstaller .app, DMG) that's Mac-only. Windows installer is the first thing after launch week.

---

## Twitter / X thread

10 tweets, one per demo GIF. Pin the thread Tuesday 8am PST. Keep each tweet under 240 chars so screen-readers and quote-tweets fit.

**Tweet 1 (hook, pinned, include the morning-digest GIF):**
> I built an AI agent that uses my real Chrome.
>
> Not a sandbox. My actual browser — logged into my stuff, looking at my tabs. Driven from Telegram.
>
> Build a HubSpot / LinkedIn / Instagram agent in 30 sec. Or pick a starter.
>
> CtxAnt. Mac + Chrome, free, ships today.
>
> [GIF: /morning command → 400 unreads shrink to 3 bullets]

**Tweet 2 (job blast demo):**
> Send it a photo of your resume + "apply to 5 Senior React jobs in Berlin posted today" and it actually does it.
>
> Your LinkedIn session. Your Easy Apply. Your cookies. Because it's your browser.
>
> [GIF: 5 tabs firing Easy Apply in sequence]

**Tweet 3 (price drop demo):**
> Price tracking without signing up for a price-tracking site.
>
> `/watch <amazon-url> below 500`
>
> Telegram ping when it drops.
>
> [GIF: 24h timelapse, price crosses threshold, phone pings]

**Tweet 4 (address update demo):**
> Just moved. Had to update my address on Amazon, Chase, and the DMV.
>
> One message. Three tabs. Done.
>
> [GIF: split-screen, 3 forms fill in parallel]

**Tweet 5 (subscription audit demo):**
> "What am I paying for and never using?"
>
> /audit-subs → scans Gmail for recurring charges → opens each service → lists cost + last-used → offers to cancel.
>
> Found $72/mo I wasn't using.
>
> [GIF: 10 subs surfaced, 3 canceled inline]

**Tweet 6 (form + photo demo):**
> Photo of your kid's birth certificate + link to a summer camp form → filled.
>
> The part of parenting no one warned you about: PDFs.
>
> [GIF: photo upload → filled form screenshot]

**Tweet 7 (flight deal demo):**
> `/flight NYC PAR may 12-18 alert below 500`
>
> Daily check, Telegram ping when it hits.
>
> Stop babysitting Google Flights.
>
> [GIF: price graph → alert]

**Tweet 8 (comparison demo):**
> Same product, three stores, three prices.
>
> /compare airfryer → price grid in 20 seconds.
>
> [GIF: command → 3-column result]

**Tweet 9 (appointment demo):**
> "Book a dentist next Tuesday or Thursday after 5pm within 10 min of 10001, in-network with Aetna"
>
> It researches, opens the booking pages, fills.
>
> [GIF: message → confirmation email]

**Tweet 10 (schedule + CTA):**
> Everything scheduleable. `/schedule every day at 9am` and the agent bot DMs you at 9am with the work done.
>
> Mac + Chrome. Free. BYOK.
> Installs in under 2 minutes.
>
> → ctxant.com
>
> [GIF: morning ping arriving on the lock screen]

**Tweet 11 (build-your-own, include a wizard screen-recording GIF):**
> The thing I'm proudest of: you can build your own agent in 30 seconds.
>
> Tap ➕ Build your own → answer 5 questions → pair a Telegram bot → done.
>
> HubSpot agent. LinkedIn agent. Instagram agent. Whatever you need. Each one gets its own memory, schedule, chat bubble.
>
> [GIF: wizard walkthrough, 5 bubbles, new bot appears]

---

## Reddit

**r/productivity — post format: discussion**

Title: *I built an AI that lives in my Telegram and drives my real Chrome. It saves me about 90 min a day.*

Body:
> For the last six months I've been writing one-off browser scripts for boring tasks — unread triage, price tracking, cross-posting to socials. Each one was maybe 40 minutes well spent, but I kept redoing them every time a site changed a button.
>
> So I built the thing I actually wanted: an AI I text from Telegram that uses my real Chrome — with my logins, my cookies, my everything. Not a sandboxed cloud agent. Chrome extension + a small Mac app.
>
> A few agents I use daily:
>
> - `/morning` — 9am summary of unread email, calendar, and news on topics I follow. Telegram ping instead of opening 3 tabs before coffee.
> - Job Hunter — scans LinkedIn for roles matching my CV and queues Easy Apply for my approval.
> - Deal Finder — watches a few Amazon URLs and pings when a price drops.
>
> Each agent is its own Telegram bot with its own chat, which sounds silly but actually feels like having a team of employees who DM you when something's done.
>
> Free, open source, BYOK (you pay xAI/Anthropic directly, about $2/mo for me). Mac right now, Windows soon.
>
> Happy to go into implementation details if anyone's curious. Link in comments per sub rules.

**r/shortcuts**

Title: *CtxAnt — Siri Shortcuts but for your actual browser, driven by an AI agent*

Body:
> If you like Shortcuts but wished the "open URL" + "get contents" + "run JS" steps were replaced by "describe what you want in English and the AI figures it out," this is that.
>
> It's a Mac app + Chrome extension. You text it from Telegram. It uses your real Chrome session so anything you're logged into works — banks, LinkedIn, Gmail, etc.
>
> Getctxant.app. Free, open source. BYOK so no subscription.

**r/selfhosted**

Title: *CtxAnt — self-hosted AI browser agent. Local Python daemon + Chrome extension. BYOK, no cloud, no telemetry.*

Body:
> For the selfhosted crowd: CtxAnt is a local Python process that runs one or more Telegram bots and a WebSocket bridge to your own Chrome. No CtxAnt server exists. The extension pairs to the local daemon via a secret generated on first run at `http://127.0.0.1:8766/pair`.
>
> - SQLite DB at `~/Library/Application Support/ctxant/`
> - No analytics, no crash reporting, no account system
> - BYOK — you bring your own xAI or Anthropic key
> - Source is MIT on GitHub
>
> Mac bundle is PyInstaller + rumps. If you'd rather run the Python directly (no bundle), that path is documented. Windows and Linux aren't bundled yet but the backend is platform-agnostic — should work headless on a Pi if you wire Chrome to it.
>
> Feedback appreciated, especially on the pairing flow and the Telegram-as-frontend choice.

**r/sideproject**

Title: *Shipped my side project today — CtxAnt, an AI that drives your real Chrome from Telegram*

Body:
> After a few months of nights and weekends, launching today.
>
> Core idea: cloud AI agents open a sandboxed browser that doesn't know you. CtxAnt uses *your* Chrome with your logins, driven from Telegram. Feels less like "using an AI product" and more like having a coworker.
>
> Pick an agent from a gallery (Job Hunter, Deal Finder, Inbox Triage, Morning Digest, Researcher, Social Poster, Lead Tracker, Meeting Prep, Support Triage, Invoice Collector, Marketplace Monitor, Web Runner), answer a few setup questions, and a dedicated Telegram bot starts working for you.
>
> Mac app + Chrome extension. Free and open source. BYOK.
>
> ctxant.com

**r/Telegram**

Title: *CtxAnt — turn your Telegram into an AI command center for your real Chrome*

Body:
> Built this for Telegram people specifically: you create a bot via @BotFather, paste the token into a small Mac app, and now that bot drives your real Chrome. You can deploy multiple bots in one install — I have a Job Hunter bot, a Deal Finder bot, and a Morning Digest bot, each with its own chat.
>
> Open source, BYOK. Link in comments.

---

## Indie Hackers

Title: *Launched today: CtxAnt — my take on why browser agents feel useless (and what to do about it)*

Body:
> **The thesis:**
> Every browser agent I tried in 2025 had the same problem. They open a fresh sandboxed Chromium that isn't logged into anything. So the agent can "search Amazon for an air fryer" but it can't "check my Amazon order history" because it's not you. It can "draft a LinkedIn post" but can't "post it" because it's not logged in as you. The actual useful tasks all live behind your logged-in wall — and the cloud agents can't cross it.
>
> **The bet:**
> Ship an agent that uses *your real Chrome* instead. Extension + local daemon. Your cookies, your tabs, your 2FA, your everything.
>
> **The interface:**
> Telegram. Because the chat UI already exists on every device I own, and bots feel like coworkers when they live next to my actual friends in the sidebar. Also: I don't need to build a web app.
>
> **The shape:**
> One hub bot plus one dedicated bot per agent you deploy. Job Hunter is its own bot. Deal Finder is its own bot. Each has its own chat bubble and its own memory of who you are (CV, target role, watchlist, tone). It feels genuinely different from talking to one mega-bot.
>
> **The factory:**
> The real unlock is you can build your own agents in 30 seconds — tap ➕, describe the task (HubSpot follow-ups, LinkedIn Sales Nav saves, Instagram reposts, whatever), pair a Telegram bot. Each custom agent is fully isolated. Deploy as many as you want.
>
> **The model:**
> BYOK. You bring xAI or Anthropic. I don't touch your data — there is no CtxAnt server, just the Mac app talking to the provider directly from your machine. Typical user spend is under $2/month.
>
> **The status:**
> Shipping today for Mac. Windows/Linux next. Code is MIT. No pricing, no waitlist, no funding round. Just a thing I wanted and figured a few other people would too.
>
> ctxant.com — happy to answer anything in comments.

---

## BetaList

**One-liner:**
> Text any agent. Or build your own in 30 seconds. Your Chrome, controlled from Telegram.

**Description:**
> Install the CtxAnt Mac app + Chrome extension in two minutes. Pick a starter agent (Job Hunter, Deal Finder, Inbox Triage, …) or **build your own** — describe the task in 5 quick answers and deploy a dedicated Telegram bot for it (HubSpot, LinkedIn, Instagram, whatever you need). Each agent uses your real browser with your real logins. Scheduled runs, multi-tab parallelism, BYOK, no CtxAnt server. Mac now, Windows soon.

---

## DM / cold-outreach template (for tagging tech Twitter with a personalized demo)

Replace the bracketed bits before sending. Keep under 600 chars so Twitter doesn't collapse it.

> Hey [NAME] — remembered you tweeted about [THING THEY POSTED ABOUT BROWSER AGENTS / PRODUCTIVITY / TELEGRAM BOTS]. Shipped a thing today you might enjoy: CtxAnt, an AI agent that drives your real Chrome (not a sandbox) and takes orders from Telegram. Free, open source, BYOK. Picked [RELEVANT GIF] for you — [one-sentence why this one]. No ask, just thought you'd find it fun. ctxant.com

---

## 90-second explainer video — narration script

For the hero video on ctxant.com. Voiceover, screen recording, no talking head.

**Beat 1 (0:00–0:10, lay out the problem):**
> AI browser agents are everywhere now. But try one and you'll notice: they open a fresh browser that has no idea who you are. No cookies. No logins. No Prime. No LinkedIn session. So the useful stuff — the stuff behind the login wall — is off-limits.

**Beat 2 (0:10–0:25, introduce the solution):**
> CtxAnt flips it. It doesn't open its own browser. It drives *yours*. Same Chrome you're using right now, with all your tabs and all your sessions intact. And the only interface is a Telegram chat.

**Beat 3 (0:25–0:55, demo montage — three of the ten GIFs, subtle cuts):**
> (morning-digest GIF): "Morning. Summarize my unread." — 400 emails become three bullets.
> (job-blast GIF): "Apply to five Senior Frontend roles in Berlin." — five tabs firing Easy Apply.
> (price-drop GIF): "Watch this Amazon URL below five hundred." — ping arrives when it drops.

**Beat 4 (0:55–1:20, install):**
> Two clicks to install. Download the Mac app, drag it in. Install the Chrome extension. Paste your Telegram bot token and an AI API key. That's it. Your bot is live.

**Beat 5 (1:20–1:30, close):**
> Free. Open source. Bring your own AI key. Your data stays on your machine.
>
> CtxAnt. Text your browser anything. ctxant.com.

---

## Key numbers to know when people ask

- DMG size: ~45 MB
- Time to first working agent, fresh Mac: under 5 min
- Average user monthly AI cost: under $2
- Tools the agent has: screenshot, navigate, click, type, scroll, get_content, tabs, run_command, read/write/list
- Starter pack: 12 agents (job_hunter, deal_finder, inbox_triage, morning_digest, researcher, social_poster, lead_tracker, meeting_prep, support_triage, invoice_collector, marketplace_monitor, web_runner) + "➕ Build your own" factory for custom agents (HubSpot, LinkedIn, Instagram, …)
- Hard cap per task: 6 tool calls before asking the user to confirm continuation
- History retention: last 20 turns per agent chat
- Privacy surface: ws://127.0.0.1:8765 (local), AI provider (yours), Telegram (yours). Nothing else.
