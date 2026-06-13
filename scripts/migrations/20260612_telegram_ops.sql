-- Telegram ops: dedup notifications + optional config audit
CREATE TABLE IF NOT EXISTS telegram_ops_notification (
    id BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    message_id TEXT NOT NULL DEFAULT '',
    notify_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (conversation_id, message_id, notify_type)
);

CREATE INDEX IF NOT EXISTS idx_telegram_ops_notification_created
    ON telegram_ops_notification (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_telegram_ops_notification_type
    ON telegram_ops_notification (notify_type, created_at DESC);
