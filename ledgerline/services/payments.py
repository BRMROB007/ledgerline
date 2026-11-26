import sqlite3
from decimal import Decimal

from .. import db, money
from ..auth import Principal
from ..errors import Conflict, NotFound, Unprocessable
from ..schemas import PaymentIn
from . import audit, invoices


def refunded(conn: sqlite3.Connection, payment_id: str) -> Decimal:
    rows = conn.execute("SELECT amount FROM refunds WHERE payment_id = ?", (payment_id,))
    return money.total(r["amount"] for r in rows)


def _serialize(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "invoice_id": row["invoice_id"],
        "amount": row["amount"],
        "amount_refunded": money.fmt(refunded(conn, row["id"])),
        "method": row["method"],
        "captured_at": row["captured_at"],
    }


def find(conn: sqlite3.Connection, account_id: str, payment_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM payments WHERE id = ? AND account_id = ?", (payment_id, account_id)
    ).fetchone()
    if row is None:
        raise NotFound("payment not found")
    return row


def get(conn: sqlite3.Connection, account_id: str, payment_id: str) -> dict:
    return _serialize(conn, find(conn, account_id, payment_id))


def capture(conn: sqlite3.Connection, who: Principal, body: PaymentIn) -> dict:
    invoice = invoices.get(conn, who.account_id, body.invoice_id)
    if invoice["status"] != "open":
        raise Conflict(f"invoice is {invoice['status']}")
    try:
        amount = money.parse(body.amount)
    except money.MoneyError as exc:
        raise Unprocessable(str(exc)) from exc
    if amount <= 0:
        raise Unprocessable("amount must be positive")
    outstanding = money.parse(invoice["total"]) - money.parse(invoice["amount_paid"])
    if amount > outstanding:
        raise Unprocessable("amount exceeds outstanding balance")
    payment_id = db.new_id("pay")
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?)",
            (payment_id, who.account_id, body.invoice_id, money.fmt(amount), body.method,
             db.now()),
        )
        if amount == outstanding:
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (body.invoice_id,))
        audit.record(conn, who, "payment.captured", payment_id, amount=money.fmt(amount))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return get(conn, who.account_id, payment_id)
