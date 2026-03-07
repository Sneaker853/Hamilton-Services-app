"""
Security Screener - Filter and score stocks based on persona criteria
Retrieves stocks from database and applies fundamental analysis scoring
"""

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from typing import Dict, List, Optional
from config_manager import get_config

logger = logging.getLogger(__name__)


class SecurityScreener:
    """Screen and score securities based on persona criteria."""
    
    def __init__(self, db_url: str, config=None):
        """
        Initialize screener with database connection.
        
        Args:
            db_url: PostgreSQL connection URL
            config: Optional ConfigManager instance (for flexibility)
        """
        self.db_url = db_url
        self.config = config or get_config()
    
    def _normalize_fundamental(self, value, metric_config: Dict, is_percentile=False):
        """
        Normalize a fundamental metric to 0-100 score.
        
        Args:
            value: The raw value to normalize
            metric_config: Config dict with 'lower_is_better' and 'outlier_threshold'
            is_percentile: If True, treat as percentile already (0-100)
            
        Returns:
            Score 0-100, or None if invalid
        """
        if value is None or np.isnan(value):
            return None
        
        if is_percentile:
            return max(0, min(100, value))
        
        lower_is_better = metric_config.get('lower_is_better', False)
        outlier_threshold = metric_config.get('outlier_threshold', 100)
        
        # Cap outliers
        if abs(value) > outlier_threshold:
            return None
        
        # Normalize to 0-100
        if lower_is_better:
            # For metrics where lower is better (P/E, debt), invert
            # Assume typical range 0-200 for P/E
            score = max(0, min(100, 100 - (value * 50)))
        else:
            # For metrics where higher is better (ROE, EPS growth)
            # Assume typical range 0-200 for percentage metrics
            score = max(0, min(100, value * 50))
        
        return score
    
    def _calculate_stock_scores(self, stocks_df: pd.DataFrame, persona_name: str) -> pd.DataFrame:
        """
        Calculate component scores (value, quality, growth, momentum) for stocks.
        
        Args:
            stocks_df: DataFrame with stock fundamentals
            persona_name: Name of persona
            
        Returns:
            DataFrame with added score columns
        """
        stocks_df = stocks_df.copy()
        fundamentals_config = self.config.get_fundamentals_config()
        
        # VALUE SCORE: Low P/E ratio
        stocks_df['value_score'] = stocks_df['pe_ratio'].apply(
            lambda x: self._normalize_fundamental(x, fundamentals_config['pe_ratio'])
        )
        
        # QUALITY SCORE: High ROE, Low Debt-to-Equity, High Current Ratio
        stocks_df['quality_score_roe'] = stocks_df['roe'].apply(
            lambda x: self._normalize_fundamental(x, fundamentals_config['roe'])
        )
        stocks_df['quality_score_debt'] = stocks_df['debt_to_equity'].apply(
            lambda x: self._normalize_fundamental(x, fundamentals_config['debt_to_equity'])
        )
        stocks_df['quality_score_current'] = stocks_df.get('current_ratio', pd.Series()).apply(
            lambda x: max(0, min(100, (x - 0.5) * 30)) if pd.notna(x) else None
        )
        
        # Average quality scores (use only non-null values)
        quality_cols = ['quality_score_roe', 'quality_score_debt', 'quality_score_current']
        stocks_df['quality_score'] = stocks_df[quality_cols].mean(axis=1)
        
        # GROWTH SCORE: EPS growth, revenue growth
        stocks_df['growth_score'] = stocks_df['eps_growth'].apply(
            lambda x: self._normalize_fundamental(x, fundamentals_config['eps_growth'])
        )
        
        # MOMENTUM SCORE: Dividend yield proxy for now (would use price momentum in real implementation)
        stocks_df['momentum_score'] = stocks_df['dividend_yield'].apply(
            lambda x: self._normalize_fundamental(x, fundamentals_config['dividend_yield'])
        )
        
        # Replace NaN scores with median for that score type
        for score_col in ['value_score', 'quality_score', 'growth_score', 'momentum_score']:
            median = stocks_df[score_col].median()
            if pd.isna(median):
                median = 50
            stocks_df.loc[:, score_col] = stocks_df[score_col].fillna(median)
        
        # Calculate TOTAL SCORE based on persona weights
        persona = self.config.get_persona(persona_name)
        scoring_weights = persona.get('scoring_weights', self.config.get_scoring_weights())
        
        # Normalize expected_return if present or set default
        if 'expected_return' in stocks_df.columns:
            stocks_df['expected_return'] = pd.to_numeric(stocks_df['expected_return'], errors='coerce').fillna(0.08)
        else:
            stocks_df['expected_return'] = 0.08

        # Convert expected returns (decimal annual) to a 0-100 score so it is comparable
        # to other component scores in total_score aggregation.
        er_pct = stocks_df['expected_return'] * 100.0
        stocks_df['expected_return_score'] = ((er_pct + 5.0) / 25.0 * 100.0).clip(0, 100)

        stocks_df['total_score'] = (
            stocks_df.get('value_score', 0) * scoring_weights.get('value', 0.25) +
            stocks_df.get('quality_score', 0) * scoring_weights.get('quality', 0.30) +
            stocks_df.get('growth_score', 0) * scoring_weights.get('growth', 0.25) +
            stocks_df.get('momentum_score', 0) * scoring_weights.get('momentum', 0.10) +
            stocks_df.get('expected_return_score', 50) * scoring_weights.get('expected_return', 0)
        )

        return stocks_df
    
    def get_stocks_for_persona(self, persona_name: str, 
                               exchanges: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Get screened stocks for a persona.
        
        Args:
            persona_name: Name of persona from config
            exchanges: Optional list of exchange codes to filter (e.g., ['NYSE', 'NASDAQ'])
            
        Returns:
            DataFrame with screened stocks, sorted by total_score descending
        """
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get number of stocks to return
            num_stocks = self.config.get_stocks_in_portfolio(persona_name)
            persona = self.config.get_persona(persona_name)
            
            # Build SQL query
            exchange_filter = ""
            exchange_params = []
            if exchanges:
                # Map display names to exchange codes
                exchange_map = {
                    'NYSE': 'NYQ',
                    'NASDAQ': ['NMS', 'NGM', 'NCM'],
                    'NYSE American': 'ASE',
                    'NYSE Arca': 'PCX',
                    'CBOE': 'BTS',
                }
                
                codes = []
                for ex in exchanges:
                    mapped = exchange_map.get(ex, ex)
                    if isinstance(mapped, list):
                        codes.extend(mapped)
                    else:
                        codes.append(mapped)
                
                if codes:
                    placeholders = ','.join(['%s'] * len(codes))
                    exchange_filter = f"AND exchange IN ({placeholders})"
                    exchange_params = codes
            
            # Query to get stocks - exclude stocks with critical missing data
            sql = f"""
                SELECT 
                    s.ticker, s.name, s.exchange, s.sector,
                    s.pe_ratio, s.roe, s.eps_growth, s.dividend_yield,
                    s.debt_to_equity, s.beta, s.market_cap,
                    m.expected_return, m.volatility
                FROM stocks s
                LEFT JOIN asset_metrics m ON m.ticker = s.ticker
                WHERE s.asset_class = 'stock'
                    AND s.pe_ratio IS NOT NULL
                    AND s.roe IS NOT NULL
                    AND s.ticker NOT IN (
                        SELECT ticker FROM stocks 
                        WHERE pe_ratio IS NULL OR roe IS NULL OR eps_growth IS NULL
                    )
                    {exchange_filter}
                ORDER BY market_cap DESC NULLS LAST
                LIMIT {num_stocks * 3}
            """
            
            cur.execute(sql, exchange_params)
            rows = cur.fetchall()
            conn.close()
            
            if not rows:
                logger.warning(f"No stocks found for persona {persona_name}")
                return pd.DataFrame()
            
            df = pd.DataFrame([dict(row) for row in rows])
            
            # Convert numeric columns
            numeric_cols = ['pe_ratio', 'roe', 'eps_growth', 'dividend_yield', 
                           'debt_to_equity', 'beta', 'market_cap',
                           'expected_return', 'volatility']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Calculate scores
            df = self._calculate_stock_scores(df, persona_name)
            
            # Filter by persona constraints if specified
            constraints = persona.get('constraints', {})
            
            # Apply preferred tickers boost (if specified)
            preferred = persona.get('preferred_tickers', [])
            if preferred:
                df['is_preferred'] = df['ticker'].isin(preferred)
                df.loc[df['is_preferred'], 'total_score'] = df.loc[df['is_preferred'], 'total_score'] * 1.1
            
            # Sort by total score and take top N
            df = df.sort_values('total_score', ascending=False).head(num_stocks)
            
            # Add exchange normalisation for display
            exchange_map = {
                'NYQ': 'NYSE',
                'NMS': 'NASDAQ',
                'NGM': 'NASDAQ Capital',
                'YHD': 'Yahoo',
                'NCM': 'NASDAQ',
                'PCX': 'NYSE Arca',
                'ASE': 'NYSE American',
                'BTS': 'CBOE',
                'PNK': 'Pink Sheets',
                'OQB': 'OTC',
            }
            df['exchange'] = df['exchange'].map(lambda x: exchange_map.get(x, x))
            
            logger.info(f"Screened {len(df)} stocks for persona '{persona_name}'")
            return df
            
        except Exception as e:
            logger.error(f"Error screening stocks for persona {persona_name}: {e}")
            return pd.DataFrame()
    
    def get_stocks_by_sector(self, sector: str, limit: int = 50) -> pd.DataFrame:
        """
        Get stocks for a specific sector.
        
        Args:
            sector: Sector name
            limit: Maximum number of stocks to return
            
        Returns:
            DataFrame with stocks from sector
        """
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            sql = """
                SELECT 
                    s.ticker, s.name, s.exchange, s.sector,
                    s.pe_ratio, s.roe, s.eps_growth, s.dividend_yield,
                    s.debt_to_equity, s.beta, s.market_cap,
                    m.expected_return, m.volatility
                FROM stocks s
                LEFT JOIN asset_metrics m ON m.ticker = s.ticker
                WHERE s.sector = %s AND s.asset_class = 'stock'
                ORDER BY market_cap DESC NULLS LAST
                LIMIT %s
            """
            
            cur.execute(sql, (sector, limit))
            rows = cur.fetchall()
            conn.close()
            
            if not rows:
                return pd.DataFrame()
            
            df = pd.DataFrame([dict(row) for row in rows])
            
            # Convert numeric columns
            numeric_cols = ['pe_ratio', 'roe', 'eps_growth', 'dividend_yield', 
                           'debt_to_equity', 'beta', 'market_cap',
                           'expected_return', 'volatility']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting stocks for sector {sector}: {e}")
            return pd.DataFrame()
