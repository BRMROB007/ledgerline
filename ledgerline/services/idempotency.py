import json
import sqlite3

from .. import db


def lookup(conn: sqlite3.Connection, account_id: str, key: str | None, route: str):
    if not key:
        return None
    row = conn.execute(
        "SELECT response FROM idempotency_keys WHERE account_id = ? AND key = ? AND route = ?",
        (account_id, key, route),
    ).fetchone()
    return json.loads(row["response"]) if row else None


def store(conn: sqlite3.Connection, account_id: str, key: str | None, route: str, response) -> None:
    if not key:
        return
    conn.execute(
        "INSERT OR IGNORE INTO idempotency_keys VALUES (?, ?, ?, ?, ?)",
        (account_id, key, route, json.dumps(response), db.now()),
    )
