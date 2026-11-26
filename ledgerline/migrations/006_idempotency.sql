CREATE TABLE idempotency_keys (
    account_id TEXT NOT NULL REFERENCES accounts(id),
    key TEXT NOT NULL,
    route TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (account_id, key, route)
);
