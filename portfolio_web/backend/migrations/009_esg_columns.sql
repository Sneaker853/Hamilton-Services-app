-- Migration 009: Add ESG score column to stocks table
-- Stores Environmental, Social, and Governance composite score (0-100)
-- and carbon intensity for ESG-aware portfolio optimization

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'stocks' AND column_name = 'esg_score'
    ) THEN
        ALTER TABLE stocks ADD COLUMN esg_score REAL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'stocks' AND column_name = 'carbon_intensity'
    ) THEN
        ALTER TABLE stocks ADD COLUMN carbon_intensity REAL;
    END IF;
END $$;

-- Index for ESG filtering in optimization queries
CREATE INDEX IF NOT EXISTS idx_stocks_esg_score ON stocks (esg_score) WHERE esg_score IS NOT NULL;
