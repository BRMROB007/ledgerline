import sqlite3

from fastapi import APIRouter, Depends, Query

from ..auth import Principal, get_conn, principal
from ..schemas import AuditOut
from ..services import audit

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut])
def list_entries(
    limit: int = Query(default=50, ge=1, le=200),
    who: Principal = Depends(principal),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return audit.list_entries(conn, who.account_id, limit)
