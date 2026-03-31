-- Migration 008: Add portfolio sharing (read-only link)
-- Adds share_token and is_public columns to saved_portfolios

ALTER TABLE saved_portfolios ADD COLUMN IF NOT EXISTS share_token TEXT UNIQUE;
ALTER TABLE saved_portfolios ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_saved_portfolios_share_token ON saved_portfolios (share_token) WHERE share_token IS NOT NULL;
