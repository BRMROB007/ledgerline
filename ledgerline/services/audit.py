import json
import sqlite3

from .. import db
from ..auth import Principal


def record(
    conn: sqlite3.Connection, who: Principal, action: str, subject: str, **detail
) -> None:
    conn.execute(
        "INSERT INTO audit_log (account_id, actor, action, subject, detail, at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (who.account_id, who.key_prefix, action, subject, json.dumps(detail), db.now()),
    )


def list_entries(conn: sqlite3.Connection, account_id: str, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM audit_log WHERE account_id = ? ORDER BY id DESC LIMIT ?",
        (account_id, limit),
    ).fetchall()
    return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]
