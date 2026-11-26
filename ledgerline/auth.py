import hashlib
import secrets
import sqlite3
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request

from . import db


@dataclass(frozen=True)
class Principal:
    account_id: str
    key_prefix: str


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def issue_key(conn: sqlite3.Connection, account_id: str) -> str:
    key = "ll_live_" + secrets.token_urlsafe(24)
    conn.execute(
        "INSERT INTO api_keys (key_hash, prefix, account_id) VALUES (?, ?, ?)",
        (hash_key(key), key[:12], account_id),
    )
    return key


def create_account(conn: sqlite3.Connection, name: str, currency: str = "EUR") -> str:
    account_id = db.new_id("acct")
    conn.execute(
        "INSERT INTO accounts (id, name, currency, created_at) VALUES (?, ?, ?, ?)",
        (account_id, name, currency, db.now()),
    )
    return account_id


def get_conn(request: Request) -> sqlite3.Connection:
    return request.app.state.conn


def principal(
    authorization: str | None = Header(default=None),
    conn: sqlite3.Connection = Depends(get_conn),
) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    row = conn.execute(
        "SELECT account_id, prefix FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
        (hash_key(authorization[7:]),),
    ).fetchone()
    if row is None:
        raise HTTPException(401, "invalid api key")
    return Principal(account_id=row["account_id"], key_prefix=row["prefix"])
