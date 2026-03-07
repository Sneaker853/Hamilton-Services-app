"""
Complete Stock Fundamentals Ingestion Script
Fetches all stock data from Yahoo Finance and populates PostgreSQL database
Includes: revenue, net_income, operating_margin, current_ratio, market_cap
"""

import yfinance as yf
import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
import logging
from datetime import datetime
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration from environment variables
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = os.getenv('DB_NAME', 'portfolio_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

class StockFundamentalsIngester:
    def __init__(self):
        """Initialize database connection"""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            logger.info("✅ Database connection established")
        except Exception as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            raise

    def ensure_columns_exist(self):
        """Add new columns to stocks table if they don't exist"""
        try:
            cur = self.conn.cursor()
            
            # SQL to add columns if they don't exist
            sql = """
            ALTER TABLE stocks ADD COLUMN IF NOT EXISTS revenue DECIMAL(15,2);
            ALTER TABLE stocks ADD COLUMN IF NOT EXISTS net_income DECIMAL(15,2);
            ALTER TABLE stocks ADD COLUMN IF NOT EXISTS operating_margin DECIMAL(5,2);
            ALTER TABLE stocks ADD COLUMN IF NOT EXISTS current_ratio DECIMAL(5,2);
            ALTER TABLE stocks ADD COLUMN IF NOT EXISTS market_cap DECIMAL(15,2);
            """
            
            for statement in sql.strip().split(';'):
                if statement.strip():
                    cur.execute(statement)
            
            self.conn.commit()
            logger.info("✅ Database columns verified/created")
        except Exception as e:
            logger.error(f"❌ Error ensuring columns exist: {e}")
            self.conn.rollback()
            raise

    def fetch_stock_fundamentals(self, ticker):
        """
        Fetch comprehensive financial data from Yahoo Finance
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            dict: Stock fundamentals
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            fundamentals = {
                'ticker': ticker.upper(),
                'name': info.get('longName', ticker),
                'exchange': info.get('exchange', 'UNKNOWN'),
                'sector': info.get('sector', 'Unknown'),
                
                # Existing fields
                'pe_ratio': info.get('trailingPE'),
                'roe': info.get('returnOnEquity'),
                'eps_growth': info.get('earningsGrowth'),
                'dividend_yield': info.get('dividendYield'),
                'debt_to_equity': info.get('debtToEquity'),
                'beta': info.get('beta'),
                
                # NEW FIELDS
                'revenue': info.get('totalRevenue'),
                'net_income': info.get('netIncomeToCommon'),
                'operating_margin': info.get('operatingMargins'),
                'current_ratio': info.get('currentRatio'),
                'market_cap': info.get('marketCap'),
            }
            
            logger.info(f"✅ Fetched fundamentals for {ticker}")
            return fundamentals
            
        except Exception as e:
            logger.warning(f"⚠️ Error fetching {ticker}: {e}")
            return None

    def insert_or_update_stock(self, fundamentals):
        """
        Insert or update stock fundamentals in database
        
        Args:
            fundamentals: dict with stock data
        """
        if not fundamentals:
            return False
            
        try:
            cur = self.conn.cursor()
            
            # Use ON CONFLICT to update existing stocks
            sql = """
            INSERT INTO stocks 
            (ticker, name, exchange, sector, pe_ratio, roe, eps_growth, 
             dividend_yield, debt_to_equity, beta, revenue, net_income, 
             operating_margin, current_ratio, market_cap, updated_at)
            VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (ticker) DO UPDATE SET
                name = EXCLUDED.name,
                exchange = EXCLUDED.exchange,
                sector = EXCLUDED.sector,
                pe_ratio = EXCLUDED.pe_ratio,
                roe = EXCLUDED.roe,
                eps_growth = EXCLUDED.eps_growth,
                dividend_yield = EXCLUDED.dividend_yield,
                debt_to_equity = EXCLUDED.debt_to_equity,
                beta = EXCLUDED.beta,
                revenue = EXCLUDED.revenue,
                net_income = EXCLUDED.net_income,
                operating_margin = EXCLUDED.operating_margin,
                current_ratio = EXCLUDED.current_ratio,
                market_cap = EXCLUDED.market_cap,
                updated_at = NOW()
            """
            
            cur.execute(sql, (
                fundamentals['ticker'],
                fundamentals['name'],
                fundamentals['exchange'],
                fundamentals['sector'],
                fundamentals['pe_ratio'],
                fundamentals['roe'],
                fundamentals['eps_growth'],
                fundamentals['dividend_yield'],
                fundamentals['debt_to_equity'],
                fundamentals['beta'],
                fundamentals['revenue'],
                fundamentals['net_income'],
                fundamentals['operating_margin'],
                fundamentals['current_ratio'],
                fundamentals['market_cap']
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inserting {fundamentals['ticker']}: {e}")
            self.conn.rollback()
            return False

    def get_all_tickers(self):
        """Get list of all stock tickers from database"""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT DISTINCT ticker FROM stocks ORDER BY ticker")
            tickers = [row[0] for row in cur.fetchall()]
            logger.info(f"✅ Found {len(tickers)} stocks to update")
            return tickers
        except Exception as e:
            logger.error(f"❌ Error getting tickers: {e}")
            return []

    def ingest_all_stocks(self, test_mode=False):
        """
        Ingest fundamentals for all stocks
        
        Args:
            test_mode: If True, only process first 5 stocks for testing
        """
        logger.info("=" * 60)
        logger.info("🚀 Starting Stock Fundamentals Ingestion")
        logger.info("=" * 60)
        
        # Ensure columns exist
        self.ensure_columns_exist()
        
        # Get all tickers
        tickers = self.get_all_tickers()
        
        if test_mode:
            tickers = tickers[:5]
            logger.info(f"📋 TEST MODE: Processing first 5 stocks")
        
        if not tickers:
            logger.error("❌ No stocks found in database")
            return
        
        successful = 0
        failed = 0
        
        for idx, ticker in enumerate(tickers, 1):
            try:
                logger.info(f"[{idx}/{len(tickers)}] Processing {ticker}...")
                
                # Fetch data from Yahoo Finance
                fundamentals = self.fetch_stock_fundamentals(ticker)
                
                if fundamentals:
                    # Insert into database
                    if self.insert_or_update_stock(fundamentals):
                        successful += 1
                    else:
                        failed += 1
                else:
                    failed += 1
                
                # Rate limiting - Yahoo Finance has limits
                if idx % 10 == 0:
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Error processing {ticker}: {e}")
                failed += 1
                continue
        
        logger.info("=" * 60)
        logger.info(f"✅ Ingestion Complete!")
        logger.info(f"   Successful: {successful}")
        logger.info(f"   Failed: {failed}")
        logger.info(f"   Total: {len(tickers)}")
        logger.info("=" * 60)

    def verify_data(self):
        """Verify that data was properly ingested"""
        try:
            cur = self.conn.cursor()
            
            # Count stocks with new fields populated
            sql = """
            SELECT 
                COUNT(*) as total_stocks,
                COUNT(CASE WHEN revenue IS NOT NULL THEN 1 END) as with_revenue,
                COUNT(CASE WHEN net_income IS NOT NULL THEN 1 END) as with_net_income,
                COUNT(CASE WHEN operating_margin IS NOT NULL THEN 1 END) as with_margin,
                COUNT(CASE WHEN current_ratio IS NOT NULL THEN 1 END) as with_ratio,
                COUNT(CASE WHEN market_cap IS NOT NULL THEN 1 END) as with_market_cap
            FROM stocks
            """
            
            cur.execute(sql)
            result = cur.fetchone()
            
            logger.info("=" * 60)
            logger.info("📊 Data Verification Report")
            logger.info("=" * 60)
            logger.info(f"Total Stocks: {result[0]}")
            logger.info(f"With Revenue: {result[1]} ({result[1]/result[0]*100:.1f}%)")
            logger.info(f"With Net Income: {result[2]} ({result[2]/result[0]*100:.1f}%)")
            logger.info(f"With Operating Margin: {result[3]} ({result[3]/result[0]*100:.1f}%)")
            logger.info(f"With Current Ratio: {result[4]} ({result[4]/result[0]*100:.1f}%)")
            logger.info(f"With Market Cap: {result[5]} ({result[5]/result[0]*100:.1f}%)")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error verifying data: {e}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


def main():
    """Main execution"""
    ingester = None
    try:
        ingester = StockFundamentalsIngester()
        
        # Run ingestion (set test_mode=True for first run with just 5 stocks)
        ingester.ingest_all_stocks(test_mode=False)
        
        # Verify results
        ingester.verify_data()
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
    finally:
        if ingester:
            ingester.close()


if __name__ == "__main__":
    main()
