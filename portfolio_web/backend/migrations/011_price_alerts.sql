-- Migration 011: Price alerts / notifications
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_name = 'price_alerts') THEN
        CREATE TABLE price_alerts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
            ticker TEXT NOT NULL,
            condition TEXT NOT NULL CHECK (condition IN ('above', 'below', 'pct_change')),
            threshold DOUBLE PRECISION NOT NULL,
            reference_price DOUBLE PRECISION,
            is_active BOOLEAN DEFAULT TRUE,
            is_triggered BOOLEAN DEFAULT FALSE,
            triggered_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            notes TEXT DEFAULT ''
        );
        CREATE INDEX idx_price_alerts_user ON price_alerts(user_id);
        CREATE INDEX idx_price_alerts_active ON price_alerts(is_active) WHERE is_active = TRUE;
    END IF;
END $$;
