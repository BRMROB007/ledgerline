# ledgerline

Invoicing, payments and refunds API. Multi-tenant; every request is scoped to
the account that owns the API key.

## Run

```
make install
LEDGERLINE_DB=./ledgerline.sqlite3 make run
```

Interactive docs at `/docs`.

## API

| Method | Path | Notes |
| - | - | - |
| POST | /v1/invoices | create draft |
| GET | /v1/invoices | list, `status`, `limit`, `cursor` |
| GET | /v1/invoices/{id} | |
| POST | /v1/invoices/{id}/finalize | draft -> open |
| POST | /v1/invoices/{id}/void | open -> void |
| POST | /v1/payments | capture against an open invoice |
| GET | /v1/payments/{id} | |
| POST | /v1/refunds | full or partial |
| POST | /v1/refunds/bulk | up to 500 payments per batch |
| GET | /v1/refunds/{id} | |
| GET | /v1/payments/{id}/refunds | |
| GET | /v1/audit | account audit trail |

Auth: `Authorization: Bearer <api key>`. Writes accept `Idempotency-Key`.

Amounts are decimal strings in the invoice currency (`"129.90"`). See
[docs/money.md](docs/money.md).

## Layout

```
ledgerline/
  app.py          application factory
  auth.py         API key -> account
  db.py           SQLite connection, migrations
  money.py        Decimal parsing and rounding
  schemas.py      request/response models
  routers/        HTTP layer
  services/       business rules
  migrations/     numbered SQL files, applied in order
```

## Tests

```
make test
make lint
```
