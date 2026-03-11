import yfinance as yf
import psycopg2
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import time
import pandas as pd

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'portfolio_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# Ticker mappings for yfinance
TICKER_MAPPING = {
    'BTC': 'BTC-USD',
    'ETH': 'ETH-USD',
    'XRP': 'XRP-USD',
    'ADA': 'ADA-USD',
    'SOL': 'SOL-USD',
    'DOT': 'DOT-USD',
    'LINK': 'LINK-USD',
    'MATIC': 'MATIC-USD',
    'AVAX': 'AVAX-USD',
    'AAVE': 'AAVE-USD',
    'UNI': 'UNI-USD',
    'SUSHI': 'SUSHI-USD',
    'CRV': 'CRV-USD',
    'GMX': 'GMX-USD',
    'LDO': 'LDO-USD',
    'ARB': 'ARB-USD',
    'OP': 'OP-USD',
    'DYDX': 'DYDX-USD',
    'FIL': 'FIL-USD',
    'ICP': 'ICP-USD',
    'NEAR': 'NEAR-USD',
    'ATOM': 'ATOM-USD',
}

def download_prices(ticker_map, end_date):
    """Download historical price data from yfinance"""
    prices_data = {}
    
    for original_ticker, yf_ticker in list(ticker_map.items()):
        try:
            print(f"Downloading {original_ticker}...", end="", flush=True)
            
            ticker_obj = yf.Ticker(yf_ticker)
            hist = ticker_obj.history(start='2021-02-08', end=end_date)
            
            if hist.empty or len(hist) == 0:
                print(f" SKIP - No data")
                continue
            
            # Ensure we have clean scalar values
            hist = hist.reset_index()
            
            prices = []
            for _, row in hist.iterrows():
                try:
                    date_val = pd.Timestamp(row['Date']).date() if 'Date' in row else None
                    open_val = float(row['Open']) if 'Open' in row and pd.notna(row['Open']) else None
                    high_val = float(row['High']) if 'High' in row and pd.notna(row['High']) else None
                    low_val = float(row['Low']) if 'Low' in row and pd.notna(row['Low']) else None
                    close_val = float(row['Close']) if 'Close' in row and pd.notna(row['Close']) else None
                    volume_val = int(row['Volume']) if 'Volume' in row and pd.notna(row['Volume']) else 0
                    
                    if date_val and close_val and close_val > 0:
                        prices.append({
                            'ticker': original_ticker,
                            'date': date_val,
                            'open': open_val if open_val else close_val,
                            'high': high_val if high_val else close_val,
                            'low': low_val if low_val else close_val,
                            'close': close_val,
                            'volume': volume_val
                        })
                except Exception:
                    continue
            
            if prices:
                prices_data[original_ticker] = prices
                print(f" OK ({len(prices)} records)")
            else:
                print(f" SKIP - No valid prices")
            
            time.sleep(0.3)
            
        except Exception as e:
            print(f" ERROR: {str(e)[:60]}")
            continue
    
    return prices_data


def ensure_price_history_id_default(conn, cur):
    """Ensure price_history.id auto-increments in environments where default is missing."""
    cur.execute(
        """
        SELECT column_default, is_identity
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'price_history'
          AND column_name = 'id'
        """
    )
    row = cur.fetchone()

    if not row:
        return

    column_default, is_identity = row
    if column_default is not None or is_identity == 'YES':
        return

    cur.execute("SELECT COALESCE(MAX(id), 0) FROM price_history")
    max_id = int(cur.fetchone()[0] or 0)

    cur.execute("CREATE SEQUENCE IF NOT EXISTS price_history_id_seq")
    if max_id > 0:
        cur.execute("SELECT setval('price_history_id_seq', %s, true)", (max_id,))
    else:
        cur.execute("SELECT setval('price_history_id_seq', 1, false)")

    cur.execute("ALTER TABLE price_history ALTER COLUMN id SET DEFAULT nextval('price_history_id_seq')")
    cur.execute("ALTER SEQUENCE price_history_id_seq OWNED BY price_history.id")
    conn.commit()
    print("Configured auto-increment default for price_history.id")

def insert_prices(prices_data):
    """Insert prices into database"""
    conn = psycopg2.connect(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    cur = conn.cursor()

    ensure_price_history_id_default(conn, cur)
    
    total_inserted = 0
    failed_tickers = 0
    for ticker, prices in prices_data.items():
        print(f"Inserting {ticker}...", end="", flush=True)
        
        try:
            cur.execute("DELETE FROM price_history WHERE ticker = %s", (ticker,))
            
            batch = [(p['ticker'], p['date'], p['open'], p['high'], p['low'], p['close'], p['volume']) 
                     for p in prices]
            
            cur.executemany(
                "INSERT INTO price_history (ticker, date, open, high, low, close, volume) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                batch
            )
            conn.commit()
            total_inserted += len(prices)
            print(f" OK ({len(prices)} records)")
        except Exception as e:
            conn.rollback()
            failed_tickers += 1
            print(f" ERROR: {str(e)[:60]}")
    
    cur.close()
    conn.close()
    return total_inserted, failed_tickers

if __name__ == "__main__":
    conn = psycopg2.connect(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT ticker FROM stocks ORDER BY ticker")
    all_tickers = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    
    print(f"Found {len(all_tickers)} tickers in database\n")
    
    ticker_map = {}
    for ticker in all_tickers:
        if ticker in TICKER_MAPPING:
            ticker_map[ticker] = TICKER_MAPPING[ticker]
        else:
            ticker_map[ticker] = ticker
    
    print(f"Downloading prices for {len(ticker_map)} tickers...\n")
    
    end_date = datetime.now().date() + timedelta(days=1)
    print(f"Using yfinance end date (exclusive): {end_date}")
    prices_data = download_prices(ticker_map, end_date)

    latest_downloaded_date = None
    for series in prices_data.values():
        if not series:
            continue
        series_latest = max(item['date'] for item in series if item.get('date'))
        if latest_downloaded_date is None or series_latest > latest_downloaded_date:
            latest_downloaded_date = series_latest

    if latest_downloaded_date:
        print(f"Latest downloaded price date: {latest_downloaded_date}")
    
    if prices_data:
        print(f"\nInserting {len(prices_data)} assets into database...\n")
        total, failed_tickers = insert_prices(prices_data)
        print(f"\nCompleted! {len(prices_data)} assets with {total:,} total records")
        if failed_tickers:
            print(f"Tickers with insert failures: {failed_tickers}")
        if total == 0:
            raise SystemExit("Price ingestion inserted 0 records; failing job.")
    else:
        print("No price data downloaded")
