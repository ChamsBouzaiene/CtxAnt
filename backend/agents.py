"""Agent registry + per-user memory + setup-flow runner.

An *agent* is a reusable task template. It consists of:

    - slug            unique id, e.g. "job_hunter"
    - display_name    "Job Hunter"
    - emoji           "🧑‍💼"
    - prompt_template natural-language instructions with {placeholders} filled from memory
    - setup_flow      list of questions the hub asks once to populate memory
    - default_schedule optional string like "every day at 9am"

Agents are stored globally in `agents` (seeded on startup from STARTER_PACK).
Per-user customisation lives in `agent_memory(chat_id, agent_slug, key, value)`.

A question in `setup_flow` looks like:

    {
        "key":  "role",
        "type": "text" | "choice" | "multi_choice" | "file" | "boolean",
        "q":    "What role are you after?",
        "options": ["daily", "weekly", "manual"]     # for choice types
        "required": true,
        "help":  "You can skip and set this later with /settings"
    }
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import string
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

import db

logger = logging.getLogger(__name__)

_CUSTOM_SLUG_PREFIX = "custom_"
_DEFAULT_CUSTOM_EMOJI = "🤖"


# ── Starter pack ──────────────────────────────────────────────────────────────

@dataclass
class AgentSpec:
    slug: str
    display_name: str
    emoji: str
    description: str
    prompt_template: str
    setup_flow: list[dict] = field(default_factory=list)
    default_schedule: str | None = None


STARTER_PACK: list[AgentSpec] = [
    AgentSpec(
        slug="job_hunter",
        display_name="Job Hunter",
        emoji="🧑‍💼",
        description="Finds roles matching your profile and preps applications for your approval.",
        prompt_template=(
            "You are the user's Job Hunter agent. "
            "The user is looking for: {role} roles in {cities}. "
            "Open LinkedIn Jobs (https://www.linkedin.com/jobs), filter to roles posted in the last 24h "
            "that match the role and location, and list the top 10 with company, location, and 1-line summary. "
            "Do not apply yet — surface the list so the user can approve which to Easy Apply to. "
            "If a CV is needed for applications, reference the stored file at: {cv_path}."
        ),
        setup_flow=[
            {"key": "role",   "type": "text",   "q": "What role are you looking for? (e.g. 'Senior React Engineer')", "required": True},
            {"key": "cities", "type": "text",   "q": "Which cities, or 'remote'? (comma-separated)",                   "required": True},
            {"key": "cv_path","type": "file",   "q": "Send your CV as a PDF, or type 'skip' to add it later.",         "required": False},
            {"key": "cadence","type": "choice", "q": "How often should I check for new roles?",
             "options": ["Every morning", "Twice a week", "On demand only"], "required": True},
        ],
        default_schedule=None,  # set from cadence answer
    ),
    AgentSpec(
        slug="deal_finder",
        display_name="Deal Finder",
        emoji="🛒",
        description="Watches product prices across sites and DMs you when they drop.",
        prompt_template=(
            "You are the user's Deal Finder agent. "
            "Watchlist: {watchlist}. Price thresholds (URL → max price): {thresholds}. "
            "For each URL, open it, read the current price, and if it is at or below the threshold "
            "tell the user immediately with a direct 'Buy' link. Otherwise report current prices succinctly."
        ),
        setup_flow=[
            {"key": "watchlist",  "type": "text",   "q": "Paste product URLs you want me to watch, one per line.", "required": True},
            {"key": "thresholds", "type": "text",   "q": "For each URL, what max price would you buy at? Format 'url — $price' per line.", "required": True},
            {"key": "cadence",    "type": "choice", "q": "How often should I check?",
             "options": ["Every hour", "Every 6 hours", "Once a day"], "required": True},
        ],
        default_schedule="every 6 hours",
    ),
    AgentSpec(
        slug="inbox_triage",
        display_name="Inbox Triage",
        emoji="📧",
        description="Digests your inbox into need-reply / skim / archive buckets.",
        prompt_template=(
            "You are the user's Inbox Triage agent. Provider: {provider}. "
            "Open the inbox and scan the last 24h of unread mail. "
            "Priority senders (treat as need-reply if anything from them): {priority_senders}. "
            "Return three groups: (1) NEED REPLY — up to 3 items with sender + 1-line reason, "
            "(2) SKIM — short subject list, (3) ARCHIVE-WORTHY — promos / newsletters count only."
        ),
        setup_flow=[
            {"key": "provider", "type": "choice", "q": "Which inbox?",
             "options": ["Gmail", "Outlook", "Other (I'll tell it)"], "required": True},
            {"key": "priority_senders", "type": "text",
             "q": "Emails you never want to miss (boss, spouse, clients) — comma-separated. Or 'skip'.", "required": False},
            {"key": "cadence", "type": "choice", "q": "When should I deliver the digest?",
             "options": ["Every morning 8am", "Twice a day", "On demand only"], "required": True},
        ],
    ),
    AgentSpec(
        slug="social_poster",
        display_name="Social Poster",
        emoji="🐦",
        description="Cross-posts to your accounts, optionally waiting for your approval.",
        prompt_template=(
            "You are the user's Social Poster agent. "
            "Target platforms: {platforms}. Require approval before posting: {approval}. Default tone: {tone}. "
            "Given the user's draft, open each platform in a new tab, adapt the text to that platform's norms "
            "(length, hashtags, @-mentions), and either post directly or show the drafts for approval depending on the setting."
        ),
        setup_flow=[
            {"key": "platforms", "type": "multi_choice",
             "q": "Which platforms should I cross-post to? (tap all)",
             "options": ["X/Twitter", "LinkedIn", "Instagram", "Threads", "Bluesky"], "required": True},
            {"key": "approval", "type": "boolean",
             "q": "Should I always ask you to approve the drafts before posting?", "required": True},
            {"key": "tone", "type": "choice",
             "q": "Default tone?",
             "options": ["Personal", "Professional", "Playful", "No preference"], "required": True},
        ],
    ),
    AgentSpec(
        slug="researcher",
        display_name="Researcher",
        emoji="🔎",
        description="Gives you structured summaries from multiple sources on any topic.",
        prompt_template=(
            "You are the user's Researcher agent. Depth setting: {depth}. Output format: {format}. "
            "The user will ask about a topic. Open the top {depth} most relevant sources across Google / Scholar / news, "
            "read each, and return a summary in the requested format. Cite each claim with its source URL."
        ),
        setup_flow=[
            {"key": "depth", "type": "choice",
             "q": "How thorough should I be by default?",
             "options": ["Fast (3 sources)", "Balanced (6 sources)", "Deep (12 sources)"], "required": True},
            {"key": "format", "type": "choice",
             "q": "Default output format?",
             "options": ["Bulleted summary", "Comparison table", "One-paragraph brief"], "required": True},
        ],
    ),
    AgentSpec(
        slug="lead_tracker",
        display_name="Lead Tracker",
        emoji="🧾",
        description="Scans your CRM for warm leads that need a follow-up and sends the next actions.",
        prompt_template=(
            "You are the user's Lead Tracker agent. CRM: {crm}. "
            "Target pipeline stages: {stages}. Leads count as stale after {stale_window}. "
            "Every run, open the CRM, find leads in those stages with no meaningful activity inside that window, "
            "and return the most important follow-ups as {output_format}. Include the lead name, company, "
            "last activity date, and one recommended next action for each result."
        ),
        setup_flow=[
            {"key": "crm", "type": "choice", "q": "Which CRM should I inspect by default?",
             "options": ["HubSpot", "Salesforce", "Pipedrive", "Other (I'll tell it)"], "required": True},
            {"key": "stages", "type": "text",
             "q": "Which stages count as warm or follow-up worthy? (comma-separated)", "required": True},
            {"key": "stale_window", "type": "choice",
             "q": "When should I treat a lead as stale?",
             "options": ["3 days", "5 days", "7 days", "14 days"], "required": True},
            {"key": "output_format", "type": "choice",
             "q": "How should I summarize the leads?",
             "options": ["Top 5 bullets", "Compact table", "Priority tiers"], "required": True},
            {"key": "cadence", "type": "choice", "q": "How often should I check for follow-up gaps?",
             "options": ["Every weekday morning", "Every day at 9am", "On demand only"], "required": True},
        ],
        default_schedule="every day at 9am",
    ),
    AgentSpec(
        slug="meeting_prep",
        display_name="Meeting Prep",
        emoji="🗂",
        description="Builds a short pre-meeting brief from calendar, CRM, and company context before a call.",
        prompt_template=(
            "You are the user's Meeting Prep agent. Calendar source: {calendar_source}. "
            "Prepare the briefing {lead_time} before each meeting. Account context source: {context_sources}. "
            "For every relevant upcoming meeting, gather the attendee/company context, recent notes if visible, "
            "and return a short brief with these sections: {brief_sections}."
        ),
        setup_flow=[
            {"key": "calendar_source", "type": "choice", "q": "Which calendar should I use?",
             "options": ["Google Calendar", "Outlook Calendar", "Other (I'll tell it)"], "required": True},
            {"key": "lead_time", "type": "choice", "q": "How far ahead should I prepare the brief?",
             "options": ["15 minutes before", "30 minutes before", "1 hour before", "Each morning"], "required": True},
            {"key": "context_sources", "type": "text",
             "q": "Which sources should I consult? (e.g. HubSpot, company site, LinkedIn)", "required": True},
            {"key": "brief_sections", "type": "text",
             "q": "Which sections do you want in the briefing? (comma-separated)", "required": True},
            {"key": "cadence", "type": "choice", "q": "How should I trigger the prep?",
             "options": ["Before every meeting", "Every weekday morning", "On demand only"], "required": True},
        ],
        default_schedule=None,
    ),
    AgentSpec(
        slug="support_triage",
        display_name="Support Triage",
        emoji="🎫",
        description="Sweeps urgent support tickets and groups what needs fast human attention.",
        prompt_template=(
            "You are the user's Support Triage agent. Support tool: {platform}. "
            "Urgency rules: {urgency_rules}. VIP accounts: {vip_customers}. "
            "Open the support queue, find tickets that match the urgency rules, and return a concise triage grouped as "
            "{output_mode}. Each item should include the customer, subject, age or SLA risk, and the main blocker."
        ),
        setup_flow=[
            {"key": "platform", "type": "choice", "q": "Which support tool should I scan?",
             "options": ["Zendesk", "Intercom", "Help Scout", "Other (I'll tell it)"], "required": True},
            {"key": "urgency_rules", "type": "text",
             "q": "What counts as urgent? (e.g. enterprise customers, billing, outages, angry sentiment)", "required": True},
            {"key": "vip_customers", "type": "text",
             "q": "Any VIP customers to always surface? (comma-separated or 'skip')", "required": False},
            {"key": "output_mode", "type": "choice",
             "q": "How should I structure the summary?",
             "options": ["Critical / Soon / Watchlist", "Top 5 bullets", "Owner handoff list"], "required": True},
            {"key": "cadence", "type": "choice", "q": "How often should I scan the queue?",
             "options": ["Every hour", "Every 4 hours", "Every weekday morning", "On demand only"], "required": True},
        ],
        default_schedule="every hour",
    ),
    AgentSpec(
        slug="invoice_collector",
        display_name="Invoice Collector",
        emoji="🧮",
        description="Logs into vendor billing portals, pulls the latest invoices, and summarizes what changed.",
        prompt_template=(
            "You are the user's Invoice Collector agent. Vendor portals to inspect: {vendors}. "
            "What to extract from each run: {fields_to_extract}. Download preference: {download_preference}. "
            "Open each portal, find the newest invoices or receipts, summarize what is new since the last run, "
            "and report any missing downloads or billing anomalies."
        ),
        setup_flow=[
            {"key": "vendors", "type": "text",
             "q": "Which vendor portals should I check? (name + URL per line)", "required": True},
            {"key": "fields_to_extract", "type": "text",
             "q": "What details should I include? (e.g. amount, due date, invoice number)", "required": True},
            {"key": "download_preference", "type": "choice",
             "q": "What should I do with matching invoices?",
             "options": ["Summarize only", "Summarize + download PDFs", "Summarize + flag missing PDFs"], "required": True},
            {"key": "cadence", "type": "choice", "q": "How often should I collect invoices?",
             "options": ["Every weekday morning", "Once a day", "Once a week", "On demand only"], "required": True},
        ],
        default_schedule="once a day",
    ),
    AgentSpec(
        slug="marketplace_monitor",
        display_name="Marketplace Monitor",
        emoji="📍",
        description="Watches marketplace searches and pings only when new matching listings appear.",
        prompt_template=(
            "You are the user's Marketplace Monitor agent. Searches to watch: {search_urls}. "
            "Maximum price: {max_price}. Geography or delivery constraint: {geography}. "
            "For each saved search, open it, detect net-new listings that fit the criteria, and return only the "
            "listings worth attention with title, price, condition, and link."
        ),
        setup_flow=[
            {"key": "search_urls", "type": "text",
             "q": "Paste the search URLs to monitor, one per line.", "required": True},
            {"key": "max_price", "type": "text",
             "q": "What price ceiling should I apply? (e.g. EUR 1500 or 'none')", "required": False},
            {"key": "geography", "type": "text",
             "q": "Any location or delivery constraints? (city, country, radius, pickup only, etc.)", "required": False},
            {"key": "freshness_rule", "type": "choice",
             "q": "What should count as worth pinging?",
             "options": ["Only net-new listings", "Net-new and price drops", "Everything that matches"], "required": True},
            {"key": "cadence", "type": "choice", "q": "How often should I re-check the searches?",
             "options": ["Every 4 hours", "Every 8 hours", "Once a day", "On demand only"], "required": True},
        ],
        default_schedule="every 4 hours",
    ),
    AgentSpec(
        slug="morning_digest",
        display_name="Morning Digest",
        emoji="☀️",
        description="A daily briefing: calendar, inbox highlights, topic news.",
        prompt_template=(
            "You are the user's Morning Digest agent. Topics of interest: {topics}. "
            "At run time: (1) open Google Calendar, list today's events one-line each. "
            "(2) open Gmail, highlight up to 3 emails that look important from the last 24h. "
            "(3) scan headlines on the user's interest topics and return 1 sentence per topic. "
            "Keep the whole digest under 200 words."
        ),
        setup_flow=[
            {"key": "topics", "type": "text",
             "q": "Which news topics do you care about? (comma-separated, e.g. 'AI, F1, Bitcoin')",
             "required": False},
            {"key": "send_time", "type": "choice",
             "q": "When should I send it?",
             "options": ["7am", "8am", "9am", "On demand only"], "required": True},
        ],
        default_schedule="every day at 8am",
    ),
    AgentSpec(
        slug="web_runner",
        display_name="Web Runner",
        emoji="🛠",
        description="Your generic web hand — any task, one-shot or on a schedule.",
        prompt_template=(
            "You are the user's general-purpose web agent. "
            "You have a browser and can navigate, extract, fill forms, click — anything on the open web.\n\n"
            "Standing task (used when you're triggered with no fresh instructions, "
            "e.g. a bare /run or a scheduled fire): {task}\n"
            "Standing preferences (apply to every run): {preferences}\n\n"
            "If the user's current message is non-empty, treat it as fresh instructions that "
            "OVERRIDE the standing task for this run only. Otherwise carry out the standing task. "
            "Report concisely: what you did, what you found, and any blocker (login wall, captcha, "
            "missing info) so the user can intervene."
        ),
        setup_flow=[
            {"key": "task", "type": "text",
             "q": ("Standing task? (what I run when you trigger me with no arguments or on a "
                   "schedule). Example: 'Summarize the top 5 HN stories and send a 3-sentence "
                   "brief per story.' Reply 'skip' if you only want to send me one-shot tasks."),
             "required": False},
            {"key": "preferences", "type": "text",
             "q": ("Standing preferences? (tone, language, 'always cite URLs', "
                   "'pause if you hit a login wall', etc.). Reply 'skip' for none."),
             "required": False},
        ],
        default_schedule=None,
    ),
]

STARTER_SLUG_ORDER = [agent.slug for agent in STARTER_PACK]
_STARTER_POSITION = {slug: index for index, slug in enumerate(STARTER_SLUG_ORDER)}


# ── Registry ──────────────────────────────────────────────────────────────────

def seed_starter_pack() -> None:
    """Insert starter-pack agents if they don't already exist in the DB.

    Safe to call on every startup; we ON CONFLICT ignore existing slugs so users'
    customisations on their side aren't clobbered (in future they'll be able to
    fork a slug; for v1 the registry is effectively read-only)."""
    for a in STARTER_PACK:
        db.execute(
            "INSERT INTO agents(slug, display_name, emoji, prompt_template, "
            "setup_flow_json, default_schedule, description) "
            "VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(slug) DO NOTHING",
            (a.slug, a.display_name, a.emoji, a.prompt_template,
             json.dumps(a.setup_flow), a.default_schedule, a.description),
        )


def get(slug: str) -> dict | None:
    row = db.query_one("SELECT * FROM agents WHERE slug=?", (slug,))
    return dict(row) if row else None


def list_all() -> list[dict]:
    rows = [dict(r) for r in db.query("SELECT * FROM agents")]

    def sort_key(row: dict) -> tuple[int, int, str]:
        slug = row.get("slug", "")
        is_custom = slug.startswith(_CUSTOM_SLUG_PREFIX)
        if is_custom:
            return (1, 0, str(row.get("display_name", slug)).lower())
        return (0, _STARTER_POSITION.get(slug, 10_000), str(row.get("display_name", slug)).lower())

    return sorted(rows, key=sort_key)


def setup_flow(slug: str) -> list[dict]:
    row = db.query_one("SELECT setup_flow_json FROM agents WHERE slug=?", (slug,))
    if not row:
        return []
    try:
        return json.loads(row["setup_flow_json"])
    except json.JSONDecodeError:
        return []


# ── Memory ────────────────────────────────────────────────────────────────────

def memory_get(chat_id: int, slug: str, key: str, default: str = "") -> str:
    row = db.query_one(
        "SELECT value FROM agent_memory WHERE chat_id=? AND agent_slug=? AND key=?",
        (chat_id, slug, key),
    )
    return row["value"] if row else default


def memory_set(chat_id: int, slug: str, key: str, value: str) -> None:
    db.execute(
        "INSERT INTO agent_memory(chat_id, agent_slug, key, value) "
        "VALUES(?,?,?,?) "
        "ON CONFLICT(chat_id, agent_slug, key) DO UPDATE SET "
        "  value=excluded.value, updated=CURRENT_TIMESTAMP",
        (chat_id, slug, key, value),
    )


def memory_all(chat_id: int, slug: str) -> dict[str, str]:
    rows = db.query(
        "SELECT key, value FROM agent_memory WHERE chat_id=? AND agent_slug=?",
        (chat_id, slug),
    )
    return {r["key"]: r["value"] for r in rows}


def memory_clear(chat_id: int, slug: str) -> int:
    cur = db.execute(
        "DELETE FROM agent_memory WHERE chat_id=? AND agent_slug=?",
        (chat_id, slug),
    )
    return cur.rowcount


def is_setup_complete(chat_id: int, slug: str) -> bool:
    """True iff every required setup-flow key has a non-empty value in memory."""
    flow = setup_flow(slug)
    mem = memory_all(chat_id, slug)
    for q in flow:
        if q.get("required") and not mem.get(q["key"], "").strip():
            return False
    return True


# ── Prompt rendering ──────────────────────────────────────────────────────────

class _SafeDict(dict):
    """Renders missing keys as '(not set)' instead of raising KeyError."""

    def __missing__(self, key: str) -> str:  # type: ignore[override]
        return "(not set)"


def render_prompt(chat_id: int, slug: str, extra_vars: dict | None = None) -> str:
    """Fill the agent's prompt_template with memory values + any extras."""
    agent = get(slug)
    if not agent:
        raise ValueError(f"Unknown agent: {slug}")
    mem = memory_all(chat_id, slug)
    if extra_vars:
        mem = {**mem, **extra_vars}
    tpl = agent["prompt_template"]
    try:
        return string.Formatter().vformat(tpl, (), _SafeDict(mem))
    except Exception as e:
        logger.warning(f"Prompt render failed for {slug}: {e}")
        return tpl


