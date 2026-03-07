from datetime import datetime
from typing import List, Dict, Optional
import logging
import math
import json
import os

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf, OAS
from fastapi import APIRouter, HTTPException, Header, Cookie
from psycopg2.extras import Json

from db import get_cursor
from schemas import (
    SavePortfolioRequest,
    SavedPortfolioResponse,
    PersonaInfo,
    PortfolioRequest,
    PortfolioResponse,
    OptimizeWeightsRequest,
    CovarianceMetricsRequest,
    EfficientFrontierRequest,
    PortfolioHistoryRequest,
    BenchmarkAnalyticsRequest,
    BacktestRequest,
    StressTestRequest,
    RiskDecompositionRequest,
    DriftMonitorRequest,
)
from security import get_user_from_token, resolve_auth_token
from services import get_config_manager, get_portfolio_builder
from config import SESSION_COOKIE_NAME, PORTFOLIO_RISK_FREE_RATE
from portfolio_helpers import (
    load_mean_returns_and_covariance as _load_mean_returns_and_covariance,
    get_covariance_method as _get_covariance_method,
    fetch_price_matrix as _fetch_price_matrix,
    build_portfolio_returns as _build_portfolio_returns,
    normalize_weight_map as _normalize_weight_map,
    apply_min_active_weight as _apply_min_active_weight,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["portfolio"])

# Helper functions (_load_mean_returns_and_covariance, _get_covariance_method,
# _normalize_weight_map, _apply_min_active_weight, _fetch_price_matrix,
# _build_portfolio_returns) are imported from portfolio_helpers.py


