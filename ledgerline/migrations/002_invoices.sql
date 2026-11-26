CREATE TABLE invoices (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    customer_ref TEXT NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'open', 'paid', 'void')),
    total TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finalized_at TEXT
);

CREATE INDEX invoices_account_created ON invoices (account_id, created_at, id);

CREATE TABLE invoice_lines (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price TEXT NOT NULL,
    tax_rate TEXT NOT NULL DEFAULT '0'
);
