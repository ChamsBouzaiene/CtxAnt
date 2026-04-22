import os
import sqlite3
import threading
from pathlib import Path

# DB location: ~/Library/Application Support/ctxant/ctxant.db (Mac)
# Falls back to project-local for dev.
def _db_path() -> Path:
    env = os.getenv("CTXANT_DB_PATH")
    if env:
        return Path(env).expanduser()
    if os.sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "ctxant"
    else:
        base = Path.home() / ".ctxant"
    base.mkdir(parents=True, exist_ok=True)
    return base / "ctxant.db"


_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_db_path(), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _init_schema(_conn)
    return _conn


def _init_schema(c: sqlite3.Connection) -> None:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS kv (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    -- Legacy: free-form macros (kept for backward compatibility, superseded by `agents`)
    CREATE TABLE IF NOT EXISTS macros (
        chat_id  INTEGER NOT NULL,
        name     TEXT NOT NULL,
        prompt   TEXT NOT NULL,
        created  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (chat_id, name)
    );

    CREATE TABLE IF NOT EXISTS schedules (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id    INTEGER NOT NULL,
        macro_name TEXT NOT NULL,
        cron       TEXT NOT NULL,
        created    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS usage (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id       INTEGER NOT NULL,
        ts            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        provider      TEXT NOT NULL,
        model         TEXT NOT NULL,
        input_tokens  INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        cost_usd      REAL NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_usage_chat_ts ON usage (chat_id, ts);

    -- ─── Multi-bot / agent tables (v2 of the schema) ─────────────────────────

    -- Global agent registry. Seeded with the starter pack by agents.py on startup.
    -- One row per agent slug. Users may add custom agents later (same table).
    CREATE TABLE IF NOT EXISTS agents (
        slug              TEXT PRIMARY KEY,
        display_name      TEXT NOT NULL,
        emoji             TEXT NOT NULL DEFAULT '🤖',
        prompt_template   TEXT NOT NULL,
        setup_flow_json   TEXT NOT NULL DEFAULT '[]',
        default_schedule  TEXT,
        description       TEXT NOT NULL DEFAULT '',
        created           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Per-user memory for each agent (CV path, target role, watchlist, tone, …).
    -- Filled by the setup_flow + /settings updates; injected into prompt_template at run time.
    CREATE TABLE IF NOT EXISTS agent_memory (
        chat_id     INTEGER NOT NULL,
        agent_slug  TEXT    NOT NULL,
        key         TEXT    NOT NULL,
        value       TEXT    NOT NULL,
        updated     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (chat_id, agent_slug, key)
    );

    -- Telegram bots this CtxAnt install is running.
    --   role='hub'   -> the control/coordination bot (one row, agent_slug NULL)
    --   role='agent' -> bot bound to a single agent slug (0..N rows)
    CREATE TABLE IF NOT EXISTS bots (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        token         TEXT    NOT NULL UNIQUE,
        role          TEXT    NOT NULL CHECK (role IN ('hub','agent')),
        agent_slug    TEXT,
        display_name  TEXT,
        username      TEXT,
        owner_chat_id INTEGER,
        enabled       INTEGER NOT NULL DEFAULT 1,
        created       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (role, agent_slug, owner_chat_id)
    );
    """)

    # Additive column migrations (safe if re-run; IF NOT EXISTS isn't supported
    # for ALTER TABLE before SQLite 3.35, so we inspect PRAGMA table_info).
    def _has_column(table: str, col: str) -> bool:
        return any(r["name"] == col for r in c.execute(f"PRAGMA table_info({table})").fetchall())

    if not _has_column("schedules", "agent_slug"):
        c.execute("ALTER TABLE schedules ADD COLUMN agent_slug TEXT")
    if not _has_column("usage", "agent_slug"):
        c.execute("ALTER TABLE usage ADD COLUMN agent_slug TEXT")

    c.commit()


def kv_get(key: str, default: str | None = None) -> str | None:
    with _lock:
        row = conn().execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def kv_set(key: str, value: str) -> None:
    with _lock:
        conn().execute(
            "INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn().commit()


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    with _lock:
        cur = conn().execute(sql, params)
        conn().commit()
        return cur


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        return conn().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with _lock:
        return conn().execute(sql, params).fetchone()