@router.post("/api/portfolios/save", response_model=SavedPortfolioResponse)
async def save_portfolio(
    request: SavePortfolioRequest,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))

    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Portfolio name is required")
    if not request.source.strip():
        raise HTTPException(status_code=400, detail="Portfolio source is required")

    with get_cursor(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO saved_portfolios (user_id, name, source, data)
            VALUES (%s, %s, %s, %s)
            RETURNING id, name, source, created_at, data
            """,
            (user["id"], request.name.strip(), request.source.strip(), Json(request.data)),
        )
        saved = cur.fetchone()
        conn.commit()

    return dict(saved)


@router.get("/api/portfolios")
async def list_saved_portfolios(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT id, name, source, created_at, data
            FROM saved_portfolios
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user["id"],),
        )
        rows = cur.fetchall()

    return {"portfolios": rows}


@router.get("/api/personas", response_model=List[PersonaInfo])
async def get_personas():
    try:
        config_manager = get_config_manager()
        personas = config_manager.get_personas()
        return [
            PersonaInfo(
                name=name,
                display_name=config.get("display_name", name),
                description=config.get("description", ""),
                risk_level=config.get("risk_level", "medium"),
                expected_return=config.get("expected_return_range", ""),
            )
            for name, config in personas.items()
        ]
    except Exception:
        logger.exception("Error fetching personas")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/portfolio/generate", response_model=PortfolioResponse)
async def generate_portfolio(request: PortfolioRequest):
    try:
        config_manager = get_config_manager()
        portfolio_builder = get_portfolio_builder()

        personas = config_manager.get_personas()
        if request.persona_name not in personas:
            raise HTTPException(status_code=400, detail=f"Invalid persona. Available: {list(personas.keys())}")

        custom_overrides = {}
        if request.min_holdings:
            custom_overrides["min_stocks"] = request.min_holdings
        if request.max_holdings:
            custom_overrides["max_stocks"] = request.max_holdings
        if request.max_position_pct:
            custom_overrides["max_weight_per_stock"] = request.max_position_pct / 100
        if request.max_sector_pct:
            custom_overrides["max_sector_cap"] = request.max_sector_pct / 100
        custom_overrides["include_bonds"] = request.include_bonds
        custom_overrides["include_etfs"] = request.include_etfs

        portfolio_dict = portfolio_builder.build_portfolio(
            persona_name=request.persona_name,
            custom_overrides=custom_overrides if custom_overrides else None,
            exchanges=["NASDAQ", "TSX", "NYSE"],
        )

        if not portfolio_dict:
            raise HTTPException(status_code=500, detail="Failed to build portfolio")

        weights = portfolio_dict.get("weights", {})
        stocks_df = portfolio_dict.get("stocks")
        stats = portfolio_dict.get("stats", {})

        holdings = []
        if stocks_df is not None and not stocks_df.empty:
            for _, row in stocks_df.iterrows():
                ticker = row["ticker"]
                weight = row.get("weight", weights.get(ticker, 0))
                if weight < 0.0001:
                    continue

                amount = request.investment_amount * weight
                asset_class = row.get("asset_class", "stock")

                if asset_class == "bond":
                    holding_type = "bond"
                    default_exchange = "NYSE"
                elif asset_class in ["etf", "defensive_etf"]:
                    holding_type = "etf"
                    default_exchange = "NYSE"
                else:
                    holding_type = "stock"
                    default_exchange = "NASDAQ"

                raw_exchange = row.get("exchange")
                exchange = raw_exchange if raw_exchange and str(raw_exchange).strip() and str(raw_exchange) != "nan" else default_exchange

                if holding_type == "bond" and not request.include_bonds:
                    continue
                if holding_type == "etf" and not request.include_etfs:
                    continue

                expected_return = row.get("expected_return")
                volatility = row.get("volatility")

                # Log when model-derived estimates are missing (formerly hardcoded 0.08/0.15)
                if expected_return is None:
                    logger.debug("No model expected_return for %s — field will be null", ticker)
                if volatility is None:
                    logger.debug("No model volatility for %s — field will be null", ticker)

                price = 100

                holdings.append(
                    {
                        "ticker": ticker,
                        "name": row.get("name", ticker),
                        "sector": row.get("sector", "Unknown"),
                        "exchange": exchange,
                        "type": holding_type,
                        "asset_class": asset_class,
                        "weight": weight * 100,
                        "shares": round(amount / price, 2) if price > 0 else 0,
                        "value": round(amount, 2),
                        "expected_return": round(expected_return * 100, 2) if expected_return else None,
                        "volatility": round(volatility * 100, 2) if volatility else None,
                        "total_score": round(row.get("total_score", 0), 2),
                    }
                )

        if holdings:
            total_weight = sum(h["weight"] for h in holdings)
            if total_weight > 0 and abs(total_weight - 100) > 0.01:
                for holding in holdings:
                    holding["weight"] = round(holding["weight"] / total_weight * 100, 2)
                    holding["value"] = round(request.investment_amount * holding["weight"] / 100, 2)

        holdings.sort(key=lambda x: x["weight"], reverse=True)

        asset_class_breakdown = {}
        for holding in holdings:
            asset_type = holding["type"]
            asset_class_breakdown[asset_type] = asset_class_breakdown.get(asset_type, 0) + holding["weight"] / 100

        stats["asset_class_breakdown"] = asset_class_breakdown

        return PortfolioResponse(
            id=f"port_{datetime.utcnow().timestamp()}",
            persona=request.persona_name,
            created_at=datetime.utcnow(),
            investment_amount=request.investment_amount,
            holdings=holdings,
            summary={
                "total_holdings": len(holdings),
                "expected_return": stats.get("expected_return", 0),
                "volatility": stats.get("volatility", 0),
                "sector_breakdown": stats.get("sector_breakdown", {}),
                "asset_class_breakdown": asset_class_breakdown,
            },
            metrics=stats,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error generating portfolio")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/portfolio/analyze")
async def analyze_portfolio(holdings: List[Dict]):
    try:
        if not holdings:
            raise HTTPException(status_code=400, detail="Portfolio is empty")

        tickers = [holding["ticker"] for holding in holdings]
        placeholders = ",".join(["%s"] * len(tickers))

        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                f"""
                SELECT ticker, beta, pe_ratio, roe, sector
                FROM stocks
                WHERE ticker IN ({placeholders})
                """,
                tickers,
            )
            fundamentals = {row["ticker"]: row for row in cur.fetchall()}

        total_value = sum(holding.get("value", 0) for holding in holdings)

        analysis = {
            "total_holdings": len(holdings),
            "total_value": total_value,
            "concentration": max(holding.get("weight", 0) for holding in holdings) if holdings else 0,
            "sector_breakdown": {},
            "risk_metrics": {
                "avg_beta": sum(fundamentals.get(holding["ticker"], {}).get("beta", 0) or 0 for holding in holdings) / len(holdings) if holdings else 0,
                "portfolio_beta": sum((holding.get("weight", 0) * (fundamentals.get(holding["ticker"], {}).get("beta", 0) or 0)) for holding in holdings),
            },
            "performance_metrics": {
                "avg_pe": sum((fundamentals.get(holding["ticker"], {}).get("pe_ratio", 0) or 0) for holding in holdings) / len(holdings) if holdings else 0,
                "avg_roe": sum((fundamentals.get(holding["ticker"], {}).get("roe", 0) or 0) for holding in holdings) / len(holdings) if holdings else 0,
            },
        }

        return analysis
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error analyzing portfolio")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/portfolio/optimize-weights")
async def optimize_weights(request: OptimizeWeightsRequest):
    try:
        if not request.tickers:
            raise HTTPException(status_code=400, detail="No tickers provided")

        if not request.optimize_sharpe:
            equal_weight = 100.0 / len(request.tickers)
            result = [{"ticker": ticker, "weight": round(equal_weight, 2)} for ticker in request.tickers]
            return {
                "weights": result,
                "total_tickers": len(result),
                "optimized": False,
                "warning": {
                    "code": "OPTIMIZATION_BYPASSED",
                    "reason": "optimize_sharpe disabled",
                    "fallback_method": "equal_weight",
                },
            }

        aligned_tickers, mean_returns, cov_matrix = _load_mean_returns_and_covariance(request.tickers)

        if len(aligned_tickers) < 2:
            raise HTTPException(status_code=400, detail="Need at least two tickers for optimization")

        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT ticker, COALESCE(sector, 'Unknown') AS sector
                FROM stocks
                WHERE ticker = ANY(%s)
                """,
                (aligned_tickers,),
            )
            sector_rows = cur.fetchall()

        ticker_to_sector = {row["ticker"]: row["sector"] for row in sector_rows}

        def portfolio_return(weights):
            return np.dot(weights, mean_returns)

        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

        # ---- Previous weights (must be computed before objective uses them) ----
        previous_weight_map = _normalize_weight_map(request.previous_weights)
        previous_weights_vec = np.array([previous_weight_map.get(ticker, 0.0) for ticker in aligned_tickers], dtype=float)
        prev_total = float(previous_weights_vec.sum())
        if prev_total > 0:
            previous_weights_vec = previous_weights_vec / prev_total

        # ---- Diversification penalty (HHI) ----
        hhi_lambda = float(request.hhi_penalty_lambda or 0.0)

        def hhi_penalty(weights):
            """HHI = sum(w_i^2); lower is more diversified."""
            return float(np.sum(weights ** 2))

        # ---- Cost proxy ----
        cost_bps = float(request.cost_bps or 0.0)
        cost_decimal = cost_bps / 10000.0  # convert bps to decimal

        def turnover_cost(weights):
            """One-way turnover cost vs previous weights."""
            if prev_total <= 0 or cost_decimal <= 0:
                return 0.0
            return float(np.sum(np.abs(weights - previous_weights_vec))) * cost_decimal

        # ---- Objective function dispatcher ----
        objective_name = request.objective or "max_sharpe"

        def objective_function(weights):
            if objective_name == "min_vol":
                obj = portfolio_volatility(weights)
            elif objective_name == "target_return":
                # Minimise vol subject to return >= target (via constraint below)
                obj = portfolio_volatility(weights)
            elif objective_name == "risk_parity":
                vol = portfolio_volatility(weights)
                if vol < 1e-12:
                    return 0.0
                # Marginal risk contribution
                mrc = np.dot(cov_matrix, weights) / vol
                rc = weights * mrc
                target_rc = vol / len(weights)
                obj = float(np.sum((rc - target_rc) ** 2))
            else:  # max_sharpe (default)
                ret = portfolio_return(weights)
                vol = portfolio_volatility(weights)
                sharpe = (ret - PORTFOLIO_RISK_FREE_RATE) / vol if vol > 0 else 0
                obj = -sharpe

            # Add HHI penalty
            if hhi_lambda > 0:
                obj += hhi_lambda * hhi_penalty(weights)

            # Add cost penalty
            obj += turnover_cost(weights)

            return obj

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        # ---- Target return constraint ----
        if objective_name == "target_return" and request.target_return is not None:
            target_ret = float(request.target_return)
            constraints.append(
                {"type": "ineq", "fun": lambda w, tr=target_ret: portfolio_return(w) - tr}
            )

        if request.max_turnover is not None and prev_total > 0:
            max_turnover = float(request.max_turnover)
            constraints.append(
                {
                    "type": "ineq",
                    "fun": lambda w, pw=previous_weights_vec, mt=max_turnover: mt - float(np.sum(np.abs(w - pw))),
                }
            )

        benchmark_sector_weights = _normalize_weight_map(request.benchmark_sector_weights)
        if request.max_sector_active_weight is not None and not benchmark_sector_weights:
            if prev_total > 0:
                for idx, ticker in enumerate(aligned_tickers):
                    sector = ticker_to_sector.get(ticker, "Unknown")
                    benchmark_sector_weights[sector] = benchmark_sector_weights.get(sector, 0.0) + float(previous_weights_vec[idx])
            else:
                equal_weight = 1.0 / len(aligned_tickers)
                for ticker in aligned_tickers:
                    sector = ticker_to_sector.get(ticker, "Unknown")
                    benchmark_sector_weights[sector] = benchmark_sector_weights.get(sector, 0.0) + equal_weight
        if request.max_sector_active_weight is not None:
            max_sector_active_weight = float(request.max_sector_active_weight)
            sectors = sorted({ticker_to_sector.get(ticker, "Unknown") for ticker in aligned_tickers})

            for sector in sectors:
                idx = np.array(
                    [i for i, ticker in enumerate(aligned_tickers) if ticker_to_sector.get(ticker, "Unknown") == sector],
                    dtype=int,
                )
                benchmark_weight = float(benchmark_sector_weights.get(sector, 0.0))

                constraints.append(
                    {
                        "type": "ineq",
                        "fun": lambda w, idx=idx, bw=benchmark_weight, limit=max_sector_active_weight: (
                            limit - (float(np.sum(w[idx])) - bw)
                        ),
                    }
                )
                constraints.append(
                    {
                        "type": "ineq",
                        "fun": lambda w, idx=idx, bw=benchmark_weight, limit=max_sector_active_weight: (
                            limit + (float(np.sum(w[idx])) - bw)
                        ),
                    }
                )

        bounds = tuple((0.0, 1.0) for _ in range(len(aligned_tickers)))
        initial_weights = np.array([1.0 / len(aligned_tickers)] * len(aligned_tickers))

        if prev_total > 0:
            initial_weights = previous_weights_vec.copy()

        result_opt = minimize(
            objective_function,
            initial_weights,
            method="SLSQP",
            bounds=bounds,
            constraints=tuple(constraints),
            options={"maxiter": 1000},
        )

        if not result_opt.success:
            equal_weight = 100.0 / len(request.tickers)
            result = [{"ticker": ticker, "weight": round(equal_weight, 2)} for ticker in request.tickers]
            return {
                "weights": result,
                "total_tickers": len(result),
                "optimized": False,
                "warning": {
                    "code": "OPTIMIZATION_FAILED",
                    "reason": str(result_opt.message),
                    "fallback_method": "equal_weight",
                },
            }

        optimized_weights = _apply_min_active_weight(result_opt.x, float(request.min_active_weight or 0.0))

        if request.max_turnover is not None and prev_total > 0:
            realized_turnover = float(np.sum(np.abs(optimized_weights - previous_weights_vec)))
            max_turnover = float(request.max_turnover)
            if realized_turnover > max_turnover and realized_turnover > 0:
                blend = max(0.0, min(1.0, max_turnover / realized_turnover))
                optimized_weights = previous_weights_vec + blend * (optimized_weights - previous_weights_vec)
                optimized_weights = np.clip(optimized_weights, 0.0, None)
                total = float(optimized_weights.sum())
                if total > 0:
                    optimized_weights = optimized_weights / total

        result = []

        for index, ticker in enumerate(aligned_tickers):
            weight_pct = optimized_weights[index] * 100
            expected_return = mean_returns[index] * 100
            volatility = np.sqrt(cov_matrix[index, index]) * 100
            result.append(
                {
                    "ticker": ticker,
                    "weight": round(weight_pct, 2),
                    "expected_return": round(expected_return, 2),
                    "volatility": round(volatility, 2),
                }
            )

        portfolio_ret = portfolio_return(optimized_weights) * 100
        portfolio_vol = portfolio_volatility(optimized_weights) * 100
        portfolio_sharpe = (
            (portfolio_ret - (PORTFOLIO_RISK_FREE_RATE * 100)) / portfolio_vol
            if portfolio_vol > 0
            else 0
        )

        realized_turnover = None
        if prev_total > 0:
            realized_turnover = float(np.sum(np.abs(optimized_weights - previous_weights_vec)))

        return {
            "weights": result,
            "total_tickers": len(result),
            "optimized": True,
            "portfolio_metrics": {
                "expected_return": round(portfolio_ret, 2),
                "volatility": round(portfolio_vol, 2),
                "sharpe_ratio": round(portfolio_sharpe, 2),
            },
            "constraints_applied": {
                "objective": objective_name,
                "min_active_weight": float(request.min_active_weight or 0.0),
                "max_turnover": float(request.max_turnover) if request.max_turnover is not None else None,
                "realized_turnover": round(realized_turnover, 6) if realized_turnover is not None else None,
                "max_sector_active_weight": float(request.max_sector_active_weight)
                if request.max_sector_active_weight is not None
                else None,
                "hhi_penalty_lambda": hhi_lambda,
                "cost_bps": cost_bps,
            },
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error optimizing weights")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/portfolio/covariance-metrics")
async def covariance_metrics(request: CovarianceMetricsRequest):
    try:
        if not request.holdings:
            raise HTTPException(status_code=400, detail="No holdings provided")

        tickers = [holding.ticker for holding in request.holdings if holding.ticker]
        if not tickers:
            raise HTTPException(status_code=400, detail="No valid tickers provided")

        aligned_tickers, mean_returns, cov_matrix = _load_mean_returns_and_covariance(tickers)

        weight_map = {holding.ticker: float(holding.weight) for holding in request.holdings}
        raw_weights = np.array([weight_map.get(ticker, 0.0) for ticker in aligned_tickers], dtype=float)
        raw_weights = np.clip(raw_weights, 0.0, None)

        if raw_weights.size == 0 or float(raw_weights.sum()) <= 0:
            raise HTTPException(status_code=400, detail="Holdings must have positive weights")

        # Support both decimal (0..1) and percent (0..100) inputs
        if float(np.nanmax(raw_weights)) > 1.5:
            raw_weights = raw_weights / 100.0

        total_weight = float(raw_weights.sum())
        if total_weight <= 0:
            raise HTTPException(status_code=400, detail="Holdings must have positive weights")

        weights = raw_weights / total_weight
        portfolio_return = float(np.dot(weights, mean_returns))
        portfolio_variance = float(weights.T @ cov_matrix @ weights)
        portfolio_volatility = math.sqrt(max(portfolio_variance, 0.0))

        rf = float(request.risk_free_rate)
        sharpe = (portfolio_return - rf) / portfolio_volatility if portfolio_volatility > 0 else 0.0

        return {
            "metrics": {
                "expected_return": round(portfolio_return * 100, 4),
                "volatility": round(portfolio_volatility * 100, 4),
                "sharpe_ratio": round(sharpe, 4),
            },
            "n_assets": len(aligned_tickers),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error calculating covariance metrics")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/portfolio/efficient-frontier")
