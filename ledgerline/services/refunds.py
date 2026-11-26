import sqlite3

from .. import db, money
from ..auth import Principal
from ..errors import NotFound, Unprocessable
from ..schemas import BulkRefundIn, RefundIn
from . import audit, payments


def _serialize(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "payment_id": row["payment_id"],
        "amount": row["amount"],
        "reason": row["reason"],
        "created_at": row["refunded_at"],
        "batch_id": row["batch_id"],
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
            "INSERT INTO refunds (id, account_id, payment_id, amount, reason, refunded_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
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


def _refundable(conn: sqlite3.Connection, payment_ids: list[str]) -> dict[str, float]:
    marks = ",".join("?" * len(payment_ids))
    balances = {
        r["id"]: float(r["amount"])
        for r in conn.execute(f"SELECT id, amount FROM payments WHERE id IN ({marks})", payment_ids)
    }
    for r in conn.execute(
        f"SELECT payment_id, amount FROM refunds WHERE payment_id IN ({marks})", payment_ids
    ):
        balances[r["payment_id"]] -= float(r["amount"])
    return balances


def create_bulk(conn: sqlite3.Connection, who: Principal, body: BulkRefundIn) -> dict:
    batch_id = db.new_id("rb")
    balances = _refundable(conn, [item.payment_id for item in body.items])
    rows, failed = [], []
    total = 0.0
    for item in body.items:
        remaining = balances.get(item.payment_id)
        if remaining is None:
            failed.append({"payment_id": item.payment_id, "message": "payment not found"})
            continue
        amount = remaining if item.amount is None else float(item.amount)
        if amount <= 0:
            failed.append({"payment_id": item.payment_id, "message": "nothing to refund"})
            continue
        if amount > remaining:
            failed.append(
                {"payment_id": item.payment_id, "message": "amount exceeds refundable balance"}
            )
            continue
        total += amount
        rows.append(
            (db.new_id("re"), who.account_id, item.payment_id, f"{amount:.2f}", body.reason,
             db.now(), batch_id)
        )
    conn.execute("BEGIN")
    try:
        conn.executemany(
            "INSERT INTO refunds (id, account_id, payment_id, amount, reason, refunded_at,"
            " batch_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        audit.record(
            conn, who, "refund.batch_created", batch_id,
            count=len(rows), failed=len(failed), total=f"{total:.2f}", reason=body.reason,
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    created = conn.execute(
        "SELECT * FROM refunds WHERE batch_id = ? ORDER BY rowid", (batch_id,)
    ).fetchall()
    return {
        "batch_id": batch_id,
        "created": [_serialize(r) for r in created],
        "failed": failed,
        "total_refunded": f"{total:.2f}",
    }
