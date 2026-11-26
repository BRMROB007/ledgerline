CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    subject TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '{}',
    at TEXT NOT NULL
);

CREATE INDEX audit_account_at ON audit_log (account_id, id);
