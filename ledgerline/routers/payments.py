import sqlite3

from fastapi import APIRouter, Depends, Header

from ..auth import Principal, get_conn, principal
from ..schemas import PaymentIn, PaymentOut, RefundOut
from ..services import idempotency, payments, refunds

router = APIRouter(prefix="/v1/payments", tags=["payments"])


@router.post("", response_model=PaymentOut, status_code=201)
def capture(
    body: PaymentIn,
    idempotency_key: str | None = Header(default=None),
    who: Principal = Depends(principal),
    conn: sqlite3.Connection = Depends(get_conn),
):
    replay = idempotency.lookup(conn, who.account_id, idempotency_key, "payments")
    if replay is not None:
        return replay
    result = payments.capture(conn, who, body)
    idempotency.store(conn, who.account_id, idempotency_key, "payments", result)
    return result


@router.get("/{payment_id}", response_model=PaymentOut)
def get(payment_id: str, who: Principal = Depends(principal),
        conn: sqlite3.Connection = Depends(get_conn)):
    return payments.get(conn, who.account_id, payment_id)


@router.get("/{payment_id}/refunds", response_model=list[RefundOut])
def list_refunds(payment_id: str, who: Principal = Depends(principal),
                 conn: sqlite3.Connection = Depends(get_conn)):
    return refunds.list_for_payment(conn, who.account_id, payment_id)
