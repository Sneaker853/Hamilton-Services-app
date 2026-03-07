import psycopg2
from datetime import datetime, timedelta
import random
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'portfolio_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

def generate_price_history():
    conn = psycopg2.connect(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    cur = conn.cursor()
    
    cur.execute("SELECT ticker, asset_class FROM stocks WHERE ticker NOT IN (SELECT DISTINCT ticker FROM price_history) ORDER BY ticker")
    new_assets = cur.fetchall()
    print(f"Found {len(new_assets)} assets without price history")
    
    asset_config = {
        'crypto': {'volatility': 0.08},
        'commodity': {'volatility': 0.035},
        'etf': {'volatility': 0.015},
        'bond': {'volatility': 0.008},
        'stock': {'volatility': 0.02}
    }
    
    starting_prices = {
        'BTC': 47000, 'ETH': 1700, 'SOL': 1.5, 'MATIC': 0.35, 'UNI': 22,
        'AAVE': 350, 'LINK': 25, 'SUSHI': 15, 'DOGE': 0.08, 'XRP': 0.65,
        'ADA': 0.38, 'AVAX': 20, 'DOT': 22, 'ATOM': 9, 'FTM': 0.25,
        'OP': 0.5, 'ARB': 0.6, 'NEAR': 4, 'APTOS': 7, 'HBAR': 0.22,
        'GLD': 175, 'USO': 60, 'SLV': 25, 'PALL': 850, 'UUP': 103,
        'UNG': 5, 'DBC': 18, 'CORN': 600, 'WEAT': 700, 'SOYB': 1400,
        'LGUL': 12, 'GSG': 25, 'PDBC': 18, 'CANE': 45,
        'XLF': 35, 'XLI': 85, 'XLV': 125, 'XLY': 75, 'XLK': 180, 'XLRE': 65, 'XLU': 60,
        'SCHD': 70, 'VIG': 150, 'DGRO': 65, 'VXUS': 95, 'IEFA': 70, 'IEMG': 45,
        'SHY': 80, 'IEF': 130, 'TLT': 145, 'VGIT': 82, 'LQD': 125, 'VCIT': 82, 'VCEB': 115,
        'BNDX': 60, 'SCHP': 58, 'MUB': 113, 'FLOT': 50, 'GOVT': 93
    }
    
    target_prices = {
        'BTC': 85000, 'ETH': 3200, 'SOL': 150, 'MATIC': 1.8, 'UNI': 35,
        'AAVE': 800, 'LINK': 45, 'SUSHI': 4, 'DOGE': 0.35, 'XRP': 1.5,
        'ADA': 1.2, 'AVAX': 65, 'DOT': 55, 'ATOM': 18, 'FTM': 1.2,
        'OP': 2.5, 'ARB': 2.2, 'NEAR': 12, 'APTOS': 15, 'HBAR': 0.5,
        'GLD': 195, 'USO': 75, 'SLV': 32, 'PALL': 1100, 'UUP': 103,
        'UNG': 8, 'DBC': 22, 'CORN': 700, 'WEAT': 750, 'SOYB': 1400,
        'LGUL': 14, 'GSG': 28, 'PDBC': 20, 'CANE': 48,
        'XLF': 50, 'XLI': 110, 'XLV': 160, 'XLY': 115, 'XLK': 280, 'XLRE': 85, 'XLU': 75,
        'SCHD': 105, 'VIG': 210, 'DGRO': 95, 'VXUS': 155, 'IEFA': 105, 'IEMG': 75,
        'SHY': 82, 'IEF': 100, 'TLT': 95, 'VGIT': 80, 'LQD': 118, 'VCIT': 88, 'VCEB': 115,
        'BNDX': 75, 'SCHP': 62, 'MUB': 115, 'FLOT': 51, 'GOVT': 95
    }
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=1825)
    
    count = 0
    for ticker, asset_class in new_assets:
        config = asset_config.get(asset_class, {'volatility': 0.015})
        starting_price = starting_prices.get(ticker, 100)
        target_price = target_prices.get(ticker, starting_price * 1.2)
        volatility = config['volatility']
        
        current_price = starting_price
        current_date = start_date
        total_days = (end_date - start_date).days
        price_ratio = target_price / starting_price
        log_return = np.log(price_ratio) / total_days
        
        batch = []
        while current_date <= end_date:
            drift = log_return
            noise = np.random.normal(0, volatility / np.sqrt(252))
            daily_return = drift + noise
            new_price = current_price * np.exp(daily_return)
            new_price = max(new_price, current_price * 0.5)
            
            open_price = current_price
            close_price = new_price
            high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, volatility/3)))
            low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, volatility/3)))
            
            if asset_class == 'crypto':
                volume = int(random.randint(1000000, 10000000))
            elif asset_class == 'commodity':
                volume = int(random.randint(500000, 5000000))
            else:
                volume = int(random.randint(1000000, 50000000))
            
            batch.append((ticker, current_date, float(round(open_price, 2)), float(round(high_price, 2)), float(round(low_price, 2)), float(round(close_price, 2)), int(volume)))
            
            if len(batch) >= 1000:
                cur.executemany("INSERT INTO price_history (ticker, date, open, high, low, close, volume) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (ticker, date) DO NOTHING", batch)
                conn.commit()
                batch = []
            
            current_price = close_price
            current_date += timedelta(days=1)
        
        if batch:
            cur.executemany("INSERT INTO price_history (ticker, date, open, high, low, close, volume) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (ticker, date) DO NOTHING", batch)
            conn.commit()
        
        count += 1
        if count % 10 == 0:
            print(f"Generated price history for {count} assets...")
    
    cur.close()
    conn.close()
    print(f"Successfully generated price history for {len(new_assets)} new assets")

if __name__ == "__main__":
    generate_price_history()