# ── Helpers used by the telegram handler ──────────────────────────────────────

def setup_next_question(chat_id: int, slug: str) -> dict | None:
    """Return the next unanswered setup question for this user+agent, or None."""
    flow = setup_flow(slug)
    mem = memory_all(chat_id, slug)
    for q in flow:
        k = q["key"]
        if q.get("required") and not mem.get(k, "").strip():
            return q
    # All required answered; offer optional ones that are still blank too
    for q in flow:
        if not q.get("required") and not mem.get(q["key"], "").strip():
            return q
    return None


def iter_starter() -> Iterable[AgentSpec]:
    return iter(STARTER_PACK)


# ── Custom (user-built) agents ────────────────────────────────────────────────
#
# Users build their own agents via the hub bot's "➕ Build your own" wizard.
# We write a fresh row into the `agents` table — the rest of the system
# (picker, deploy flow, /run, /schedule, memory, history) is slug-agnostic and
# picks it up automatically. Each custom agent is a distinct slug, so:
#   - different users can each have a "HubSpot" agent (namespaced by chat_id)
#   - one user can have HubSpot + LinkedIn + Instagram side-by-side
#   - deleting and recreating the same nickname creates a fresh slug, so the
#     previous version's memory/history don't leak into the new one.


_CUSTOM_PROMPT_TEMPLATE = (
    "You are the user's {display_name} agent.{description_sentence}\n\n"
    "Standing task (used when you're triggered with no fresh instructions, "
    "e.g. a bare /run or a scheduled fire):\n"
    "{task}\n\n"
    "Standing preferences (apply to every run):\n"
    "{preferences}\n\n"
    "If the user's current message is non-empty, treat it as fresh instructions "
    "that OVERRIDE the standing task for this run only. Otherwise carry out the "
    "standing task. You have a browser — navigate, extract, click, fill forms, "
    "whatever the task needs. Report concisely: what you did, what you found, "
    "and any blocker (login wall, captcha, missing input) so the user can intervene."
)


