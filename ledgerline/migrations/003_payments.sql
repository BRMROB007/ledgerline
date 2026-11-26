CREATE TABLE payments (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    amount TEXT NOT NULL,
    method TEXT NOT NULL,
    captured_at TEXT NOT NULL
);

CREATE INDEX payments_invoice ON payments (invoice_id);
