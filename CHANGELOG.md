# Changelog

## 3.15.0
- `POST /v1/refunds/bulk`: refund up to 500 payments in one request.
- Refunds carry `batch_id`.
- Requests are serialized on the shared database connection, so one request's rollback
  can no longer undo another's writes.

## 3.14.2
- Fix cursor pagination returning a duplicate row when invoices share a timestamp.

## 3.14.1
- Audit entries now record the API key prefix.

## 3.14.0
- `GET /v1/payments/{id}/refunds`.

## 3.13.0
- Idempotency keys on payments and refunds.

## 3.12.3
- Reject payments on void invoices with 409 instead of 400.

## 3.12.0
- Partial refunds.

## 3.11.0
- Audit trail endpoint.

## 3.10.0
- Line item tax rates.
