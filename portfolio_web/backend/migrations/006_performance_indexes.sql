-- Performance indexes for frequently queried paths
-- Covers: session lookups, stock filtering, portfolio listing, price queries

-- Session token lookups (auth middleware on every request)
CREATE INDEX IF NOT EXISTS idx_user_sessions_token
ON user_sessions (token)
WHERE revoked_at IS NULL;

-- Session user lookups
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id
ON user_sessions (user_id);

-- Stock filtering by sector + exchange (market data screening)
CREATE INDEX IF NOT EXISTS idx_stocks_sector_exchange
ON stocks (sector, exchange);

-- Single ticker lookups
CREATE INDEX IF NOT EXISTS idx_stocks_ticker
ON stocks (ticker);

-- Saved portfolios per user (ordered by most recent)
CREATE INDEX IF NOT EXISTS idx_saved_portfolios_user_created
ON saved_portfolios (user_id, created_at DESC);

-- Auth action token lookups (password reset / email verify)
CREATE INDEX IF NOT EXISTS idx_auth_action_tokens_hash
ON auth_action_tokens (token_hash);

-- Price history date-only index for global date range queries
CREATE INDEX IF NOT EXISTS idx_price_history_date
ON price_history (date DESC);

-- Price history composite index for per-ticker latest price lookups (LATERAL joins)
CREATE INDEX IF NOT EXISTS idx_price_history_ticker_date
ON price_history (ticker, date DESC);
