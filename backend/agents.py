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
import string
from dataclasses import dataclass, field
from typing import Any, Iterable

import db

logger = logging.getLogger(__name__)


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
]


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
    return [dict(r) for r in db.query("SELECT * FROM agents ORDER BY slug")]


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
