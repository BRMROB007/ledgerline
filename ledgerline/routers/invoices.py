import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Query

from ..auth import Principal, get_conn, principal
from ..schemas import InvoiceIn, InvoiceOut, InvoicePage
from ..services import invoices

router = APIRouter(prefix="/v1/invoices", tags=["invoices"])


@router.post("", response_model=InvoiceOut, status_code=201)
def create(body: InvoiceIn, who: Principal = Depends(principal),
           conn: sqlite3.Connection = Depends(get_conn)):
    return invoices.create(conn, who, body)


@router.get("", response_model=InvoicePage)
def list_invoices(
    status: Literal["draft", "open", "paid", "void"] | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = None,
    who: Principal = Depends(principal),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return invoices.list_page(conn, who.account_id, status, limit, cursor)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get(invoice_id: str, who: Principal = Depends(principal),
        conn: sqlite3.Connection = Depends(get_conn)):
    return invoices.get(conn, who.account_id, invoice_id)


@router.post("/{invoice_id}/finalize", response_model=InvoiceOut)
def finalize(invoice_id: str, who: Principal = Depends(principal),
             conn: sqlite3.Connection = Depends(get_conn)):
    return invoices.finalize(conn, who, invoice_id)


@router.post("/{invoice_id}/void", response_model=InvoiceOut)
def void(invoice_id: str, who: Principal = Depends(principal),
         conn: sqlite3.Connection = Depends(get_conn)):
    return invoices.void(conn, who, invoice_id)
