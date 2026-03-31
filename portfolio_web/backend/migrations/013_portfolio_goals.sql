-- Migration 013: Portfolio goals and allocation targets
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_name = 'portfolio_goals') THEN
        CREATE TABLE portfolio_goals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
            portfolio_id INTEGER REFERENCES saved_portfolios(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            target_allocations JSONB NOT NULL DEFAULT '{}',
            rebalance_threshold DOUBLE PRECISION DEFAULT 5.0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX idx_goals_user ON portfolio_goals(user_id);
    END IF;
END $$;