async def efficient_frontier(request: EfficientFrontierRequest):
    from scipy.optimize import minimize as scipy_minimize

    try:
        if not request.holdings:
            raise HTTPException(status_code=400, detail="No holdings provided")

        tickers = [holding.ticker for holding in request.holdings if holding.ticker]
        if len(tickers) < 2:
            raise HTTPException(status_code=400, detail="Need at least two holdings for frontier")

        aligned_tickers, mean_returns, cov_matrix = _load_mean_returns_and_covariance(tickers)
        n_assets = len(aligned_tickers)
        if n_assets < 2:
            raise HTTPException(status_code=400, detail="Need at least two aligned assets for frontier")

        weight_map = {holding.ticker: float(holding.weight) for holding in request.holdings}
        current_weights = np.array([weight_map.get(ticker, 0.0) for ticker in aligned_tickers], dtype=float)
        current_weights = np.clip(current_weights, 0.0, None)
        if current_weights.size and float(np.nanmax(current_weights)) > 1.5:
            current_weights = current_weights / 100.0
        if float(current_weights.sum()) <= 0:
            current_weights = np.array([1.0 / n_assets] * n_assets, dtype=float)
        else:
            current_weights = current_weights / float(current_weights.sum())

        def portfolio_stats(weights: np.ndarray) -> tuple[float, float]:
            port_return = float(np.dot(weights, mean_returns))
            port_variance = float(weights.T @ cov_matrix @ weights)
            port_risk = math.sqrt(max(port_variance, 0.0))
            return port_return, port_risk

        # --- Markowitz mean-variance optimization for the efficient frontier ---
        # Find return range from individual assets
        asset_returns = [float(mean_returns[i]) for i in range(n_assets)]
        min_ret = min(asset_returns)
        max_ret = max(asset_returns)

        if not np.isfinite(min_ret) or not np.isfinite(max_ret) or max_ret <= min_ret:
            raise HTTPException(status_code=400, detail="Insufficient return dispersion for frontier")

        # Bounds: each weight between 0 and 1 (long-only)
        bounds = [(0.0, 1.0)] * n_assets
        # Constraint: weights sum to 1
        sum_constraint = {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}

        n_frontier_points = int(request.bins)
        target_returns = np.linspace(min_ret, max_ret, n_frontier_points)

        frontier_points = []
        for target_ret in target_returns:
            return_constraint = {
                "type": "eq",
                "fun": lambda w, tr=target_ret: float(np.dot(w, mean_returns) - tr),
            }

            def objective(w):
                return float(w.T @ cov_matrix @ w)

            # Start from equal weights
            x0 = np.array([1.0 / n_assets] * n_assets, dtype=float)
            result = scipy_minimize(
                objective,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=[sum_constraint, return_constraint],
                options={"maxiter": 500, "ftol": 1e-12},
            )
            if result.success:
                opt_weights = result.x
                opt_ret, opt_risk = portfolio_stats(opt_weights)
                if np.isfinite(opt_ret) and np.isfinite(opt_risk) and opt_risk >= 0:
                    frontier_points.append(
                        {
                            "risk": round(opt_risk * 100, 2),
                            "return": round(opt_ret * 100, 2),
                        }
                    )

        # Sort by return (low → high) so the full hyperbola traces correctly:
        # bottom-right → min-variance vertex → top-right
        frontier_points.sort(key=lambda p: p["return"])

        diagonal = np.diag(cov_matrix)
        asset_points = []
        for idx, ticker in enumerate(aligned_tickers):
            asset_points.append(
                {
                    "name": ticker,
                    "risk": round(math.sqrt(max(float(diagonal[idx]), 0.0)) * 100, 2),
                    "return": round(float(mean_returns[idx]) * 100, 2),
                    "weight": round(float(current_weights[idx]) * 100, 2),
                }
            )

        current_return, current_risk = portfolio_stats(current_weights)

        return {
            "frontier": frontier_points,
            "asset_points": asset_points,
            "current_portfolio": {
                "risk": round(current_risk * 100, 2),
                "return": round(current_return * 100, 2),
            },
            "n_assets": n_assets,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error generating efficient frontier")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/portfolio/risk-diagnostics")
