"""
Asset Expansion Script - Add Crypto, Commodities, and More Bonds/ETFs
This script expands the portfolio universe from 986 to 1,200+ securities
"""

import psycopg2
from psycopg2.extras import execute_batch
import logging
from datetime import datetime
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

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = os.getenv('DB_NAME', 'portfolio_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


class AssetExpander:
    """Expand portfolio with crypto, commodities, and more bonds/ETFs"""
    
    def __init__(self):
        """Initialize database connection"""
        try:
            self.conn = psycopg2.connect(DB_URL)
            logger.info("✅ Database connection established")
        except Exception as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            raise

    def add_assets(self, assets, asset_class):
        """Add multiple assets to database"""
        try:
            cur = self.conn.cursor()
            
            sql = """
            INSERT INTO stocks 
            (ticker, name, exchange, sector, asset_class, 
             pe_ratio, roe, eps_growth, dividend_yield, 
             debt_to_equity, beta, market_cap, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (ticker) DO UPDATE SET
                name = EXCLUDED.name,
                asset_class = EXCLUDED.asset_class,
                updated_at = NOW()
            """
            
            rows = []
            for asset in assets:
                rows.append((
                    asset['ticker'].upper(),
                    asset['name'],
                    asset.get('exchange', 'Unknown'),
                    asset.get('sector', 'N/A'),
                    asset_class,
                    asset.get('pe_ratio'),
                    asset.get('roe'),
                    asset.get('eps_growth'),
                    asset.get('dividend_yield'),
                    asset.get('debt_to_equity'),
                    asset.get('beta'),
                    asset.get('market_cap')
                ))
            
            execute_batch(cur, sql, rows)
            self.conn.commit()
            logger.info(f"✅ Added {len(assets)} {asset_class} assets")
            return len(assets)
            
        except Exception as e:
            logger.error(f"❌ Error adding assets: {e}")
            self.conn.rollback()
            return 0

    def add_crypto(self):
        """Add cryptocurrency assets"""
        crypto_assets = [
            # Large Cap
            {'ticker': 'BTC', 'name': 'Bitcoin', 'exchange': 'CRYPTO', 'sector': 'Digital Assets', 'beta': 2.5},
            {'ticker': 'ETH', 'name': 'Ethereum', 'exchange': 'CRYPTO', 'sector': 'Digital Assets', 'beta': 2.8},
            {'ticker': 'BNB', 'name': 'Binance Coin', 'exchange': 'CRYPTO', 'sector': 'Digital Assets', 'beta': 2.4},
            {'ticker': 'SOL', 'name': 'Solana', 'exchange': 'CRYPTO', 'sector': 'Digital Assets', 'beta': 2.9},
            {'ticker': 'ADA', 'name': 'Cardano', 'exchange': 'CRYPTO', 'sector': 'Digital Assets', 'beta': 2.6},
            
            # Layer 2 & Scaling
            {'ticker': 'MATIC', 'name': 'Polygon', 'exchange': 'CRYPTO', 'sector': 'Layer 2', 'beta': 3.0},
            {'ticker': 'ARB', 'name': 'Arbitrum', 'exchange': 'CRYPTO', 'sector': 'Layer 2', 'beta': 3.1},
            {'ticker': 'OP', 'name': 'Optimism', 'exchange': 'CRYPTO', 'sector': 'Layer 2', 'beta': 3.0},
            
            # DeFi
            {'ticker': 'UNI', 'name': 'Uniswap', 'exchange': 'CRYPTO', 'sector': 'DeFi', 'beta': 2.7},
            {'ticker': 'AAVE', 'name': 'Aave', 'exchange': 'CRYPTO', 'sector': 'DeFi', 'beta': 2.8},
            {'ticker': 'LINK', 'name': 'Chainlink', 'exchange': 'CRYPTO', 'sector': 'Infrastructure', 'beta': 2.6},
            {'ticker': 'SUSHI', 'name': 'SushiSwap', 'exchange': 'CRYPTO', 'sector': 'DeFi', 'beta': 2.9},
            {'ticker': 'LIDO', 'name': 'Lido DAO', 'exchange': 'CRYPTO', 'sector': 'DeFi', 'beta': 2.7},
            {'ticker': 'CURVE', 'name': 'Curve DAO', 'exchange': 'CRYPTO', 'sector': 'DeFi', 'beta': 2.8},
            
            # Infrastructure
            {'ticker': 'ATOM', 'name': 'Cosmos', 'exchange': 'CRYPTO', 'sector': 'Infrastructure', 'beta': 2.5},
            {'ticker': 'DOT', 'name': 'Polkadot', 'exchange': 'CRYPTO', 'sector': 'Infrastructure', 'beta': 2.4},
            {'ticker': 'AVAX', 'name': 'Avalanche', 'exchange': 'CRYPTO', 'sector': 'Infrastructure', 'beta': 3.0},
            
            # Staking & Consensus
            {'ticker': 'ETH2', 'name': 'Ethereum 2.0', 'exchange': 'CRYPTO', 'sector': 'Staking', 'beta': 2.8},
            {'ticker': 'LST', 'name': 'Liquid Staking', 'exchange': 'CRYPTO', 'sector': 'Staking', 'beta': 2.7},
            
            # Payment & Utility
            {'ticker': 'XRP', 'name': 'Ripple XRP', 'exchange': 'CRYPTO', 'sector': 'Payment', 'beta': 2.2},
            {'ticker': 'LTC', 'name': 'Litecoin', 'exchange': 'CRYPTO', 'sector': 'Payment', 'beta': 2.3},
            {'ticker': 'DOGE', 'name': 'Dogecoin', 'exchange': 'CRYPTO', 'sector': 'Payment', 'beta': 2.5},
        ]
        
        logger.info(f"Adding {len(crypto_assets)} cryptocurrency assets...")
        return self.add_assets(crypto_assets, 'crypto')

    def add_commodities(self):
        """Add commodity ETFs"""
        commodity_etfs = [
            # Precious Metals
            {'ticker': 'GLD', 'name': 'SPDR Gold Shares', 'exchange': 'NYQ', 'sector': 'Precious Metals'},
            {'ticker': 'SLV', 'name': 'iShares Silver Trust', 'exchange': 'NMS', 'sector': 'Precious Metals'},
            {'ticker': 'PALL', 'name': 'Aberdeen Palladium Shares', 'exchange': 'NMS', 'sector': 'Precious Metals'},
            {'ticker': 'UUP', 'name': 'Invesco DB USD Index', 'exchange': 'NMS', 'sector': 'Commodities'},
            
            # Energy
            {'ticker': 'USO', 'name': 'United States Oil Fund', 'exchange': 'NYQ', 'sector': 'Energy'},
            {'ticker': 'UNG', 'name': 'United States Natural Gas Fund', 'exchange': 'NYQ', 'sector': 'Energy'},
            {'ticker': 'BNO', 'name': 'Brent Oil ETN', 'exchange': 'NMS', 'sector': 'Energy'},
            {'ticker': 'DBC', 'name': 'Commodities Index ETF', 'exchange': 'NMS', 'sector': 'Commodities'},
            
            # Agriculture
            {'ticker': 'DBA', 'name': 'Agriculture ETF', 'exchange': 'NMS', 'sector': 'Agriculture'},
            {'ticker': 'CORN', 'name': 'Teucrium Corn Fund', 'exchange': 'NMS', 'sector': 'Agriculture'},
            {'ticker': 'SOYB', 'name': 'Teucrium Soybean Fund', 'exchange': 'NMS', 'sector': 'Agriculture'},
            {'ticker': 'WEAT', 'name': 'Teucrium Wheat Fund', 'exchange': 'NMS', 'sector': 'Agriculture'},
            
            # Broad Commodities
            {'ticker': 'GSG', 'name': 'iShares S&P GSCI Commodity', 'exchange': 'NMS', 'sector': 'Commodities'},
            {'ticker': 'PDBC', 'name': 'Invesco Commodity Index', 'exchange': 'NMS', 'sector': 'Commodities'},
        ]
        
        logger.info(f"Adding {len(commodity_etfs)} commodity ETFs...")
        return self.add_assets(commodity_etfs, 'commodity')

    def add_additional_etfs(self):
        """Add more sector and diversified ETFs"""
        etfs = [
            # Sector ETFs
            {'ticker': 'XLF', 'name': 'Financial Select Sector SPDR', 'exchange': 'NYQ', 'sector': 'Financials'},
            {'ticker': 'XLE', 'name': 'Energy Select Sector SPDR', 'exchange': 'NYQ', 'sector': 'Energy'},
            {'ticker': 'XLV', 'name': 'Healthcare Select Sector SPDR', 'exchange': 'NYQ', 'sector': 'Healthcare'},
            {'ticker': 'XLK', 'name': 'Technology Select Sector SPDR', 'exchange': 'NYQ', 'sector': 'Technology'},
            {'ticker': 'XLI', 'name': 'Industrial Select Sector SPDR', 'exchange': 'NYQ', 'sector': 'Industrials'},
            {'ticker': 'XLY', 'name': 'Consumer Discretionary SPDR', 'exchange': 'NYQ', 'sector': 'Consumer Cyclical'},
            {'ticker': 'XLP', 'name': 'Consumer Staples SPDR', 'exchange': 'NYQ', 'sector': 'Consumer Defensive'},
            {'ticker': 'XLRE', 'name': 'Real Estate SPDR', 'exchange': 'NYQ', 'sector': 'Real Estate'},
            {'ticker': 'XLU', 'name': 'Utilities SPDR', 'exchange': 'NYQ', 'sector': 'Utilities'},
            {'ticker': 'XLCM', 'name': 'Communication Services SPDR', 'exchange': 'NYQ', 'sector': 'Communication'},
            
            # International & Emerging Markets
            {'ticker': 'VEA', 'name': 'Vanguard FTSE Developed Markets', 'exchange': 'NMS', 'sector': 'International'},
            {'ticker': 'VWO', 'name': 'Vanguard FTSE Emerging Markets', 'exchange': 'NMS', 'sector': 'Emerging Markets'},
            {'ticker': 'EFA', 'name': 'iShares MSCI EAFE ETF', 'exchange': 'NMS', 'sector': 'International'},
            {'ticker': 'EEM', 'name': 'iShares MSCI Emerging Markets', 'exchange': 'NMS', 'sector': 'Emerging Markets'},
            
            # Dividend & Income
            {'ticker': 'VYM', 'name': 'Vanguard High Dividend Yield ETF', 'exchange': 'NMS', 'sector': 'Dividend'},
            {'ticker': 'SCHD', 'name': 'Schwab US Dividend Equity ETF', 'exchange': 'NMS', 'sector': 'Dividend'},
            {'ticker': 'SDY', 'name': 'SPDR S&P Dividend ETF', 'exchange': 'NYQ', 'sector': 'Dividend'},
            {'ticker': 'DGRO', 'name': 'iShares Core Dividend Growth ETF', 'exchange': 'NMS', 'sector': 'Dividend'},
            
            # Value & Growth
            {'ticker': 'VTV', 'name': 'Vanguard Value ETF', 'exchange': 'NMS', 'sector': 'Value'},
            {'ticker': 'VUG', 'name': 'Vanguard Growth ETF', 'exchange': 'NMS', 'sector': 'Growth'},
            {'ticker': 'IVE', 'name': 'iShares S&P 500 Value ETF', 'exchange': 'NMS', 'sector': 'Value'},
            {'ticker': 'IVW', 'name': 'iShares S&P 500 Growth ETF', 'exchange': 'NMS', 'sector': 'Growth'},
            
            # Size-Based
            {'ticker': 'VB', 'name': 'Vanguard Small-Cap ETF', 'exchange': 'NMS', 'sector': 'Small Cap'},
            {'ticker': 'VTV', 'name': 'Vanguard Mid-Cap ETF', 'exchange': 'NMS', 'sector': 'Mid Cap'},
            
            # Fixed Income - Treasury Ladder
            {'ticker': 'VGSH', 'name': 'Vanguard Short-Term Treasury ETF', 'exchange': 'NMS', 'sector': 'Treasuries'},
            {'ticker': 'VGIT', 'name': 'Vanguard Intermediate-Term Treasury', 'exchange': 'NMS', 'sector': 'Treasuries'},
            {'ticker': 'VGLT', 'name': 'Vanguard Long-Term Treasury ETF', 'exchange': 'NMS', 'sector': 'Treasuries'},
            
            # Corporate Bonds
            {'ticker': 'LQD', 'name': 'iShares Investment Grade Corporate', 'exchange': 'NMS', 'sector': 'Corporate Bonds'},
            {'ticker': 'VCIT', 'name': 'Vanguard Intermediate Corporate', 'exchange': 'NMS', 'sector': 'Corporate Bonds'},
            {'ticker': 'VCLT', 'name': 'Vanguard Long-Term Corporate', 'exchange': 'NMS', 'sector': 'Corporate Bonds'},
            
            # High Yield Bonds
            {'ticker': 'HYG', 'name': 'iShares High Yield Corporate Bond', 'exchange': 'NMS', 'sector': 'High Yield'},
            {'ticker': 'VWEHX', 'name': 'Vanguard High-Yield', 'exchange': 'NMS', 'sector': 'High Yield'},
        ]
        
        logger.info(f"Adding {len(etfs)} additional ETFs...")
        return self.add_assets(etfs, 'etf')

    def add_additional_bonds(self):
        """Add more bond options"""
        bonds = [
            # Municipal Bonds
            {'ticker': 'MUB', 'name': 'iShares National Muni Bond ETF', 'exchange': 'NMS', 'sector': 'Municipal'},
            {'ticker': 'VWBMX', 'name': 'Vanguard Municipal Bond Fund', 'exchange': 'NMS', 'sector': 'Municipal'},
            
            # International Bonds
            {'ticker': 'BNDX', 'name': 'Vanguard International Bond ETF', 'exchange': 'NMS', 'sector': 'International'},
            {'ticker': 'IBOXX', 'name': 'iShares Emerging Market Bond ETF', 'exchange': 'NMS', 'sector': 'Emerging Market'},
            
            # TIPS (Inflation Protected)
            {'ticker': 'TIPS', 'name': 'iShares TIPS Bond ETF', 'exchange': 'NMS', 'sector': 'TIPS'},
            {'ticker': 'VTIP', 'name': 'Vanguard Short-Term TIPS', 'exchange': 'NMS', 'sector': 'TIPS'},
            
            # Floating Rate
            {'ticker': 'FLOT', 'name': 'iShares Floating Rate Bond ETF', 'exchange': 'NMS', 'sector': 'Floating Rate'},
            {'ticker': 'VFLOAT', 'name': 'Vanguard Floating Rate Bond ETF', 'exchange': 'NMS', 'sector': 'Floating Rate'},
        ]
        
        logger.info(f"Adding {len(bonds)} bonds...")
        return self.add_assets(bonds, 'bond')

    def verify_insertion(self):
        """Verify assets were added"""
        try:
            cur = self.conn.cursor()
            
            # Count by asset class
            cur.execute("""
                SELECT asset_class, COUNT(*) as count 
                FROM stocks 
                GROUP BY asset_class
                ORDER BY asset_class
            """)
            
            results = cur.fetchall()
            
            logger.info("=" * 60)
            logger.info("Asset Distribution:")
            logger.info("=" * 60)
            total = 0
            for asset_class, count in results:
                logger.info(f"  {asset_class or 'NULL'}: {count}")
                total += count
            
            logger.info("=" * 60)
            logger.info(f"Total Securities: {total}")
            logger.info("=" * 60)
            
            cur.close()
            
        except Exception as e:
            logger.error(f"Error verifying insertion: {e}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


def main():
    """Main execution"""
    expander = None
    try:
        logger.info("=" * 60)
        logger.info("Starting Asset Expansion")
        logger.info("=" * 60)
        
        expander = AssetExpander()
        
        # Add all new assets
        total_added = 0
        total_added += expander.add_crypto()
        total_added += expander.add_commodities()
        total_added += expander.add_additional_etfs()
        total_added += expander.add_additional_bonds()
        
        logger.info(f"\n✅ Successfully added {total_added} new assets!")
        
        # Verify
        expander.verify_insertion()
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
    finally:
        if expander:
            expander.close()


if __name__ == "__main__":
    main()
