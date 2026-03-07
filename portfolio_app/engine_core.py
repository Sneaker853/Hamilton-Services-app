"""
Portfolio builder: Select and weight stocks based on persona and guardrails.
Replaces old mean-variance optimization with rule-based approach.
"""

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
from typing import Dict, List, Tuple
from config_manager import get_config
from screener import SecurityScreener

logger = logging.getLogger(__name__)


class PortfolioBuilder:
    """Build portfolios using screened stocks and guardrails."""
    
    def __init__(self, config_or_db_url, config=None):
        """
        Initialize builder.
        
        Args:
            config_or_db_url: Either PostgreSQL connection URL string or ConfigManager object
            config: Optional ConfigManager when first argument is DB URL
        """
        # Handle both string DB URL and ConfigManager for backwards compatibility
        if isinstance(config_or_db_url, str):
            self.db_url = config_or_db_url
            self.config = config or get_config()
            self.screener = SecurityScreener(config_or_db_url, self.config)
        else:
            # It's a ConfigManager object
            self.config = config_or_db_url
            self.db_url = os.environ.get("DATABASE_URL")
            if not self.db_url:
                raise ValueError("Missing required environment variable: DATABASE_URL")
            self.screener = SecurityScreener(self.db_url, self.config)
        
        # Cache for sector lookups to avoid repeated yfinance calls
        self._sector_cache = {}
    
    def _get_asset_allocation(self, persona_name: str) -> Dict[str, float]:
        """Get asset allocation for persona (stocks, bonds, defensive_etfs)."""
        return self.config.get_asset_allocation(persona_name)
    
    def get_stock_sector(self, ticker: str) -> str:
        """Get sector for a stock from database. Uses cache to avoid repeated queries."""
        if ticker in self._sector_cache:
            return self._sector_cache[ticker]
        
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT sector FROM stocks WHERE ticker = %s", (ticker,))
            row = cur.fetchone()
            conn.close()
            
            sector = row['sector'] if row and row.get('sector') else 'Unknown'
        except Exception as e:
            logger.warning(f"Error fetching sector for {ticker}: {e}")
            sector = 'Unknown'
        
        # Cache the result
        self._sector_cache[ticker] = sector
        return sector
    
    def _equal_weight_with_guardrails(self, stocks_df: pd.DataFrame, 
                                       persona_name: str) -> Dict[str, float]:
        """
        Equal-weight portfolio respecting guardrails.
        
        Args:
            stocks_df: DataFrame with screened stocks
            persona_name: Name of persona
            
        Returns:
            Dict of ticker -> weight
        """
        constraints = self.config.get_persona_constraints(persona_name)
        return self._equal_weight_with_guardrails_custom(stocks_df, persona_name, constraints)
    
    def _score_weighted_with_guardrails(self, stocks_df: pd.DataFrame, 
                                        persona_name: str,
                                        custom_overrides: Dict = None,
                                        weight_by: str = "expected_return") -> Dict[str, float]:
        """
        Score-weighted portfolio respecting guardrails (for growth-focused personas).
        Heavier stocks get higher weights based on their expected return / total score.
        
        Args:
            stocks_df: DataFrame with screened stocks
            persona_name: Name of persona
            custom_overrides: Optional dict of constraint overrides
            
        Returns:
            Dict of ticker -> weight
        """
        constraints = self.config.get_persona_constraints(persona_name)
        
        # Apply custom overrides
        if custom_overrides:
            logger.info(f"Applying custom overrides: {custom_overrides}")
            
            if 'max_weight_per_stock' in custom_overrides:
                constraints['max_weight_per_stock'] = custom_overrides['max_weight_per_stock']
            if 'max_sector_cap' in custom_overrides:
                constraints['max_sector_cap'] = custom_overrides['max_sector_cap']
            
            # Apply stock count constraints: min_stocks and max_stocks
            if 'min_stocks' in custom_overrides or 'max_stocks' in custom_overrides:
                min_s = custom_overrides.get('min_stocks', 5)
                max_s = custom_overrides.get('max_stocks', 50)
                max_s = min(max_s, len(stocks_df))
                logger.info(f"Limiting stocks to max {max_s} (current: {len(stocks_df)})")
                stocks_df = stocks_df.head(max_s)
        
        if stocks_df.empty:
            logger.warning("No stocks remain after applying custom filters")
            return {}
        
        max_weight = constraints['max_weight_per_stock']
        max_sector_cap = constraints['max_sector_cap']
        
        if custom_overrides and 'min_stocks' in custom_overrides:
            min_holdings = custom_overrides['min_stocks']
        else:
            min_holdings = constraints.get('min_holdings', 5)
        
        logger.info(f"Constraints: max_weight={max_weight:.2%}, max_sector_cap={max_sector_cap:.2%}, min_holdings={min_holdings}")
        
        # Use a weighting factor (expected_return or total_score)
        weight_col = weight_by
        if weight_col not in stocks_df.columns:
            if 'expected_return' in stocks_df.columns:
                weight_col = 'expected_return'
            elif 'total_score' in stocks_df.columns:
                weight_col = 'total_score'
            else:
                logger.warning("No usable weight column in dataframe, falling back to equal weight")
                return self._equal_weight_with_guardrails_custom(stocks_df, persona_name, custom_overrides)
        
        # Calculate raw weights based on expected return (exponential boost to differentiate)
        # Higher return = higher weight, but clipped to max_weight constraint
        stocks_df = stocks_df.copy()
        
        # Normalize weighting factor to 0-1 range
        base_series = pd.to_numeric(stocks_df[weight_col], errors='coerce')
        min_val = base_series.min()
        max_val = base_series.max()
        val_range = max_val - min_val

        if not np.isfinite(val_range) or val_range == 0:
            # Fallback to total_score if expected_return has no variation
            if weight_col != 'total_score' and 'total_score' in stocks_df.columns:
                weight_col = 'total_score'
                base_series = pd.to_numeric(stocks_df[weight_col], errors='coerce')
                min_val = base_series.min()
                max_val = base_series.max()
                val_range = max_val - min_val

            if not np.isfinite(val_range) or val_range == 0:
                logger.warning("Weight column has no variation; falling back to equal weight")
                return self._equal_weight_with_guardrails_custom(stocks_df, persona_name, custom_overrides)

        # Weight-based boost to differentiate top performers
        boost = 1.5 if weight_col == 'expected_return' else 1.2
        stocks_df['weight'] = np.exp((base_series - min_val) / val_range * boost)
        
        # Normalize to sum to available weight (before sector constraints)
        total_return_weight = stocks_df['weight'].sum()
        stocks_df['weight'] = stocks_df['weight'] / total_return_weight
        
        if weight_col == 'expected_return':
            logger.info(f"Expected returns range: {min_val:.2%} to {max_val:.2%}")
        else:
            logger.info(f"Weighting by {weight_col} (range: {min_val:.2f} to {max_val:.2f})")
        
        # Show top 10 stocks before sector filtering
        top_10_cols = ['ticker', 'weight']
        if 'expected_return' in stocks_df.columns:
            top_10_cols.insert(1, 'expected_return')
        if 'total_score' in stocks_df.columns and 'total_score' not in top_10_cols:
            top_10_cols.insert(1, 'total_score')
        top_10 = stocks_df.nlargest(10, 'weight')[top_10_cols]
        for idx, row in top_10.iterrows():
            logger.info(f"  {row['ticker']}: {row['expected_return']:.2%} return -> {row['weight']:.2%} weight")
        
        # Apply individual max weight constraint
        stocks_df['weight'] = stocks_df['weight'].clip(upper=max_weight)
        
        # Now apply sector constraints
        tickers = stocks_df['ticker'].tolist()
        weights = {}
        sector_weights = {}
        sector_counts = {}
        skipped_tickers = []
        
        # Create ticker to sector mapping from DataFrame if available
        ticker_to_sector = {}
        if 'sector' in stocks_df.columns:
            ticker_to_sector = dict(zip(stocks_df['ticker'], stocks_df['sector'].fillna('Unknown')))
        
        for idx, row in stocks_df.iterrows():
            ticker = row['ticker']
            target_weight = row['weight']
            sector = ticker_to_sector.get(ticker) or self.get_stock_sector(ticker)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            
            current_sector_weight = sector_weights.get(sector, 0)
            
            if current_sector_weight + target_weight <= max_sector_cap:
                weights[ticker] = target_weight
                sector_weights[sector] = current_sector_weight + target_weight
            else:
                skipped_tickers.append(ticker)
        
        logger.info(f"Sectors in input stocks: {sector_counts}")
        
        if skipped_tickers:
            logger.info(f"Skipped {len(skipped_tickers)} stocks due to sector cap constraints")
        
        # Normalize weights to sum to 1
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {ticker: w / total_weight for ticker, w in weights.items()}
        
        # Calculate final sector weights after normalization
        final_sector_weights = {}
        for ticker, weight in weights.items():
            sector = ticker_to_sector.get(ticker) or self.get_stock_sector(ticker)
            final_sector_weights[sector] = final_sector_weights.get(sector, 0) + weight
        
        logger.info(f"Final portfolio sector weights: {final_sector_weights}")
        logger.info(f"Portfolio built with {len(weights)} holdings (target min: {min_holdings})")
        
        if len(weights) < min_holdings:
            logger.warning(f"Could not meet min_holdings constraint ({min_holdings}). "
                          f"Only {len(weights)} stocks fit constraints. "
                          f"Try relaxing sector_cap or max_weight constraints.")
        
        return weights
    
    def _equal_weight_with_guardrails_custom(self, stocks_df: pd.DataFrame, 
                                              persona_name: str,
                                              custom_overrides: Dict = None) -> Dict[str, float]:
        """
        Equal-weight portfolio respecting guardrails with optional custom overrides.
        
        Args:
            stocks_df: DataFrame with screened stocks
            persona_name: Name of persona
            custom_overrides: Optional dict of constraint overrides
            
        Returns:
            Dict of ticker -> weight
        """
        constraints = self.config.get_persona_constraints(persona_name)
        
        # Apply custom overrides
        if custom_overrides:
            logger.info(f"Applying custom overrides: {custom_overrides}")
            
            if 'max_weight_per_stock' in custom_overrides:
                constraints['max_weight_per_stock'] = custom_overrides['max_weight_per_stock']
            if 'max_sector_cap' in custom_overrides:
                constraints['max_sector_cap'] = custom_overrides['max_sector_cap']
            
            # Apply stock count constraints: min_stocks and max_stocks
            if 'min_stocks' in custom_overrides or 'max_stocks' in custom_overrides:
                min_s = custom_overrides.get('min_stocks', 5)
                max_s = custom_overrides.get('max_stocks', 50)
                # Clamp the dataframe to the requested range
                max_s = min(max_s, len(stocks_df))
                logger.info(f"Limiting stocks to max {max_s} (current: {len(stocks_df)})")
                stocks_df = stocks_df.head(max_s)
        
        if stocks_df.empty:
            logger.warning("No stocks remain after applying custom filters")
            return {}
        
        max_weight = constraints['max_weight_per_stock']
        max_sector_cap = constraints['max_sector_cap']
        
        # Use custom min_stocks if provided, otherwise use config's min_holdings
        if custom_overrides and 'min_stocks' in custom_overrides:
            min_holdings = custom_overrides['min_stocks']
        else:
            min_holdings = constraints.get('min_holdings', 5)
        
        logger.info(f"Constraints: max_weight={max_weight:.2%}, max_sector_cap={max_sector_cap:.2%}, min_holdings={min_holdings}")
        
        tickers = stocks_df['ticker'].tolist()
        n_stocks = len(tickers)
        
        # Start with equal weight
        equal_weight = 1.0 / n_stocks
        
        # If equal weight violates max_weight, reduce to max_weight
        if equal_weight > max_weight:
            # Number of stocks we can actually hold
            actual_n = int(1.0 / max_weight)
            tickers = tickers[:actual_n]
            n_stocks = len(tickers)
            equal_weight = 1.0 / actual_n
            logger.info(f"Max weight constraint limits portfolio to {actual_n} stocks (equal weight would be {1.0/len(stocks_df):.2%})")
        
        # Build portfolio with sector limits
        weights = {}
        sector_weights = {}
        skipped_tickers = []
        sector_counts = {}
        
        # Create ticker to sector mapping from DataFrame if available
        ticker_to_sector = {}
        if 'sector' in stocks_df.columns:
            ticker_to_sector = dict(zip(stocks_df['ticker'], stocks_df['sector'].fillna('Unknown')))
        
        for ticker in tickers:
            sector = ticker_to_sector.get(ticker) or self.get_stock_sector(ticker)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            
            # Check if adding this stock would exceed sector cap
            current_sector_weight = sector_weights.get(sector, 0)
            
            if current_sector_weight + equal_weight <= max_sector_cap:
                weights[ticker] = equal_weight
                sector_weights[sector] = current_sector_weight + equal_weight
            else:
                # Skip this stock (violates sector cap)
                skipped_tickers.append(ticker)
        
        logger.info(f"Sectors in input stocks: {sector_counts}")
        logger.info(f"Sector weights before normalization: {sector_weights}")
        
        if skipped_tickers:
            logger.info(f"Skipped {len(skipped_tickers)} stocks due to sector cap constraints")
        
        # Normalize weights to sum to 1
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {ticker: w / total_weight for ticker, w in weights.items()}
        
        # Calculate final sector weights after normalization
        final_sector_weights = {}
        for ticker, weight in weights.items():
            sector = ticker_to_sector.get(ticker) or self.get_stock_sector(ticker)
            final_sector_weights[sector] = final_sector_weights.get(sector, 0) + weight
        
        logger.info(f"Final portfolio sector weights: {final_sector_weights}")
        logger.info(f"Portfolio built with {len(weights)} holdings (target min: {min_holdings})")
        
        # Check minimum holdings constraint
        if len(weights) < min_holdings:
            logger.warning(f"Could not meet min_holdings constraint ({min_holdings}). "
                          f"Only {len(weights)} stocks fit constraints. "
                          f"Try relaxing sector_cap or max_weight constraints.")
        
        return weights
    
    def _get_historical_volatility(self, tickers: List[str], days: int = 252) -> float:
        """
        Calculate portfolio volatility from historical returns.
        
        Args:
            tickers: List of stock tickers
            days: Number of days of history to use
            
        Returns:
            Annualized volatility as decimal (e.g., 0.15 for 15%)
        """
        try:
            returns = self._get_returns_matrix(tickers=tickers, lookback_days=max(days, 60))

            if returns.empty:
                return 0.15

            available_tickers = [ticker for ticker in tickers if ticker in returns.columns]
            if not available_tickers:
                return 0.15

            cov_matrix = returns[available_tickers].cov(min_periods=20).fillna(0.0).values * 252
            n = len(available_tickers)
            weights = np.array([1.0 / n] * n, dtype=float)
            portfolio_variance = float(weights @ cov_matrix @ weights)

            if not np.isfinite(portfolio_variance) or portfolio_variance <= 0:
                return 0.15

            return float(np.sqrt(portfolio_variance))

        except Exception as e:
            logger.warning(f"Could not calculate volatility: {e}, using default 15%")
            return 0.15

    def _get_returns_matrix(self, tickers: List[str], lookback_days: int = 400) -> pd.DataFrame:
        """Fetch aligned daily return matrix from local price_history table."""
        if not tickers:
            return pd.DataFrame()

        try:
            conn = psycopg2.connect(self.db_url)
            prices = pd.read_sql(
                """
                WITH recent_dates AS (
                    SELECT date
                    FROM price_history
                    WHERE ticker = ANY(%s)
                    GROUP BY date
                    ORDER BY date DESC
                    LIMIT %s
                )
                SELECT date, ticker, close
                FROM price_history
                WHERE ticker = ANY(%s)
                  AND date IN (SELECT date FROM recent_dates)
                ORDER BY date ASC
                """,
                conn,
                params=(tickers, lookback_days, tickers),
                parse_dates=["date"],
            )
            conn.close()

            if prices.empty:
                return pd.DataFrame()

            price_matrix = prices.pivot(index="date", columns="ticker", values="close").sort_index()
            returns = price_matrix.pct_change().dropna(how="all")
            return returns
        except Exception as e:
            logger.warning(f"Failed to fetch return matrix: {e}")
            return pd.DataFrame()

    def _calculate_portfolio_volatility(self, holdings_df: pd.DataFrame, lookback_days: int = 400) -> float:
        """Estimate portfolio volatility using empirical covariance from local history."""
        if holdings_df.empty:
            return 0.01

        grouped = holdings_df.groupby("ticker", as_index=True).agg({"weight": "sum", "volatility": "first"})
        grouped = grouped[grouped["weight"] > 0]
        if grouped.empty:
            return 0.01

        weights = grouped["weight"].astype(float)
        total_weight = float(weights.sum())
        if total_weight <= 0:
            return 0.01
        weights = weights / total_weight

        tickers = list(weights.index)
        returns = self._get_returns_matrix(tickers=tickers, lookback_days=lookback_days)

        cov_df = None
        if not returns.empty and returns.shape[0] >= 20:
            cov_df = returns.cov(min_periods=20) * 252

        all_tickers = tickers
        full_cov = pd.DataFrame(0.0, index=all_tickers, columns=all_tickers)

        if cov_df is not None and not cov_df.empty:
            common = [t for t in all_tickers if t in cov_df.index and t in cov_df.columns]
            if common:
                full_cov.loc[common, common] = cov_df.loc[common, common].fillna(0.0)

        fallback_vols = pd.to_numeric(grouped["volatility"], errors="coerce")
        for ticker in all_tickers:
            current_var = full_cov.at[ticker, ticker]
            if not np.isfinite(current_var) or current_var <= 0:
                vol = fallback_vols.get(ticker)
                if pd.notna(vol) and np.isfinite(vol) and vol > 0:
                    full_cov.at[ticker, ticker] = float(vol) ** 2

        cov_matrix = full_cov.fillna(0.0).values.astype(float)
        cov_matrix = (cov_matrix + cov_matrix.T) / 2.0

        w = weights.reindex(all_tickers).fillna(0.0).values.astype(float)
        portfolio_variance = float(w @ cov_matrix @ w)

        if not np.isfinite(portfolio_variance) or portfolio_variance <= 0:
            fallback_variance = 0.0
            for ticker, weight in weights.items():
                vol = fallback_vols.get(ticker)
                if pd.notna(vol) and np.isfinite(vol) and vol > 0:
                    fallback_variance += (float(weight) * float(vol)) ** 2
            portfolio_variance = fallback_variance

        if not np.isfinite(portfolio_variance) or portfolio_variance <= 0:
            return 0.01

        return max(float(np.sqrt(portfolio_variance)), 0.01)

    def _get_asset_metric_map(self, tickers: List[str]) -> Dict[str, Dict[str, float]]:
        """Fetch expected_return and volatility from DB metrics for provided tickers."""
        if not tickers:
            return {}

        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT s.ticker,
                       m.expected_return,
                       m.volatility
                FROM stocks s
                LEFT JOIN asset_metrics m ON m.ticker = s.ticker
                WHERE s.ticker = ANY(%s)
                """,
                (tickers,),
            )
            rows = cur.fetchall()
            conn.close()

            metrics: Dict[str, Dict[str, float]] = {}
            for row in rows:
                ticker = row.get('ticker')
                if not ticker:
                    continue
                metrics[ticker] = {
                    'expected_return': row.get('expected_return'),
                    'volatility': row.get('volatility'),
                }
            return metrics
        except Exception as e:
            logger.warning(f"Could not load asset metrics for defensive assets: {e}")
            return {}
    
    def build_portfolio(self, persona_name: str, custom_overrides: Dict = None, exchanges: List[str] = None) -> Dict:
        """
        Build a portfolio for a given persona with multiple asset classes.
        
        Args:
            persona_name: Name of persona from config
            custom_overrides: Optional dict of user customizations
            exchanges: Optional list of exchanges to include (e.g., ['NASDAQ', 'TSX', 'NYSE'])
            
        Returns:
            Dict with portfolio data including stocks, bonds, and defensive ETFs
        """
        logger.info(f"Building portfolio for persona: {persona_name}")
        if exchanges:
            logger.info(f"Filtering by exchanges: {exchanges}")
        
        # Get persona info
        persona = self.config.get_persona(persona_name)
        asset_allocation = self._get_asset_allocation(persona_name)
        
        # Get screened stocks (with optional filtering by min_return, min_dividend_yield)
        stocks_df = self.screener.get_stocks_for_persona(persona_name, exchanges=exchanges)

        # Apply sector exclusions if provided
        excluded_sectors = None
        if custom_overrides:
            excluded_sectors = custom_overrides.get('excluded_sectors')

        if excluded_sectors:
            # Sector column should already exist from get_latest_fundamentals, but double-check
            if 'sector' not in stocks_df.columns:
                stocks_df = stocks_df.copy()
                stocks_df['sector'] = stocks_df['ticker'].apply(self.get_stock_sector)
            before_count = len(stocks_df)
            stocks_df = stocks_df[~stocks_df['sector'].isin(excluded_sectors)]
            logger.info(f"Excluded sectors {excluded_sectors}: {before_count} -> {len(stocks_df)} stocks")
        
        if stocks_df.empty:
            logger.warning(f"No stocks returned for persona {persona_name}")
            return None
        
        logger.info(f"Screening returned {len(stocks_df)} stocks")
        
        # Use score-weighted allocation for all personas (expected_return for growth, total_score otherwise)
        if persona_name in ['growth_seeker']:
            logger.info(f"Using score-weighted allocation for {persona_name} (expected_return)")
            weights = self._score_weighted_with_guardrails(
                stocks_df,
                persona_name,
                custom_overrides=custom_overrides,
                weight_by="expected_return"
            )
        else:
            logger.info(f"Using score-weighted allocation for {persona_name} (total_score)")
            weights = self._score_weighted_with_guardrails(
                stocks_df,
                persona_name,
                custom_overrides=custom_overrides,
                weight_by="total_score"
            )
        
        if not weights:
            logger.error("Failed to build portfolio weights")
            return None
        
        # Check if bonds/ETFs should be included (from custom_overrides)
        include_bonds = custom_overrides.get('include_bonds', True) if custom_overrides else True
        include_etfs = custom_overrides.get('include_etfs', True) if custom_overrides else True
        
        # Add sectors to stocks df (should already be present from screener)
        stocks_in_portfolio = set(weights.keys())
        portfolio_stocks = stocks_df[stocks_df['ticker'].isin(stocks_in_portfolio)].copy()
        if 'sector' not in portfolio_stocks.columns:
            portfolio_stocks['sector'] = portfolio_stocks['ticker'].apply(self.get_stock_sector)
        portfolio_stocks['weight'] = portfolio_stocks['ticker'].map(weights)
        
        # Scale stock weights by allocation percentage
        # If bonds/ETFs are excluded, give all weight to stocks
        stock_allocation = asset_allocation.get('stocks', 1.0)
        if not include_bonds:
            stock_allocation += asset_allocation.get('bonds', 0.0)
        if not include_etfs:
            stock_allocation += asset_allocation.get('defensive_etfs', 0.0)
        portfolio_stocks['weight'] = portfolio_stocks['weight'] * stock_allocation
        
        # Add volatility for stocks (use stored metrics when available)
        if 'volatility' in portfolio_stocks.columns:
            portfolio_stocks['volatility'] = pd.to_numeric(portfolio_stocks['volatility'], errors='coerce')

        if 'volatility' not in portfolio_stocks.columns or portfolio_stocks['volatility'].isna().all():
            stock_tickers = list(stocks_in_portfolio)
            stocks_vol = self._get_historical_volatility(stock_tickers)
            portfolio_stocks = portfolio_stocks.assign(volatility=stocks_vol)
        
        # Ensure exchange column exists for display
        if 'exchange' not in portfolio_stocks.columns:
            portfolio_stocks['exchange'] = 'Unknown'
        
        # Get bonds and ETFs from config
        asset_universe = self.config.get_asset_universe()
        bonds_list = asset_universe.get('bonds', [])
        etfs_list = asset_universe.get('defensive_etfs', [])
        
        defensive_tickers = [item.get('ticker') for item in bonds_list + etfs_list if item.get('ticker')]
        defensive_metric_map = self._get_asset_metric_map(defensive_tickers)

        # Create bond allocation
        bonds_data = []
        bond_allocation = asset_allocation.get('bonds', 0.0)
        if bond_allocation > 0 and bonds_list and include_bonds:
            n_bonds = min(3, len(bonds_list))  # Select up to 3 bonds
            bond_weight_each = bond_allocation / n_bonds
            for bond in bonds_list[:n_bonds]:
                metric_row = defensive_metric_map.get(bond['ticker'], {})
                bonds_data.append({
                    'ticker': bond['ticker'],
                    'name': bond['name'],
                    'weight': bond_weight_each,
                    'expected_return': metric_row.get('expected_return') if metric_row.get('expected_return') is not None else bond.get('expected_return', 0.04),
                    'volatility': metric_row.get('volatility') if metric_row.get('volatility') is not None else bond.get('volatility', 0.06),
                    'total_score': 50.0,  # Bonds don't have scores
                    'value_score': 50,
                    'quality_score': 50,
                    'growth_score': 50,
                    'sector': 'Fixed Income',
                    'asset_class': 'bond'
                })
        
        # Create ETF allocation
        etf_data = []
        etf_allocation = asset_allocation.get('defensive_etfs', 0.0)
        if etf_allocation > 0 and etfs_list and include_etfs:
            n_etfs = min(2, len(etfs_list))  # Select up to 2 ETFs
            etf_weight_each = etf_allocation / n_etfs
            for etf in etfs_list[:n_etfs]:
                metric_row = defensive_metric_map.get(etf['ticker'], {})
                etf_data.append({
                    'ticker': etf['ticker'],
                    'name': etf['name'],
                    'weight': etf_weight_each,
                    'expected_return': metric_row.get('expected_return') if metric_row.get('expected_return') is not None else etf.get('expected_return', 0.06),
                    'volatility': metric_row.get('volatility') if metric_row.get('volatility') is not None else etf.get('volatility', 0.12),
                    'total_score': 60.0,  # Defensive ETFs score higher
                    'value_score': 60,
                    'quality_score': 60,
                    'growth_score': 60,
                    'sector': 'Diversified',
                    'asset_class': 'etf'
                })
        
        # Combine all holdings
        portfolio_stocks['asset_class'] = 'stock'
        if 'name' not in portfolio_stocks.columns:
            portfolio_stocks['name'] = portfolio_stocks['ticker']
        
        all_holdings = []
        if not portfolio_stocks.empty:
            # Include exchange column if it exists
            stock_cols = ['ticker', 'weight', 'expected_return', 'total_score',
                         'sector', 'asset_class', 'name', 'volatility']
            if 'exchange' in portfolio_stocks.columns:
                stock_cols.append('exchange')
            all_holdings.append(portfolio_stocks[stock_cols])
        
        if bonds_data:
            all_holdings.append(pd.DataFrame(bonds_data))
        
        if etf_data:
            all_holdings.append(pd.DataFrame(etf_data))
        
        combined_holdings = pd.concat(all_holdings, ignore_index=True) if all_holdings else pd.DataFrame()
        
        if combined_holdings.empty:
            logger.error("No holdings in portfolio")
            return None
        
        # Build all weights dict
        all_weights = {}
        for _, row in combined_holdings.iterrows():
            all_weights[row['ticker']] = row['weight']
        
        # Calculate sector breakdown
        sector_breakdown = {}
        for sector in combined_holdings['sector'].unique():
            sector_weight = combined_holdings[combined_holdings['sector'] == sector]['weight'].sum()
            sector_breakdown[sector] = sector_weight
        
        # Calculate asset class breakdown
        asset_class_breakdown = {}
        for asset_class in combined_holdings['asset_class'].unique():
            class_weight = combined_holdings[combined_holdings['asset_class'] == asset_class]['weight'].sum()
            asset_class_breakdown[asset_class] = class_weight
        
        # Calculate Herfindahl index (concentration measure)
        hhi = sum(w**2 for w in all_weights.values())
        
        # Calculate expected return (weighted average)
        portfolio_return = 0.0
        valid_weights = 0.0
        for ticker, weight in all_weights.items():
            if ticker in combined_holdings['ticker'].values:
                stock_return = combined_holdings[combined_holdings['ticker'] == ticker]['expected_return'].values
                if len(stock_return) > 0 and not np.isnan(stock_return[0]):
                    # Return is already in decimal format (0.08 = 8%)
                    portfolio_return += stock_return[0] * weight
                    valid_weights += weight
        
        # Normalize by actual weights used
        if valid_weights > 0:
            portfolio_return = portfolio_return / valid_weights
        else:
            portfolio_return = 0.06  # Default 6% if all returns are NaN
        
        portfolio_vol = self._calculate_portfolio_volatility(combined_holdings)
        
        result = {
            'persona_name': persona_name,
            'display_name': persona['display_name'],
            'description': persona['description'],
            'weights': all_weights,
            'stocks': combined_holdings.sort_values('total_score', ascending=False),
            'stats': {
                'n_holdings': len(all_weights),
                'herfindahl_index': hhi,
                'max_weight': max(all_weights.values()) if all_weights else 0,
                'min_weight': min(all_weights.values()) if all_weights else 0,
                'sector_breakdown': sector_breakdown,
                'asset_class_breakdown': asset_class_breakdown,
                'expected_return': portfolio_return,
                'volatility': portfolio_vol
            }
        }
        
        logger.info(f"Portfolio built: {len(all_weights)} holdings, HHI={hhi:.4f}, Return={portfolio_return:.2%}, Vol={portfolio_vol:.2%}")
        
        return result
    
    def build_all_personas(self) -> Dict[str, Dict]:
        """
        Build portfolios for all personas.
        
        Returns:
            Dict of persona_name -> portfolio data
        """
        portfolios = {}
        
        for persona_name in self.config.get_persona_names():
            portfolio = self.build_portfolio(persona_name)
            if portfolio:
                portfolios[persona_name] = portfolio
        
        return portfolios


if __name__ == "__main__":
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("Missing required environment variable: DATABASE_URL")
    
    builder = PortfolioBuilder(db_url)
    
    # Test building portfolio for first persona
    persona_name = "balanced"
    portfolio = builder.build_portfolio(persona_name)
    
    if portfolio:
        print(f"\nPortfolio for {portfolio['display_name']}:")
        print(f"Holdings: {portfolio['stats']['n_holdings']}")
        print(f"HHI: {portfolio['stats']['herfindahl_index']:.4f}")
        print("\nSector Breakdown:")
        for sector, weight in portfolio['stats']['sector_breakdown'].items():
            print(f"  {sector}: {weight*100:.2f}%")
        print("\nTop 10 Holdings:")
        print(portfolio['stocks'][['ticker', 'total_score', 'weight']].head(10).to_string())


