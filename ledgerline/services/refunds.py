import sqlite3
from decimal import Decimal

from .. import db, money
from ..auth import Principal
from ..errors import NotFound, Unprocessable
from ..schemas import BulkRefundIn, RefundIn
from . import audit, idempotency, payments


def _serialize(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "payment_id": row["payment_id"],
        "amount": row["amount"],
        "reason": row["reason"],
        "refunded_at": row["refunded_at"],
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
    if body.amount is None:
        amount = None
    else:
        try:
            amount = money.parse(body.amount)
        except money.MoneyError as exc:
            raise Unprocessable(str(exc)) from exc
    refund_id = db.new_id("re")
    conn.execute("BEGIN IMMEDIATE")
    try:
        remaining = money.parse(payment["amount"]) - payments.refunded(conn, payment["id"])
        if amount is None:
            amount = remaining
        if amount <= 0:
            raise Unprocessable("nothing left to refund" if body.amount is None
                                else "amount must be positive")
        if amount > remaining:
            raise Unprocessable("amount exceeds refundable balance")
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


def _refundable(
    conn: sqlite3.Connection, account_id: str, payment_ids: list[str]
) -> dict[str, Decimal]:
    ids = list(dict.fromkeys(payment_ids))
    marks = ",".join("?" * len(ids))
    balances = {
        r["id"]: money.parse(r["amount"])
        for r in conn.execute(
            f"SELECT id, amount FROM payments WHERE account_id = ? AND id IN ({marks})",
            [account_id, *ids],
        )
    }
    if not balances:
        return balances
    owned = list(balances)
    owned_marks = ",".join("?" * len(owned))
    for r in conn.execute(
        f"SELECT payment_id, amount FROM refunds WHERE payment_id IN ({owned_marks})", owned
    ):
        balances[r["payment_id"]] -= money.parse(r["amount"])
    return balances


def create_bulk(
    conn: sqlite3.Connection, who: Principal, body: BulkRefundIn,
    idempotency_key: str | None = None,
) -> dict:
    batch_id = db.new_id("rb")
    # BEGIN IMMEDIATE takes the write lock before balances are read, so concurrent
    # refunds and overlapping idempotent retries are serialized.
    conn.execute("BEGIN IMMEDIATE")
    try:
        replay = idempotency.lookup(conn, who.account_id, idempotency_key, "refunds.bulk")
        if replay is not None:
            conn.execute("COMMIT")
            return replay
        balances = _refundable(conn, who.account_id, [item.payment_id for item in body.items])
        rows, failed = [], []
        total = money.ZERO
        for item in body.items:
            remaining = balances.get(item.payment_id)
            if remaining is None:
                failed.append({"payment_id": item.payment_id, "message": "payment not found"})
                continue
            if item.amount is None:
                amount = remaining
            else:
                try:
                    amount = money.parse(item.amount)
                except money.MoneyError as exc:
                    failed.append({"payment_id": item.payment_id, "message": str(exc)})
                    continue
            if amount <= 0:
                failed.append({"payment_id": item.payment_id, "message": "nothing to refund"
                               if item.amount is None else "amount must be positive"})
                continue
            if amount > remaining:
                failed.append(
                    {"payment_id": item.payment_id, "message": "amount exceeds refundable balance"}
                )
                continue
            balances[item.payment_id] = remaining - amount
            total += amount
            rows.append(
                (db.new_id("re"), who.account_id, item.payment_id, money.fmt(amount), body.reason,
                 db.now(), batch_id)
            )
        conn.executemany(
            "INSERT INTO refunds (id, account_id, payment_id, amount, reason, refunded_at,"
            " batch_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        audit.record(
            conn, who, "refund.batch_created", batch_id,
            count=len(rows), failed=len(failed), total=money.fmt(total), reason=body.reason,
        )
        created = conn.execute(
            "SELECT * FROM refunds WHERE batch_id = ? ORDER BY rowid", (batch_id,)
        ).fetchall()
        result = {
            "batch_id": batch_id,
            "created": [_serialize(r) for r in created],
            "failed": failed,
            "total_refunded": money.fmt(total),
        }
        idempotency.store(conn, who.account_id, idempotency_key, "refunds.bulk", result)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return result
