"""
Shared financial helpers used by the portfolio router endpoints.

Extracted from routers/portfolio.py to reduce file size and improve
maintainability.  All functions here are pure utilities that operate
on numpy/pandas data — no FastAPI router or endpoint logic.
"""

import json
import logging
import math
import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf, OAS
from fastapi import HTTPException

from db import get_cursor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Covariance & return estimation
# ---------------------------------------------------------------------------

def get_covariance_method() -> str:
    """Read covariance_method from portfolio_app/config.json (cached)."""
    if not hasattr(get_covariance_method, "_cache"):
        try:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "portfolio_app", "config.json"
            )
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            method = cfg.get("estimation", {}).get("covariance_method", "ledoit_wolf")
            if method not in ("sample", "ledoit_wolf", "oas"):
                method = "ledoit_wolf"
            get_covariance_method._cache = method
        except Exception:
            get_covariance_method._cache = "ledoit_wolf"
    return get_covariance_method._cache


def load_mean_returns_and_covariance(
    tickers: List[str],
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Load FF5 expected returns and compute an annualised covariance matrix.

    Returns (aligned_tickers, mean_returns, cov_matrix).
    """
    unique_tickers = list(dict.fromkeys([t for t in tickers if t]))
    if len(unique_tickers) < 1:
        raise HTTPException(status_code=400, detail="No valid tickers provided")

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            "SELECT ticker, expected_return FROM asset_metrics WHERE ticker = ANY(%s)",
            (unique_tickers,),
        )
        metrics_rows = cur.fetchall()
        metrics_df = pd.DataFrame(metrics_rows)

        cur.execute(
            """
            WITH recent_dates AS (
                SELECT date FROM price_history
                WHERE ticker = ANY(%s)
                GROUP BY date ORDER BY date DESC LIMIT 800
            )
            SELECT date, ticker, close
            FROM price_history
            WHERE ticker = ANY(%s) AND date IN (SELECT date FROM recent_dates)
            ORDER BY date ASC
            """,
            (unique_tickers, unique_tickers),
        )
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=400, detail="No price data found for selected tickers")

    prices_df = pd.DataFrame(rows)
    if prices_df.empty:
        raise HTTPException(status_code=400, detail="No price data found for selected tickers")

    prices_pivot = prices_df.pivot(index="date", columns="ticker", values="close")
    # Forward-fill individual stock gaps (max 3 trading days) instead of
    # dropping entire dates — preserves much more history.
    prices_pivot = prices_pivot.ffill(limit=3).dropna(axis=0, how="any")

    if prices_pivot.shape[0] < 30:
        raise HTTPException(status_code=400, detail="Insufficient aligned price history for covariance metrics")

    prices_pivot = prices_pivot.tail(600)
    returns_df = prices_pivot.pct_change().dropna()
    aligned_tickers = list(prices_pivot.columns)

    if returns_df.shape[0] < 20:
        raise HTTPException(status_code=400, detail="Insufficient return data for covariance metrics")

    mean_returns = []
    for ticker in aligned_tickers:
        if not metrics_df.empty and ticker in metrics_df["ticker"].values:
            ff5_return = metrics_df[metrics_df["ticker"] == ticker]["expected_return"].values[0]
            if ff5_return is not None and not np.isnan(ff5_return):
                mean_returns.append(ff5_return)
            else:
                mean_returns.append(returns_df[ticker].mean() * 252)
        else:
            mean_returns.append(returns_df[ticker].mean() * 252)

    mean_returns = np.array(mean_returns, dtype=float)
    mean_returns = np.clip(mean_returns, -0.20, 0.35)

    cov_method = get_covariance_method()
    if cov_method == "ledoit_wolf":
        lw = LedoitWolf().fit(returns_df.values)
        cov_matrix = lw.covariance_ * 252
    elif cov_method == "oas":
        oas = OAS().fit(returns_df.values)
        cov_matrix = oas.covariance_ * 252
    else:
        cov_matrix = returns_df.cov().values * 252
        diag_cov = np.diag(np.diag(cov_matrix))
        shrinkage_delta = 0.20
        cov_matrix = (1.0 - shrinkage_delta) * cov_matrix + shrinkage_delta * diag_cov

    return aligned_tickers, mean_returns, cov_matrix


# ---------------------------------------------------------------------------
# Price matrix & portfolio returns
# ---------------------------------------------------------------------------

def fetch_price_matrix(
    tickers: List[str], days: int
) -> tuple[pd.DataFrame, List[str]]:
    """Fetch a pivot table of close prices and list of missing tickers.

    Returns (prices_pivot, missing_tickers).
    """
    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            WITH latest AS (
                SELECT MAX(date) AS d FROM price_history WHERE ticker = ANY(%s)
            )
            SELECT ph.date, ph.ticker, ph.close
            FROM price_history ph, latest l
            WHERE ph.ticker = ANY(%s)
              AND ph.date >= l.d - %s
              AND ph.date <= l.d
            ORDER BY ph.date ASC
            """,
            (tickers, tickers, days),
        )
        rows = cur.fetchall()

    if not rows:
        return pd.DataFrame(), tickers

    df = pd.DataFrame(rows)
    pivot = df.pivot_table(index="date", columns="ticker", values="close")
    pivot = pivot.sort_index()

    # Forward-fill all gaps: for active tickers this fills short gaps,
    # for delisted tickers their last known price persists (flat return)
    # which avoids survivorship bias by keeping terminal value.
    pivot = pivot.ffill()

    # Only drop rows where ALL tickers are NaN (leading NaN before first data)
    pivot = pivot.dropna(how="all")
    # Drop any tickers that have no data at all
    pivot = pivot.dropna(axis=1, how="all")
    # Fill any remaining leading NaN per ticker with the first available price
    pivot = pivot.bfill().astype(float)

    missing = [t for t in tickers if t not in pivot.columns]
    return pivot, missing


