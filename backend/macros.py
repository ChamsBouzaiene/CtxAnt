import db

# Starter pack shipped with every install. Imported per-chat via `/install`.
STARTER_PACK: dict[str, str] = {
    "morning": (
        "Open Gmail in a new tab. Scan my unread inbox from the last 24 hours. "
        "Group emails by topic/sender. Tell me the 3 that most likely need a reply, "
        "list the senders of any obvious promos, and give me the count of the rest. "
        "Then open Google Calendar and list today's events in one line each."
    ),
    "summary": (
        "The user will give you a URL. Open it in a new tab, read the main content, "
        "and reply with a 5-bullet TL;DR in plain English. Close the tab when done."
    ),
    "watch": (
        "The user will give you a product URL and a target price. Open the URL, find "
        "the current price. If it is already at or below the target, tell them immediately. "
        "Otherwise report the current price and remind them to /schedule this macro."
    ),
    "unsub": (
        "Open Gmail. Search for 'unsubscribe' in the last 30 days. For each of the top 10 "
        "promotional senders, open one of their emails, find the unsubscribe link, open it, "
        "and complete the unsubscribe flow. Report which ones succeeded and which need manual action."
    ),
    "jobs": (
        "The user will give you a job title. Open LinkedIn Jobs, filter to the last 24 hours "
        "for that title, and list the top 10 postings with company, location, and a 1-line summary. "
        "Do not apply — just list."
    ),
    "reply": (
        "Open my most recently received email in Gmail. Read it. Draft a polite, concise reply "
        "appropriate to the tone. Do NOT send it — just show me the draft here so I can approve."
    ),
    "flight": (
        "The user will give you origin, destination, and dates. Open Google Flights, search, "
        "and return the 3 cheapest options with airline, total price, stops, and departure time."
    ),
    "compare": (
        "The user will give you a product. Check the price on Amazon, Walmart, and Target. "
        "Return a 3-row table with price, link, and stock status for each."
    ),
    "post": (
        "The user will give you post text. Open twitter.com in one tab and linkedin.com in another. "
        "Compose the post on each, but DO NOT click publish — just prepare the compose windows and "
        "report back so the user can review and send."
    ),
    "receipts": (
        "Open Gmail. Search for receipts and invoices from the last 30 days "
        "(queries like 'invoice', 'receipt', 'your order'). For each, extract sender, amount, "
        "and date into a list. Return the summary."
    ),
}


def install_starter_pack(chat_id: int) -> int:
    """Install all starter macros that don't already exist. Returns count added."""
    added = 0
    for name, prompt in STARTER_PACK.items():
        if not get(chat_id, name):
            save(chat_id, name, prompt)
            added += 1
    return added


def save(chat_id: int, name: str, prompt: str) -> None:
    db.execute(
        "INSERT INTO macros(chat_id,name,prompt) VALUES(?,?,?) "
        "ON CONFLICT(chat_id,name) DO UPDATE SET prompt=excluded.prompt",
        (chat_id, name, prompt),
    )


def get(chat_id: int, name: str) -> str | None:
    row = db.query_one(
        "SELECT prompt FROM macros WHERE chat_id=? AND name=?",
        (chat_id, name),
    )
    return row["prompt"] if row else None


def list_all(chat_id: int) -> list[tuple[str, str]]:
    rows = db.query(
        "SELECT name, prompt FROM macros WHERE chat_id=? ORDER BY name",
        (chat_id,),
    )
    return [(r["name"], r["prompt"]) for r in rows]


def delete(chat_id: int, name: str) -> bool:
    cur = db.execute(
        "DELETE FROM macros WHERE chat_id=? AND name=?",
        (chat_id, name),
    )
    return cur.rowcount > 0
