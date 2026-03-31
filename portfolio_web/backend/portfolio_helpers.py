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

    # ------------------------------------------------------------------
    # Factor-based risk model overlay: Cov = B * Cov_f * B' + D_residual
    # Uses FF5 betas from asset_metrics to decompose risk into systematic
    # (factor) and idiosyncratic components. Blended 50/50 with
    # statistical covariance for robustness.
    # ------------------------------------------------------------------
    try:
        factor_cov = _build_factor_risk_model(aligned_tickers, returns_df)
        if factor_cov is not None:
            cov_matrix = 0.5 * cov_matrix + 0.5 * factor_cov
    except Exception:
        pass  # fall back to statistical covariance only

    return aligned_tickers, mean_returns, cov_matrix


def _build_factor_risk_model(
    tickers: List[str], returns_df: pd.DataFrame
) -> np.ndarray | None:
    """Build factor-based covariance: B * Cov_factors * B' + Diag(residual_var).

    Uses FF5 factor betas from asset_metrics table. Returns annualised
    covariance matrix or None if insufficient data.
    """
    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """SELECT ticker, beta_mkt, beta_smb, beta_hml, beta_rmw, beta_cma
               FROM asset_metrics WHERE ticker = ANY(%s)""",
            (tickers,),
        )
        rows = cur.fetchall()

    if len(rows) < len(tickers) * 0.7:
        return None  # too many tickers missing betas

    betas_df = pd.DataFrame(rows).set_index("ticker")
    factor_cols = ["beta_mkt", "beta_smb", "beta_hml", "beta_rmw", "beta_cma"]

    # Align betas to ticker order, fill missing with zeros
    B = np.zeros((len(tickers), len(factor_cols)))
    for i, t in enumerate(tickers):
        if t in betas_df.index:
            row = betas_df.loc[t, factor_cols]
            for j, col in enumerate(factor_cols):
                val = row[col] if not isinstance(row, pd.Series) or col == col else row[col]
                B[i, j] = float(val) if val is not None and np.isfinite(float(val)) else 0.0

    # Estimate factor covariance from returns
    # Use returns residuals to estimate idiosyncratic variance
    returns_arr = returns_df[tickers].values  # T x N
    T = returns_arr.shape[0]

    # Approximate factor returns via cross-sectional regression
    # F_hat = (B'B)^-1 B' R' — OLS factor mimicking
    BtB = B.T @ B
    if np.linalg.matrix_rank(BtB) < len(factor_cols):
        return None

    BtB_inv = np.linalg.inv(BtB + 1e-8 * np.eye(len(factor_cols)))
    factor_returns = (BtB_inv @ B.T @ returns_arr.T).T  # T x K

    cov_factors = np.cov(factor_returns, rowvar=False)  # K x K (daily)

    # Residual (idiosyncratic) variance
    fitted = (B @ factor_returns.T).T  # T x N
    residuals = returns_arr - fitted
    residual_var = np.var(residuals, axis=0, ddof=1)  # N-vector

    # Factor covariance: B * Cov_f * B' + Diag(residual_var), annualised
    factor_cov = B @ cov_factors @ B.T * 252
    np.fill_diagonal(factor_cov, np.diag(factor_cov) + residual_var * 252)

    # Ensure positive semi-definite
    eigvals = np.linalg.eigvalsh(factor_cov)
    if eigvals.min() < 0:
        factor_cov += (-eigvals.min() + 1e-8) * np.eye(len(tickers))

    return factor_cov


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