async def risk_diagnostics(request: CovarianceMetricsRequest):
    try:
        if not request.holdings:
            raise HTTPException(status_code=400, detail="No holdings provided")

        weight_map: dict[str, float] = {}
        for holding in request.holdings:
            if not holding.ticker:
                continue
            weight_map[holding.ticker] = weight_map.get(holding.ticker, 0.0) + float(holding.weight)

        tickers = list(weight_map.keys())
        if not tickers:
            raise HTTPException(status_code=400, detail="No valid tickers provided")

        raw_weights = np.array([weight_map[ticker] for ticker in tickers], dtype=float)
        raw_weights = np.clip(raw_weights, 0.0, None)
        if raw_weights.size == 0 or float(raw_weights.sum()) <= 0:
            raise HTTPException(status_code=400, detail="Holdings must have positive weights")

        if float(np.nanmax(raw_weights)) > 1.5:
            raw_weights = raw_weights / 100.0

        total_weight = float(raw_weights.sum())
        if total_weight <= 0:
            raise HTTPException(status_code=400, detail="Holdings must have positive weights")

        weights = raw_weights / total_weight
        hhi = float(np.sum(np.square(weights)))
        effective_holdings = float(1.0 / hhi) if hhi > 0 else 0.0
        top_weight_pct = float(np.max(weights) * 100)

        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT ticker, expected_return, volatility
                FROM asset_metrics
                WHERE ticker = ANY(%s)
                """,
                (tickers,),
            )
            metric_rows = cur.fetchall()

        metric_map = {row["ticker"]: row for row in metric_rows}
        missing_metrics_count = 0
        for ticker in tickers:
            row = metric_map.get(ticker)
            if row is None:
                missing_metrics_count += 1
                continue
            if row.get("expected_return") is None or row.get("volatility") is None:
                missing_metrics_count += 1

        missing_metrics_pct = (missing_metrics_count / len(tickers)) * 100 if tickers else 0.0

        covariance_available = True
        covariance_issue = None
        aligned_tickers: list[str] = []
        covariance_condition_number = None

        try:
            aligned_tickers, _, cov_matrix = _load_mean_returns_and_covariance(tickers)
            if cov_matrix.size > 0:
                condition_number = float(np.linalg.cond(cov_matrix))
                if np.isfinite(condition_number):
                    covariance_condition_number = condition_number
        except HTTPException as e:
            covariance_available = False
            covariance_issue = str(e.detail)

        return {
            "diagnostics": {
                "n_requested_assets": len(tickers),
                "n_aligned_assets": len(aligned_tickers),
                "effective_holdings": round(effective_holdings, 4),
                "top_weight_pct": round(top_weight_pct, 4),
                "hhi": round(hhi, 6),
                "missing_metrics_pct": round(missing_metrics_pct, 4),
                "missing_metrics_count": missing_metrics_count,
                "covariance_available": covariance_available,
                "covariance_condition_number": round(covariance_condition_number, 4)
                if covariance_condition_number is not None
                else None,
                "covariance_issue": covariance_issue,
            }
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error calculating risk diagnostics")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Historical portfolio performance (backfilled from real prices)
# ---------------------------------------------------------------------------

@router.post("/api/portfolio/historical-performance")
async def portfolio_historical_performance(req: PortfolioHistoryRequest):
    """
    Compute a realised historical portfolio value series using actual
    close prices from price_history.  Each holding's weight is treated as
    a fraction of the initial_value invested at the first available date,
    and the portfolio value is tracked daily going forward.
    """
    try:
        period_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}
        days = period_map.get(req.period.upper(), 365)

        tickers = [h.ticker.upper() for h in req.holdings]
        weights = np.array([h.weight for h in req.holdings], dtype=float)
        weight_sum = weights.sum()
        if weight_sum <= 0:
            raise HTTPException(status_code=400, detail="Weights must sum to a positive number")
        weights = weights / weight_sum  # normalise to 1.0

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
            return {"series": [], "tickers_missing": tickers, "period": req.period}

        prices_df = pd.DataFrame(rows)
        prices_pivot = prices_df.pivot_table(index="date", columns="ticker", values="close")
        prices_pivot = prices_pivot.sort_index()

        # Forward-fill gaps, then drop any remaining leading NaN rows
        prices_pivot = prices_pivot.ffill().dropna(how="any")

        if prices_pivot.shape[0] < 2:
            return {"series": [], "tickers_missing": tickers, "period": req.period}

        # Align columns to requested ticker order, fill missing with NaN
        present_tickers = [t for t in tickers if t in prices_pivot.columns]
        missing_tickers = [t for t in tickers if t not in prices_pivot.columns]

        if not present_tickers:
            return {"series": [], "tickers_missing": missing_tickers, "period": req.period}

        # Reweight to present tickers only
        present_indices = [tickers.index(t) for t in present_tickers]
        present_weights = weights[present_indices]
        present_weights = present_weights / present_weights.sum()

        # Normalise prices to day-0 = 1.0 for each ticker
        prices_aligned = prices_pivot[present_tickers]
        normalised = prices_aligned / prices_aligned.iloc[0]

        # Weighted portfolio index
        portfolio_index = normalised.values @ present_weights
        portfolio_values = portfolio_index * req.initial_value

        dates = prices_aligned.index.tolist()
        series = []
        for i, d in enumerate(dates):
            date_str = d.isoformat() if hasattr(d, "isoformat") else str(d)
            series.append({
                "date": date_str,
                "value": round(float(portfolio_values[i]), 2),
            })

        return {
            "series": series,
            "tickers_missing": missing_tickers,
            "period": req.period,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing historical performance")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Phase 3 — Benchmark-relative analytics
# ---------------------------------------------------------------------------
# _fetch_price_matrix and _build_portfolio_returns are imported from
# portfolio_helpers.py


@router.post("/api/portfolio/benchmark-analytics")
async def benchmark_analytics(req: BenchmarkAnalyticsRequest):
    """
    Compute benchmark-relative statistics: alpha, beta, tracking error,
    information ratio for the portfolio versus a benchmark.
    """
    try:
        period_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}
        days = period_map.get(req.period.upper(), 365)

        tickers = [h.ticker.upper() for h in req.holdings]
        weights = np.array([h.weight for h in req.holdings], dtype=float)
        w_sum = weights.sum()
        if w_sum <= 0:
            raise HTTPException(status_code=400, detail="Weights must sum to a positive number")
        weights = weights / w_sum

        # Fetch portfolio + benchmark prices in a single query
        all_tickers = list(set(tickers + [req.benchmark_ticker.upper()]))
        prices, missing = _fetch_price_matrix(all_tickers, days)

        bm = req.benchmark_ticker.upper()
        if bm in missing or bm not in prices.columns:
            raise HTTPException(status_code=404, detail=f"No price data for benchmark {bm}")

        port_rets, _, present, port_missing = _build_portfolio_returns(prices, tickers, weights)
        if port_rets.empty:
            raise HTTPException(status_code=422, detail="Insufficient price data for portfolio")

        bm_rets = prices[bm].pct_change().dropna()

        # Align dates
        common_idx = port_rets.index.intersection(bm_rets.index)
        if len(common_idx) < 5:
            raise HTTPException(status_code=422, detail="Not enough overlapping dates")

        pr = port_rets.loc[common_idx].values
        br = bm_rets.loc[common_idx].values

        # Beta & alpha (OLS regression: port = alpha + beta * benchmark + eps)
        cov_matrix = np.cov(np.vstack([pr, br]))
        cov_pb = float(cov_matrix[0, 1])
        var_b = float(cov_matrix[1, 1])
        beta = cov_pb / var_b if var_b > 0 else 0.0

        annualisation = 252
        ann_port = float(np.mean(pr)) * annualisation
        ann_bm = float(np.mean(br)) * annualisation
        alpha = ann_port - beta * ann_bm

        # Tracking error & information ratio
        active_rets = pr - br
        te = float(np.std(active_rets, ddof=1)) * math.sqrt(annualisation)
        ir = float(np.mean(active_rets)) * annualisation / te if te > 0 else 0.0

        # R-squared
        ss_res = float(np.sum((pr - (alpha / annualisation + beta * br)) ** 2))
        ss_tot = float(np.sum((pr - np.mean(pr)) ** 2))
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        return {
            "benchmark": bm,
            "period": req.period,
            "n_observations": len(common_idx),
            "tickers_missing": port_missing,
            "alpha": round(alpha, 6),
            "beta": round(beta, 6),
            "tracking_error": round(te, 6),
            "information_ratio": round(ir, 6),
            "r_squared": round(max(0.0, r_squared), 6),
            "ann_portfolio_return": round(ann_port, 6),
            "ann_benchmark_return": round(ann_bm, 6),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing benchmark analytics")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Phase 3 — Historical backtest with rebalancing schedule
# ---------------------------------------------------------------------------

@router.post("/api/portfolio/backtest")
async def portfolio_backtest(req: BacktestRequest):
    """
    Walk-forward backtest: simulate portfolio performance with periodic
    rebalancing back to target weights.  Returns daily value series,
    summary statistics, and rebalance events log.
    """
    try:
        period_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "3Y": 1095, "5Y": 1825}
        days = period_map.get(req.period.upper(), 365)

        tickers = [h.ticker.upper() for h in req.holdings]
        target_weights = np.array([h.weight for h in req.holdings], dtype=float)
        tw_sum = target_weights.sum()
        if tw_sum <= 0:
            raise HTTPException(status_code=400, detail="Weights must sum to a positive number")
        target_weights = target_weights / tw_sum

        prices, missing = _fetch_price_matrix(tickers, days)
        present = [t for t in tickers if t in prices.columns]
        if len(present) < 1 or prices.shape[0] < 3:
            raise HTTPException(status_code=422, detail="Insufficient price data for backtest")

        idx = [tickers.index(t) for t in present]
        tw = target_weights[idx]
        tw = tw / tw.sum()

        price_mat = prices[present].values  # shape (T, n)
        n_days = price_mat.shape[0]
        n_assets = price_mat.shape[1]

        # Determine rebalance schedule
        freq = req.rebalance_frequency.lower()
        rebal_interval = {
            "daily": 1, "weekly": 5, "monthly": 21, "quarterly": 63, "none": n_days + 1,
        }.get(freq, 21)

        # Walk-forward simulation
        portfolio_value = req.initial_value
        shares = tw * portfolio_value / price_mat[0]  # initial share count per asset
        rebalance_log = []
        cost_rate = req.cost_bps / 10_000  # convert bps to decimal
        total_cost = 0.0

        dates = prices.index.tolist()
        series = [{"date": dates[0].isoformat() if hasattr(dates[0], "isoformat") else str(dates[0]),
                    "value": round(portfolio_value, 2)}]

        days_since_rebal = 0
        for day in range(1, n_days):
            # Mark-to-market
            portfolio_value = float(np.sum(shares * price_mat[day]))
            days_since_rebal += 1

            # Should we rebalance?
            if days_since_rebal >= rebal_interval and day < n_days - 1:
                # Rebalance: redistribute to target weights
                new_shares = tw * portfolio_value / price_mat[day]
                trade_value = float(np.sum(np.abs(new_shares * price_mat[day] - shares * price_mat[day])))
                turnover = trade_value / portfolio_value

                # Deduct transaction costs (applied to traded notional)
                rebal_cost = trade_value * cost_rate
                total_cost += rebal_cost
                portfolio_value -= rebal_cost

                # Recalculate shares after cost deduction
                shares = tw * portfolio_value / price_mat[day]
                days_since_rebal = 0

                date_str = dates[day].isoformat() if hasattr(dates[day], "isoformat") else str(dates[day])
                rebalance_log.append({
                    "date": date_str,
                    "portfolio_value": round(portfolio_value, 2),
                    "turnover_pct": round(turnover * 100, 4),
                    "cost": round(rebal_cost, 2),
                })

            date_str = dates[day].isoformat() if hasattr(dates[day], "isoformat") else str(dates[day])
            series.append({"date": date_str, "value": round(portfolio_value, 2)})

        # Summary statistics
        values = np.array([s["value"] for s in series], dtype=float)
        daily_rets = np.diff(values) / values[:-1]
        total_return_pct = (values[-1] / values[0] - 1) * 100
        ann_return = float(np.mean(daily_rets)) * 252 * 100
        ann_vol = float(np.std(daily_rets, ddof=1)) * math.sqrt(252) * 100
        sharpe = ((ann_return - (PORTFOLIO_RISK_FREE_RATE * 100)) / ann_vol) if ann_vol > 0 else 0.0

        # Max drawdown
        running_max = np.maximum.accumulate(values)
        drawdowns = (values - running_max) / running_max
        max_drawdown_pct = float(np.min(drawdowns)) * 100

        return {
            "series": series,
            "tickers_missing": [t for t in tickers if t not in present],
            "period": req.period,
            "rebalance_frequency": req.rebalance_frequency,
            "n_rebalances": len(rebalance_log),
            "rebalance_log": rebalance_log,
            "summary": {
                "total_return_pct": round(total_return_pct, 4),
                "annualised_return_pct": round(ann_return, 4),
                "annualised_volatility_pct": round(ann_vol, 4),
                "sharpe_ratio": round(sharpe, 4),
                "max_drawdown_pct": round(max_drawdown_pct, 4),
                "initial_value": req.initial_value,
                "final_value": round(float(values[-1]), 2),
                "total_transaction_cost": round(total_cost, 2),
                "cost_bps": req.cost_bps,
            },
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error running backtest")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Phase 3 — Stress / scenario tests
# ---------------------------------------------------------------------------

_DEFAULT_SCENARIOS = {
    "rate_shock_up_200bps": {
        "label": "Interest rate shock +200 bps",
        "shocks": {"bond_factor": -0.08, "equity_factor": -0.05},
    },
    "equity_drawdown_20pct": {
        "label": "Equity drawdown −20%",
        "shocks": {"equity_factor": -0.20},
    },
    "volatility_spike_2x": {
        "label": "Volatility spike (2× recent vol)",
        "shocks": {"vol_multiplier": 2.0},
    },
    "stagflation": {
        "label": "Stagflation (rates up, equities down, vol up)",
        "shocks": {"bond_factor": -0.06, "equity_factor": -0.15, "vol_multiplier": 1.5},
    },
    "flight_to_quality": {
        "label": "Flight to quality (equities down, bonds up)",
        "shocks": {"bond_factor": 0.04, "equity_factor": -0.12},
    },
}


@router.post("/api/portfolio/stress-test")
async def stress_test(req: StressTestRequest):
    """
    Apply predefined shock scenarios to the portfolio.  Returns estimated
    portfolio PnL under each scenario using covariance + factor-based shocks.
    """
    try:
        tickers = [h.ticker.upper() for h in req.holdings]
        weights = np.array([h.weight for h in req.holdings], dtype=float)
        w_sum = weights.sum()
        if w_sum <= 0:
            raise HTTPException(status_code=400, detail="Weights must sum to a positive number")
        weights = weights / w_sum

        # Determine which scenarios to run
        if req.scenarios:
            scenario_keys = [s for s in req.scenarios if s in _DEFAULT_SCENARIOS]
            if not scenario_keys:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown scenarios. Available: {list(_DEFAULT_SCENARIOS.keys())}",
                )
        else:
            scenario_keys = list(_DEFAULT_SCENARIOS.keys())

        # Load asset metrics (beta_mkt, volatility) for factor-based shocks
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT ticker, expected_return, volatility, beta_mkt AS beta
                FROM asset_metrics WHERE ticker = ANY(%s)
                """,
                (tickers,),
            )
            rows = cur.fetchall()

        metric_map = {r["ticker"]: r for r in rows}

        # Default values for missing assets
        default_beta = 1.0
        default_vol = 0.20

        asset_betas = np.array(
            [float(metric_map.get(t, {}).get("beta") or default_beta) for t in tickers],
            dtype=float,
        )
        asset_vols = np.array(
            [float(metric_map.get(t, {}).get("volatility") or default_vol) for t in tickers],
            dtype=float,
        )

        results = []
        for key in scenario_keys:
            scenario = _DEFAULT_SCENARIOS[key]
            shocks = scenario["shocks"]

            # Compute per-asset return impact
            asset_impacts = np.zeros(len(tickers), dtype=float)

            equity_shock = shocks.get("equity_factor", 0.0)
            if equity_shock != 0.0:
                asset_impacts += asset_betas * equity_shock

            bond_shock = shocks.get("bond_factor", 0.0)
            if bond_shock != 0.0:
                # Bonds: inverse beta sensitivity approximation
                bond_sensitivity = np.clip(1.0 - asset_betas, 0.0, 1.5)
                asset_impacts += bond_sensitivity * bond_shock

            vol_mult = shocks.get("vol_multiplier", 1.0)
            if vol_mult != 1.0:
                # Vol spike: penalise proportional to asset volatility
                vol_drag = -asset_vols * (vol_mult - 1.0) * 0.5
                asset_impacts += vol_drag

            portfolio_impact = float(weights @ asset_impacts)

            # Per-asset detail
            asset_detail = []
            for i, t in enumerate(tickers):
                asset_detail.append({
                    "ticker": t,
                    "weight": round(float(weights[i]), 4),
                    "impact_pct": round(float(asset_impacts[i]) * 100, 4),
                })

            results.append({
                "scenario": key,
                "label": scenario["label"],
                "portfolio_impact_pct": round(portfolio_impact * 100, 4),
                "assets": asset_detail,
            })

        return {"scenarios": results, "n_assets": len(tickers)}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error running stress tests")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Phase 3 — Risk decomposition (marginal & component contribution)
