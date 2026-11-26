from typing import Literal

from pydantic import BaseModel, Field


class LineIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    quantity: int = Field(ge=1, le=10_000)
    unit_price: str
    tax_rate: str = "0"


class InvoiceIn(BaseModel):
    customer_ref: str = Field(min_length=1, max_length=64)
    lines: list[LineIn] = Field(min_length=1, max_length=100)


class LineOut(BaseModel):
    id: str
    description: str
    quantity: int
    unit_price: str
    tax_rate: str


class InvoiceOut(BaseModel):
    id: str
    customer_ref: str
    currency: str
    status: Literal["draft", "open", "paid", "void"]
    total: str
    amount_paid: str
    amount_refunded: str
    created_at: str
    finalized_at: str | None
    lines: list[LineOut]


class InvoicePage(BaseModel):
    data: list[InvoiceOut]
    next_cursor: str | None


class PaymentIn(BaseModel):
    invoice_id: str
    amount: str
    method: Literal["card", "sepa_debit", "bank_transfer"] = "card"


class PaymentOut(BaseModel):
    id: str
    invoice_id: str
    amount: str
    amount_refunded: str
    method: str
    captured_at: str


class RefundIn(BaseModel):
    payment_id: str
    amount: str | None = None
    reason: Literal["requested_by_customer", "duplicate", "fraudulent", "other"] = (
        "requested_by_customer"
    )


class RefundOut(BaseModel):
    id: str
    payment_id: str
    amount: str
    reason: str
    refunded_at: str
    batch_id: str | None = None


class BulkRefundItem(BaseModel):
    payment_id: str
    amount: str | None = None


class BulkRefundIn(BaseModel):
    items: list[BulkRefundItem] = Field(min_length=1, max_length=500)
    reason: Literal["requested_by_customer", "duplicate", "fraudulent", "other"] = (
        "requested_by_customer"
    )


class BulkRefundFailure(BaseModel):
    payment_id: str
    message: str


class BulkRefundOut(BaseModel):
    batch_id: str
    created: list[RefundOut]
    failed: list[BulkRefundFailure]
    total_refunded: str


class AuditOut(BaseModel):
    id: int
    actor: str
    action: str
    subject: str
    detail: dict
    at: str