def build_portfolio_returns(
    prices: pd.DataFrame,
    tickers: List[str],
    weights: np.ndarray,
) -> tuple[pd.Series, np.ndarray, List[str], List[str]]:
    """Compute daily portfolio returns from a price pivot table.

    Returns (portfolio_returns, aligned_weights, present_tickers, missing_tickers).
    """
    present = [t for t in tickers if t in prices.columns]
    missing = [t for t in tickers if t not in prices.columns]
    if not present or prices.shape[0] < 3:
        return pd.Series(dtype=float), np.array([]), present, missing

    idx = [tickers.index(t) for t in present]
    w = weights[idx]
    w = w / w.sum()

    rets = prices[present].pct_change().dropna()
    port_rets = rets.values @ w
    return pd.Series(port_rets, index=rets.index), w, present, missing


# ---------------------------------------------------------------------------
# Weight normalisation helpers
# ---------------------------------------------------------------------------

def normalize_weight_map(weight_map: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Normalise a ticker→weight mapping to sum to 1.0.

    Handles both decimal and percent inputs.
    """
    if not weight_map:
        return {}

    cleaned: Dict[str, float] = {}
    for ticker, value in weight_map.items():
        if ticker is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric < 0:
            numeric = 0.0
        cleaned[str(ticker)] = numeric

    if not cleaned:
        return {}

    max_weight = max(cleaned.values())
    if max_weight > 1.5:
        cleaned = {t: w / 100.0 for t, w in cleaned.items()}

    total = sum(cleaned.values())
    if total <= 0:
        return {}

    return {t: w / total for t, w in cleaned.items()}


def apply_min_active_weight(
    weights: np.ndarray, min_active_weight: float
) -> np.ndarray:
    """Zero out positions below *min_active_weight* and renormalise."""
    if min_active_weight <= 0:
        return weights

    adjusted = np.array(weights, dtype=float)
    adjusted[adjusted < min_active_weight] = 0.0

    total = float(adjusted.sum())
    if total <= 0:
        return weights

    return adjusted / total
