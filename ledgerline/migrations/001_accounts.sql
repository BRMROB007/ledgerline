CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    created_at TEXT NOT NULL
);

CREATE TABLE api_keys (
    key_hash TEXT PRIMARY KEY,
    prefix TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    revoked_at TEXT
);
