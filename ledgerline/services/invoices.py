import sqlite3
from decimal import Decimal

from .. import db, money
from ..auth import Principal
from ..errors import Conflict, NotFound, Unprocessable
from ..schemas import InvoiceIn
from . import audit


def _line_total(quantity: int, unit_price: Decimal, tax_rate: Decimal) -> Decimal:
    return money.quantize(quantity * unit_price * (1 + tax_rate / 100))


def create(conn: sqlite3.Connection, who: Principal, body: InvoiceIn) -> dict:
    account = conn.execute(
        "SELECT currency FROM accounts WHERE id = ?", (who.account_id,)
    ).fetchone()
    invoice_id = db.new_id("inv")
    total = money.ZERO
    lines = []
    for line in body.lines:
        try:
            unit_price = money.parse(line.unit_price)
            tax_rate = Decimal(line.tax_rate)
        except (money.MoneyError, ArithmeticError) as exc:
            raise Unprocessable(str(exc)) from exc
        if unit_price < 0 or not (0 <= tax_rate <= 100):
            raise Unprocessable("unit_price and tax_rate must not be negative")
        total += _line_total(line.quantity, unit_price, tax_rate)
        lines.append(
            (db.new_id("il"), invoice_id, line.description, line.quantity,
             money.fmt(unit_price), str(tax_rate))
        )
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO invoices (id, account_id, customer_ref, currency, status, total,"
            " created_at) VALUES (?, ?, ?, ?, 'draft', ?, ?)",
            (invoice_id, who.account_id, body.customer_ref, account["currency"],
             money.fmt(total), db.now()),
        )
        conn.executemany("INSERT INTO invoice_lines VALUES (?, ?, ?, ?, ?, ?)", lines)
        audit.record(conn, who, "invoice.created", invoice_id, total=money.fmt(total))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return get(conn, who.account_id, invoice_id)


def _row(conn: sqlite3.Connection, account_id: str, invoice_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM invoices WHERE id = ? AND account_id = ?", (invoice_id, account_id)
    ).fetchone()
    if row is None:
        raise NotFound("invoice not found")
    return row


def amount_paid(conn: sqlite3.Connection, invoice_id: str) -> Decimal:
    rows = conn.execute("SELECT amount FROM payments WHERE invoice_id = ?", (invoice_id,))
    return money.total(r["amount"] for r in rows)


def amount_refunded(conn: sqlite3.Connection, invoice_id: str) -> Decimal:
    rows = conn.execute(
        "SELECT r.amount FROM refunds r JOIN payments p ON p.id = r.payment_id"
        " WHERE p.invoice_id = ?",
        (invoice_id,),
    )
    return money.total(r["amount"] for r in rows)


def _serialize(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    lines = conn.execute(
        "SELECT id, description, quantity, unit_price, tax_rate FROM invoice_lines"
        " WHERE invoice_id = ? ORDER BY rowid",
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "customer_ref": row["customer_ref"],
        "currency": row["currency"],
        "status": row["status"],
        "total": row["total"],
        "amount_paid": money.fmt(amount_paid(conn, row["id"])),
        "amount_refunded": money.fmt(amount_refunded(conn, row["id"])),
        "created_at": row["created_at"],
        "finalized_at": row["finalized_at"],
        "lines": [dict(line) for line in lines],
    }


def get(conn: sqlite3.Connection, account_id: str, invoice_id: str) -> dict:
    return _serialize(conn, _row(conn, account_id, invoice_id))


def list_page(
    conn: sqlite3.Connection,
    account_id: str,
    status: str | None,
    limit: int,
    cursor: str | None,
) -> dict:
    sql = "SELECT * FROM invoices WHERE account_id = ?"
    args: list = [account_id]
    if status:
        sql += " AND status = ?"
        args.append(status)
    if cursor:
        try:
            created_at, last_id = cursor.split("|", 1)
        except ValueError as exc:
            raise Unprocessable("invalid cursor") from exc
        sql += " AND (created_at, id) > (?, ?)"
        args += [created_at, last_id]
    sql += " ORDER BY created_at, id LIMIT ?"
    args.append(limit + 1)
    rows = conn.execute(sql, args).fetchall()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        next_cursor = f"{page[-1]['created_at']}|{page[-1]['id']}"
    return {"data": [_serialize(conn, r) for r in page], "next_cursor": next_cursor}


def finalize(conn: sqlite3.Connection, who: Principal, invoice_id: str) -> dict:
    row = _row(conn, who.account_id, invoice_id)
    if row["status"] != "draft":
        raise Conflict(f"invoice is {row['status']}")
    conn.execute(
        "UPDATE invoices SET status = 'open', finalized_at = ? WHERE id = ?",
        (db.now(), invoice_id),
    )
    audit.record(conn, who, "invoice.finalized", invoice_id)
    return get(conn, who.account_id, invoice_id)


def void(conn: sqlite3.Connection, who: Principal, invoice_id: str) -> dict:
    row = _row(conn, who.account_id, invoice_id)
    if row["status"] != "open":
        raise Conflict(f"invoice is {row['status']}")
    if amount_paid(conn, invoice_id) > 0:
        raise Conflict("invoice has payments")
    conn.execute("UPDATE invoices SET status = 'void' WHERE id = ?", (invoice_id,))
    audit.record(conn, who, "invoice.voided", invoice_id)
    return get(conn, who.account_id, invoice_id)
