import db

# Rough $ per 1K tokens (input, output). Update as prices change.
# Sources: x.ai pricing page, anthropic pricing page.
PRICING = {
    ("grok", "grok-2-latest"):         (0.002, 0.010),
    ("grok", "grok-2-1212"):           (0.002, 0.010),
    ("grok", "grok-2-vision-latest"):  (0.002, 0.010),
    ("grok", "grok-3-latest"):         (0.003, 0.015),
    ("grok", "grok-3-mini-latest"):    (0.0003, 0.0005),
    ("claude", "claude-sonnet-4-6"):   (0.003, 0.015),
    ("claude", "claude-opus-4-7"):     (0.015, 0.075),
    ("claude", "claude-haiku-4-5-20251001"): (0.001, 0.005),
}


def record(chat_id: int, provider: str, model: str,
           input_tokens: int, output_tokens: int,
           agent_slug: str | None = None) -> float:
    """Record a usage row. Returns the estimated USD cost for this call.

    `agent_slug` is optional; pass None for hub / free-form chat usage.
    """
    in_price, out_price = PRICING.get(
        (provider, model),
        (0.003, 0.015),  # conservative fallback
    )
    cost = (input_tokens / 1000 * in_price) + (output_tokens / 1000 * out_price)

    db.execute(
        "INSERT INTO usage(chat_id, provider, model, input_tokens, output_tokens, cost_usd, agent_slug) "
        "VALUES(?,?,?,?,?,?,?)",
        (chat_id, provider, model, input_tokens, output_tokens, cost, agent_slug),
    )
    return cost


def summary(chat_id: int) -> dict:
    """Return token/cost totals for today, this month, and all time."""
    rows = {}
    for window, clause in [
        ("today",     "date(ts) = date('now','localtime')"),
        ("this_month","strftime('%Y-%m', ts) = strftime('%Y-%m', 'now','localtime')"),
        ("all_time",  "1=1"),
    ]:
        r = db.query_one(
            f"SELECT COALESCE(SUM(input_tokens),0) AS i, "
            f"       COALESCE(SUM(output_tokens),0) AS o, "
            f"       COALESCE(SUM(cost_usd),0) AS c, "
            f"       COUNT(*) AS n "
            f"FROM usage WHERE chat_id=? AND {clause}",
            (chat_id,),
        )
        rows[window] = {
            "input_tokens":  r["i"],
            "output_tokens": r["o"],
            "cost_usd":      r["c"],
            "calls":         r["n"],
        }
    return rows


def by_agent(chat_id: int, window: str = "this_month") -> list[dict]:
    """Per-agent breakdown for a given window.

    window ∈ {'today', 'this_month', 'all_time'}. Rows with agent_slug IS NULL
    are grouped under '(hub)'. Returned sorted by cost_usd desc.
    """
    clauses = {
        "today":      "date(ts) = date('now','localtime')",
        "this_month": "strftime('%Y-%m', ts) = strftime('%Y-%m', 'now','localtime')",
        "all_time":   "1=1",
    }
    clause = clauses.get(window, clauses["this_month"])
    rows = db.query(
        f"SELECT COALESCE(agent_slug, '(hub)') AS slug, "
        f"       COUNT(*) AS calls, "
        f"       SUM(input_tokens)  AS i, "
        f"       SUM(output_tokens) AS o, "
        f"       SUM(cost_usd)      AS c "
        f"FROM usage WHERE chat_id=? AND {clause} "
        f"GROUP BY COALESCE(agent_slug, '(hub)') "
        f"ORDER BY c DESC",
        (chat_id,),
    )
    return [dict(r) for r in rows]


def format_summary(chat_id: int) -> str:
    s = summary(chat_id)

    def fmt(window: str, label: str) -> str:
        w = s[window]
        return (
            f"*{label}*\n"
            f"  {w['calls']} calls · {w['input_tokens']:,} in + {w['output_tokens']:,} out tokens\n"
            f"  ≈ ${w['cost_usd']:.4f}"
        )

    body = "\n\n".join([
        fmt("today",      "Today"),
        fmt("this_month", "This month"),
        fmt("all_time",   "All time"),
    ])

    # Per-agent breakdown for this month (only if there's usage to report)
    per_agent = by_agent(chat_id, "this_month")
    if per_agent:
        lines = ["", "*By agent (this month)*"]
        for r in per_agent:
            lines.append(f"  {r['slug']}: {r['calls']} calls · ≈ ${r['c']:.4f}")
        body += "\n" + "\n".join(lines)

    return body
