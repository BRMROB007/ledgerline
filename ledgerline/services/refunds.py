import sqlite3

from .. import db, money
from ..auth import Principal
from ..errors import NotFound, Unprocessable
from ..schemas import RefundIn
from . import audit, payments


def _serialize(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "payment_id": row["payment_id"],
        "amount": row["amount"],
        "reason": row["reason"],
        "refunded_at": row["refunded_at"],
    }


def get(conn: sqlite3.Connection, account_id: str, refund_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM refunds WHERE id = ? AND account_id = ?", (refund_id, account_id)
    ).fetchone()
    if row is None:
        raise NotFound("refund not found")
    return _serialize(row)


def list_for_payment(conn: sqlite3.Connection, account_id: str, payment_id: str) -> list[dict]:
    payments.find(conn, account_id, payment_id)
    rows = conn.execute(
        "SELECT * FROM refunds WHERE payment_id = ? ORDER BY refunded_at, id", (payment_id,)
    ).fetchall()
    return [_serialize(r) for r in rows]


def create(conn: sqlite3.Connection, who: Principal, body: RefundIn) -> dict:
    payment = payments.find(conn, who.account_id, body.payment_id)
    captured = money.parse(payment["amount"])
    remaining = captured - payments.refunded(conn, payment["id"])
    if body.amount is None:
        amount = remaining
    else:
        try:
            amount = money.parse(body.amount)
        except money.MoneyError as exc:
            raise Unprocessable(str(exc)) from exc
    if amount <= 0:
        raise Unprocessable("nothing left to refund" if body.amount is None
                            else "amount must be positive")
    if amount > remaining:
        raise Unprocessable("amount exceeds refundable balance")
    refund_id = db.new_id("re")
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO refunds VALUES (?, ?, ?, ?, ?, ?)",
            (refund_id, who.account_id, payment["id"], money.fmt(amount), body.reason, db.now()),
        )
        audit.record(
            conn, who, "refund.created", refund_id,
            payment_id=payment["id"], amount=money.fmt(amount), reason=body.reason,
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return get(conn, who.account_id, refund_id)
