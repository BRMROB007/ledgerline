CREATE TABLE refunds (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    payment_id TEXT NOT NULL REFERENCES payments(id),
    amount TEXT NOT NULL,
    reason TEXT NOT NULL,
    refunded_at TEXT NOT NULL
);

CREATE INDEX refunds_payment ON refunds (payment_id);
