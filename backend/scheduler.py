import logging
import re
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta

import db

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
# Callback signature: run_cb(chat_id, name, agent_slug=None).
# Legacy callers that only accept (chat_id, name) still work — we detect and adapt.
_run_cb: Callable | None = None


def init(run_macro_cb: Callable):
    """Start the scheduler and restore jobs from DB.

    `run_macro_cb(chat_id, name, agent_slug=None)` runs a scheduled macro/agent.
    The callback may omit the agent_slug kwarg for legacy compatibility.
    """
    global _scheduler, _run_cb
    _run_cb = run_macro_cb
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    _restore_jobs()


def _restore_jobs():
    for row in db.query("SELECT id, chat_id, macro_name, cron, agent_slug FROM schedules"):
        _add_job_to_scheduler(
            row["id"], row["chat_id"], row["macro_name"], row["cron"],
            agent_slug=row["agent_slug"],
        )


async def _dispatch(chat_id: int, macro_name: str, agent_slug: str | None):
    """Wrapper so legacy 2-arg callbacks still work."""
    if _run_cb is None:
        return
    try:
        return await _run_cb(chat_id, macro_name, agent_slug=agent_slug)
    except TypeError:
        # Callback doesn't accept agent_slug — fall back to legacy signature.
        return await _run_cb(chat_id, macro_name)


def _add_job_to_scheduler(job_id: int, chat_id: int, macro_name: str, spec: str,
                          agent_slug: str | None = None):
    trigger = _parse_trigger(spec)
    if trigger is None:
        logger.warning(f"Bad schedule spec, skipping job {job_id}: {spec}")
        return
    _scheduler.add_job(
        _dispatch,
        trigger=trigger,
        args=[chat_id, macro_name, agent_slug],
        id=f"job_{job_id}",
        replace_existing=True,
    )


def _parse_trigger(spec: str):
    """Parse a human-ish schedule string into an APScheduler trigger.

    Supported forms:
      - "every day at 9am"
      - "every monday at 9am"
      - "every 30 minutes"
      - "every hour"
      - "at 14:30 daily"
      - "in 5 minutes" (one-shot)
      - raw cron "0 9 * * *"
    """
    s = spec.strip().lower()

    # One-shot: "in N minutes|hours"
    m = re.match(r"in (\d+)\s*(minute|minutes|min|hour|hours|hr|hrs)", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = timedelta(minutes=n) if "min" in unit else timedelta(hours=n)
        return DateTrigger(run_date=datetime.now() + delta)

    # Interval: "every N minutes|hours"
    m = re.match(r"every (\d+)\s*(minute|minutes|min|hour|hours|hr|hrs)", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if "min" in unit:
            return IntervalTrigger(minutes=n)
        return IntervalTrigger(hours=n)

    # "every hour" / "every minute"
    if s in ("every hour", "hourly"):
        return IntervalTrigger(hours=1)
    if s in ("every minute",):
        return IntervalTrigger(minutes=1)

    # Daily: "every day at 9am" or "at 9am daily" or "daily at 9am"
    m = re.search(r"(?:every day|daily)\s*(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
    if not m:
        m = re.search(r"at\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:daily|every day)", s)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        return CronTrigger(hour=hour, minute=minute)

    # Weekly: "every monday at 9am"
    dow_map = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6,
               "mon":0,"tue":1,"wed":2,"thu":3,"fri":4,"sat":5,"sun":6}
    m = re.search(r"every\s+(\w+?)\s*(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
    if m and m.group(1) in dow_map:
        dow = dow_map[m.group(1)]
        hour = int(m.group(2))
        minute = int(m.group(3) or 0)
        ampm = m.group(4)
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        return CronTrigger(day_of_week=dow, hour=hour, minute=minute)

    # Raw cron "m h dom mon dow"
    parts = s.split()
    if len(parts) == 5:
        try:
            return CronTrigger(minute=parts[0], hour=parts[1],
                               day=parts[2], month=parts[3], day_of_week=parts[4])
        except Exception:
            return None

    return None


def add(chat_id: int, macro_name: str, spec: str,
        agent_slug: str | None = None) -> int:
    """Save schedule to DB + register with APScheduler. Returns job id.

    Pass `agent_slug` for agent-bound schedules (preferred). Leaving it None
    is the legacy free-form-macro path.
    """
    cur = db.execute(
        "INSERT INTO schedules(chat_id, macro_name, cron, agent_slug) VALUES(?,?,?,?)",
        (chat_id, macro_name, spec, agent_slug),
    )
    job_id = cur.lastrowid
    _add_job_to_scheduler(job_id, chat_id, macro_name, spec, agent_slug=agent_slug)
    return job_id


def list_for_chat(chat_id: int, agent_slug: str | None = None) -> list[dict]:
    """List schedules for a chat. If agent_slug is given, only that agent's."""
    if agent_slug is None:
        rows = db.query(
            "SELECT id, macro_name, cron, created, agent_slug "
            "FROM schedules WHERE chat_id=? ORDER BY id",
            (chat_id,),
        )
    else:
        rows = db.query(
            "SELECT id, macro_name, cron, created, agent_slug "
            "FROM schedules WHERE chat_id=? AND agent_slug=? ORDER BY id",
            (chat_id, agent_slug),
        )
    return [dict(r) for r in rows]


def cancel(chat_id: int, job_id: int) -> bool:
    row = db.query_one("SELECT id FROM schedules WHERE id=? AND chat_id=?", (job_id, chat_id))
    if not row:
        return False
    db.execute("DELETE FROM schedules WHERE id=?", (job_id,))
    try:
        _scheduler.remove_job(f"job_{job_id}")
    except Exception:
        pass
    return True


def shutdown():
    if _scheduler:
        _scheduler.shutdown(wait=False)
