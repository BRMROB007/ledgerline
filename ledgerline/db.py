import os
import sqlite3
from datetime import UTC, datetime
from importlib import resources
from uuid import uuid4

DEFAULT_PATH = "ledgerline.sqlite3"


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(
        path or os.environ.get("LEDGERLINE_DB", DEFAULT_PATH),
        check_same_thread=False,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT)"
    )
    applied = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
    files = sorted(
        f for f in resources.files("ledgerline.migrations").iterdir() if f.name.endswith(".sql")
    )
    ran = []
    for f in files:
        if f.name in applied:
            continue
        conn.executescript(f.read_text())
        conn.execute("INSERT INTO schema_migrations VALUES (?, ?)", (f.name, now()))
        ran.append(f.name)
    return ran


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:20]}"
