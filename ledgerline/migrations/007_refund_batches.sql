ALTER TABLE refunds ADD COLUMN batch_id TEXT;

CREATE INDEX refunds_batch ON refunds (batch_id);