# ---------------------------------------------------------------------------

@router.post("/api/portfolio/risk-decomposition")
async def risk_decomposition(req: RiskDecompositionRequest):
    """
    Decompose total portfolio risk into:
    - marginal contribution to risk (MCR) per asset
    - component contribution to risk (CCR = w_i * MCR_i)
    - percentage contribution to risk (PCR = CCR_i / sigma_p)
    """
    try:
        tickers = [h.ticker.upper() for h in req.holdings]
        weights_raw = np.array([h.weight for h in req.holdings], dtype=float)
        w_sum = weights_raw.sum()
        if w_sum <= 0:
            raise HTTPException(status_code=400, detail="Weights must sum to a positive number")
        weights = weights_raw / w_sum

        aligned_tickers, mean_returns, cov_matrix = _load_mean_returns_and_covariance(tickers)
        n = len(aligned_tickers)

        # Re-align weights to matched tickers
        ticker_idx = {t: i for i, t in enumerate(tickers)}
        aligned_weights = np.array(
            [weights[ticker_idx[t]] for t in aligned_tickers], dtype=float,
        )
        aligned_weights = aligned_weights / aligned_weights.sum()

        # Portfolio variance & vol
        port_var = float(aligned_weights @ cov_matrix @ aligned_weights)
        port_vol = math.sqrt(port_var) if port_var > 0 else 1e-10

        # Marginal contribution to risk = (Σ w) / σ_p
        mcr = (cov_matrix @ aligned_weights) / port_vol

        # Component contribution = w_i * MCR_i
        ccr = aligned_weights * mcr

        # Percentage contribution = CCR_i / σ_p
        pcr = ccr / port_vol if port_vol > 0 else ccr * 0.0

        assets = []
        for i, t in enumerate(aligned_tickers):
            assets.append({
                "ticker": t,
                "weight": round(float(aligned_weights[i]), 6),
                "marginal_contribution": round(float(mcr[i]), 8),
                "component_contribution": round(float(ccr[i]), 8),
                "pct_contribution": round(float(pcr[i]) * 100, 4),
            })

        # Sort by absolute pct contribution descending
        assets.sort(key=lambda a: abs(a["pct_contribution"]), reverse=True)

        return {
            "portfolio_volatility": round(port_vol, 6),
            "portfolio_variance": round(port_var, 8),
            "n_assets": n,
            "tickers_missing": [t for t in tickers if t not in aligned_tickers],
            "assets": assets,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing risk decomposition")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Phase 3 — Portfolio drift monitor & rebalance recommendation
# ---------------------------------------------------------------------------

@router.post("/api/portfolio/drift-monitor")
async def drift_monitor(req: DriftMonitorRequest):
    """
    Detect drift of current portfolio weights from target weights.
    If current_values are provided, compute actual weights from market values.
    Otherwise, fetch latest prices and approximate current weights.
    Returns drift per asset, overall drift score, and rebalance recommendations.
    """
    try:
        tickers = [h.ticker.upper() for h in req.holdings]
        target_weights = np.array([h.weight for h in req.holdings], dtype=float)
        tw_sum = target_weights.sum()
        if tw_sum <= 0:
            raise HTTPException(status_code=400, detail="Weights must sum to a positive number")
        target_weights = target_weights / tw_sum

        # Determine current weights
        if req.current_values and len(req.current_values) > 0:
            # Use provided market values
            total_value = sum(req.current_values.values())
            if total_value <= 0:
                raise HTTPException(status_code=400, detail="Current values must be positive")
            current_weights = np.array(
                [req.current_values.get(t, 0.0) / total_value for t in tickers],
                dtype=float,
            )
        else:
            # Approximate: fetch latest prices and assume equal initial investment
            # then simulate price drift over past month
            prices, missing = _fetch_price_matrix(tickers, 30)
            if prices.empty or prices.shape[0] < 2:
                # No price data — assume weights haven't drifted
                current_weights = target_weights.copy()
            else:
                present = [t for t in tickers if t in prices.columns]
                # Price change ratios from first to last date
                price_change = np.array(
                    [float(prices[t].iloc[-1] / prices[t].iloc[0]) if t in present else 1.0 for t in tickers],
                    dtype=float,
                )
                # Current weights = target * price_change / sum(target * price_change)
                drifted = target_weights * price_change
                current_weights = drifted / drifted.sum() if drifted.sum() > 0 else target_weights.copy()

        # Per-asset drift
        drift_abs = current_weights - target_weights
        drift_pct = drift_abs * 100  # in percentage points

        # Overall drift score = sqrt(sum of squared drift)
        drift_score = float(math.sqrt(np.sum(drift_abs ** 2))) * 100

        # Rebalance recommendations
        threshold = req.rebalance_threshold
        needs_rebalance = False
        recommendations = []
        assets = []

        for i, t in enumerate(tickers):
            d = float(drift_pct[i])
            tw = float(target_weights[i]) * 100
            cw = float(current_weights[i]) * 100
            breaches = abs(d) >= threshold

            if breaches:
                needs_rebalance = True
                action = "SELL" if d > 0 else "BUY"
                recommendations.append({
                    "ticker": t,
                    "action": action,
                    "drift_pct": round(d, 4),
                    "target_weight_pct": round(tw, 4),
                    "current_weight_pct": round(cw, 4),
                })

            assets.append({
                "ticker": t,
                "target_weight_pct": round(tw, 4),
                "current_weight_pct": round(cw, 4),
                "drift_pct": round(d, 4),
                "breaches_threshold": breaches,
            })

        return {
            "drift_score": round(drift_score, 4),
            "rebalance_threshold_pct": threshold,
            "needs_rebalance": needs_rebalance,
            "n_assets": len(tickers),
            "assets": assets,
            "recommendations": recommendations,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing drift monitor")
        raise HTTPException(status_code=500, detail="Internal server error")
