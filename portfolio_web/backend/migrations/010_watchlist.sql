-- Migration 010: Watchlist / favorites table
-- Allows users to save tickers for monitoring

CREATE TABLE IF NOT EXISTS user_watchlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,
    UNIQUE(user_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_user ON user_watchlist (user_id, added_at DESC);
CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON user_watchlist (ticker);
