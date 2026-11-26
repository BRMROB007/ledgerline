import sqlite3

from fastapi import APIRouter, Depends, Header

from ..auth import Principal, get_conn, principal
from ..schemas import RefundIn, RefundOut
from ..services import idempotency, refunds

router = APIRouter(prefix="/v1/refunds", tags=["refunds"])


@router.post("", response_model=RefundOut, status_code=201)
def create(
    body: RefundIn,
    idempotency_key: str | None = Header(default=None),
    who: Principal = Depends(principal),
    conn: sqlite3.Connection = Depends(get_conn),
):
    replay = idempotency.lookup(conn, who.account_id, idempotency_key, "refunds")
    if replay is not None:
        return replay
    result = refunds.create(conn, who, body)
    idempotency.store(conn, who.account_id, idempotency_key, "refunds", result)
    return result


@router.get("/{refund_id}", response_model=RefundOut)
def get(refund_id: str, who: Principal = Depends(principal),
        conn: sqlite3.Connection = Depends(get_conn)):
    return refunds.get(conn, who.account_id, refund_id)
