-- Migration 012: Portfolio performance snapshots
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_name = 'portfolio_snapshots') THEN
        CREATE TABLE portfolio_snapshots (
            id SERIAL PRIMARY KEY,
            portfolio_id INTEGER NOT NULL REFERENCES saved_portfolios(id) ON DELETE CASCADE,
            snapshot_date DATE NOT NULL,
            actual_value DOUBLE PRECISION NOT NULL,
            projected_value DOUBLE PRECISION,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE UNIQUE INDEX idx_snapshots_portfolio_date ON portfolio_snapshots(portfolio_id, snapshot_date);
        CREATE INDEX idx_snapshots_portfolio ON portfolio_snapshots(portfolio_id);
    END IF;
END $$;