def _slugify(s: str) -> str:
    """Lowercase, replace non-alphanumerics with '-', collapse runs, trim."""
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "agent"


def _mint_custom_slug(nickname: str, chat_id: int) -> str:
    """Build a slug that's unique per user+nickname+moment.

    Format: custom_<kebab-nickname>_<chat_id>_<unix_ts>. If that collides
    (rapid double-tap), we append a 4-char random suffix.
    """
    base = f"{_CUSTOM_SLUG_PREFIX}{_slugify(nickname)}_{chat_id}_{int(time.time())}"
    if db.query_one("SELECT 1 FROM agents WHERE slug=?", (base,)) is None:
        return base
    # Collision (same second, same nickname, same user). Tack on entropy.
    return f"{base}_{secrets.token_hex(2)}"


def is_custom(slug: str) -> bool:
    """Did this agent come from the user's 'Build your own' wizard?"""
    return slug.startswith(_CUSTOM_SLUG_PREFIX)


def create_custom_agent(
    chat_id: int,
    nickname: str,
    emoji: str = "",
    description: str = "",
    task: str = "",
    preferences: str = "",
) -> str:
    """Insert a new user-built agent into the registry.

    Returns the generated slug. The new agent immediately appears in the hub
    bot's picker and can be deployed as its own Telegram bot.

    Inputs are treated as plain user-supplied strings — no Telegram-specific
    types leak in here. The helper is transport-agnostic so Phase 5 (Slack /
    WhatsApp) can call the same function from a different handler.
    """
    display_name = nickname.strip() or "Custom Agent"
    emoji = (emoji.strip() or _DEFAULT_CUSTOM_EMOJI)[:4]  # cap at a grapheme+modifier
    description = description.strip()
    task = task.strip()
    preferences = preferences.strip() or "(none set)"

    slug = _mint_custom_slug(display_name, chat_id)

    # The prompt is baked literally, not rendered from memory — custom agents
    # have an empty setup_flow, and the user's answers go straight into the
    # template at create time.
    description_sentence = f" {description.rstrip('.')}." if description else ""
    prompt = _CUSTOM_PROMPT_TEMPLATE.format(
        display_name=display_name,
        description_sentence=description_sentence,
        task=task or "(ask the user what to do — no standing task was set at creation time)",
        preferences=preferences,
    )

    # List-view description (what shows in the picker). Fall back to a generic
    # line if the user skipped this field.
    list_description = description or f"Custom agent: {display_name}."

    db.execute(
        "INSERT INTO agents(slug, display_name, emoji, prompt_template, "
        "setup_flow_json, default_schedule, description) "
        "VALUES(?,?,?,?,?,?,?)",
        (slug, display_name, emoji, prompt, json.dumps([]), None, list_description),
    )
    logger.info("Created custom agent slug=%s for chat_id=%s", slug, chat_id)
    return slug


def delete_custom_agent(slug: str) -> bool:
    """Remove a custom agent's registry row. Does NOT cascade to memory,
    schedules, conversation history, or the `bots` table — callers that want
    a full wipe should also clear those. Returns True if a row was deleted.

    Safety: refuses to delete non-custom (starter-pack) slugs so a bug in the
    caller can't accidentally wipe Job Hunter.
    """
    if not is_custom(slug):
        logger.warning("Refusing to delete non-custom agent: %s", slug)
        return False
    cur = db.execute("DELETE FROM agents WHERE slug=?", (slug,))
    return cur.rowcount > 0
