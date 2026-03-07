CREATE INDEX IF NOT EXISTS idx_price_history_ticker_date_desc
ON price_history (ticker, date DESC);

CREATE INDEX IF NOT EXISTS idx_asset_metrics_ticker
ON asset_metrics (ticker);

CREATE INDEX IF NOT EXISTS idx_stocks_asset_class
ON stocks (asset_class);
