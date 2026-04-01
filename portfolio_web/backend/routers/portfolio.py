from datetime import datetime
from typing import List, Dict, Optional
import logging
import math
import json
import os
import secrets

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf, OAS
from fastapi import APIRouter, HTTPException, Header, Cookie, Query, Request
from psycopg2.extras import Json

from db import get_cursor
from cache_store import TTLCache
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
    AnalyzePortfolioRequest,
    PortfolioGoalRequest,
)
from security import get_user_from_token, resolve_auth_token, write_audit_log
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
_persona_cache = TTLCache(ttl_seconds=300)

# Helper functions (_load_mean_returns_and_covariance, _get_covariance_method,
# _normalize_weight_map, _apply_min_active_weight, _fetch_price_matrix,
# _build_portfolio_returns) are imported from portfolio_helpers.py


@router.post("/api/portfolios/save", response_model=SavedPortfolioResponse)
async def save_portfolio(
    request: SavePortfolioRequest,
    req: Request = None,
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

    client_ip = req.client.host if req and req.client else None
    write_audit_log("portfolio_save", user_id=user["id"], detail=f"name={request.name.strip()}", ip_address=client_ip)

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


@router.post("/api/portfolios/{portfolio_id}/share")
async def share_portfolio(
    portfolio_id: int,
    req: Request = None,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Generate a share token for a saved portfolio (read-only link)."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))

    with get_cursor(dict_cursor=True) as (conn, cur):
        cur.execute(
            "SELECT id, share_token FROM saved_portfolios WHERE id = %s AND user_id = %s",
            (portfolio_id, user["id"]),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Return existing token if already shared
    if row.get("share_token"):
        return {"share_token": row["share_token"], "portfolio_id": portfolio_id}

    share_token = secrets.token_urlsafe(24)

    with get_cursor() as (conn, cur):
        cur.execute(
            "UPDATE saved_portfolios SET share_token = %s, is_public = TRUE WHERE id = %s AND user_id = %s",
            (share_token, portfolio_id, user["id"]),
        )
        conn.commit()

    client_ip = req.client.host if req and req.client else None
    write_audit_log("portfolio_share", user_id=user["id"], detail=f"portfolio_id={portfolio_id}", ip_address=client_ip)

    return {"share_token": share_token, "portfolio_id": portfolio_id}


@router.delete("/api/portfolios/{portfolio_id}/share")
async def unshare_portfolio(
    portfolio_id: int,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Revoke the share link for a portfolio."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))

    with get_cursor() as (conn, cur):
        cur.execute(
            "UPDATE saved_portfolios SET share_token = NULL, is_public = FALSE WHERE id = %s AND user_id = %s",
            (portfolio_id, user["id"]),
        )
        updated = cur.rowcount
        conn.commit()

    if updated == 0:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    return {"success": True, "message": "Share link revoked"}


@router.get("/api/shared/{share_token}")
async def get_shared_portfolio(share_token: str):
    """Public endpoint — fetch a shared portfolio by its token (read-only)."""
    if not share_token or len(share_token) > 64:
        raise HTTPException(status_code=400, detail="Invalid share token")

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT sp.id, sp.name, sp.source, sp.created_at, sp.data,
                   au.email AS owner_email
            FROM saved_portfolios sp
            JOIN app_users au ON au.id = sp.user_id
            WHERE sp.share_token = %s AND sp.is_public = TRUE
            """,
            (share_token,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Shared portfolio not found")

    # Redact owner email to first char + domain
    owner = row.get("owner_email", "")
    if "@" in owner:
        local, domain = owner.split("@", 1)
        owner = f"{local[0]}***@{domain}"

    return {
        "id": row["id"],
        "name": row["name"],
        "source": row["source"],
        "created_at": row["created_at"],
        "data": row["data"],
        "shared_by": owner,
    }


@router.get("/api/personas", response_model=List[PersonaInfo])
async def get_personas():
    cached = _persona_cache.get("personas")
    if cached is not None:
        return cached

    try:
        config_manager = get_config_manager()
        personas = config_manager.get_personas()
        result = [
            PersonaInfo(
                name=name,
                display_name=config.get("display_name", name),
                description=config.get("description", ""),
                risk_level=config.get("risk_level", "medium"),
                expected_return=config.get("expected_return_range", ""),
            )
            for name, config in personas.items()
        ]
        _persona_cache.set("personas", result)
        return result
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
async def analyze_portfolio(request: AnalyzePortfolioRequest):
    try:
        holdings = request.holdings
        if not holdings:
            raise HTTPException(status_code=400, detail="Portfolio is empty")

        tickers = [h.ticker for h in holdings]

        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT ticker, beta, pe_ratio, roe, sector
                FROM stocks
                WHERE ticker = ANY(%s)
                """,
                (tickers,),
            )
            fundamentals = {row["ticker"]: row for row in cur.fetchall()}

        total_value = sum(h.value for h in holdings)

        sector_breakdown = {}
        for h in holdings:
            sector = fundamentals.get(h.ticker, {}).get("sector") or "Unknown"
            sector_breakdown[sector] = sector_breakdown.get(sector, 0) + h.weight

        analysis = {
            "total_holdings": len(holdings),
            "total_value": total_value,
            "concentration": max(h.weight for h in holdings) if holdings else 0,
            "sector_breakdown": sector_breakdown,
            "risk_metrics": {
                "avg_beta": sum(fundamentals.get(h.ticker, {}).get("beta", 0) or 0 for h in holdings) / len(holdings) if holdings else 0,
                "portfolio_beta": sum((h.weight * (fundamentals.get(h.ticker, {}).get("beta", 0) or 0)) for h in holdings),
            },
            "performance_metrics": {
                "avg_pe": sum((fundamentals.get(h.ticker, {}).get("pe_ratio", 0) or 0) for h in holdings) / len(holdings) if holdings else 0,
                "avg_roe": sum((fundamentals.get(h.ticker, {}).get("roe", 0) or 0) for h in holdings) / len(holdings) if holdings else 0,
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

        if len(request.tickers) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 tickers allowed per optimization request")

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
            # Feasibility check: target cannot exceed max individual asset return
            max_achievable = float(np.max(mean_returns))
            if target_ret > max_achievable:
                raise HTTPException(
                    status_code=422,
                    detail=f"Target return {target_ret:.4f} exceeds maximum achievable return {max_achievable:.4f}. "
                           f"Reduce target or add higher-return assets.",
                )
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
            # Use approximate S&P 500 sector weights as default benchmark
            # instead of equal-weight, reflecting actual market structure.
            _sp500_sector_weights = {
                "Technology": 0.30, "Healthcare": 0.13, "Financials": 0.13,
                "Consumer Discretionary": 0.10, "Communication Services": 0.09,
                "Industrials": 0.08, "Consumer Staples": 0.06, "Energy": 0.04,
                "Utilities": 0.03, "Real Estate": 0.02, "Materials": 0.02,
            }
            # Map portfolio sectors to benchmark weights; unknown sectors
            # get a small residual allocation so constraints remain feasible.
            portfolio_sectors = {ticker_to_sector.get(t, "Unknown") for t in aligned_tickers}
            matched_total = sum(_sp500_sector_weights.get(s, 0.0) for s in portfolio_sectors)
            for sector in portfolio_sectors:
                if sector in _sp500_sector_weights:
                    # Re-normalise to the subset of sectors present
                    benchmark_sector_weights[sector] = _sp500_sector_weights[sector] / matched_total if matched_total > 0 else 1.0 / len(portfolio_sectors)
                else:
                    benchmark_sector_weights[sector] = 0.02  # small residual
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

        # ---- Liquidity constraint: max % of 20-day average volume ----
        if request.max_volume_pct is not None and request.portfolio_value and request.portfolio_value > 0:
            with get_cursor(dict_cursor=True) as (_, cur):
                cur.execute(
                    """
                    SELECT ticker, AVG(volume) AS avg_volume, AVG(close) AS avg_price
                    FROM (
                        SELECT ticker, volume, close,
                               ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) AS rn
                        FROM price_history
                        WHERE ticker = ANY(%s) AND volume IS NOT NULL AND volume > 0
                    ) sub
                    WHERE rn <= 20
                    GROUP BY ticker
                    """,
                    (aligned_tickers,),
                )
                vol_rows = cur.fetchall()

            vol_map = {r["ticker"]: r for r in vol_rows}
            max_pct = request.max_volume_pct / 100.0

            # Convert bounds to list so we can tighten per-asset upper bounds
            bounds_list = list(bounds)
            for i, t in enumerate(aligned_tickers):
                v = vol_map.get(t)
                if v and v["avg_volume"] and v["avg_price"] and v["avg_price"] > 0:
                    # Max dollar value = max_pct * avg_volume * avg_price
                    max_dollar = float(v["avg_volume"]) * float(v["avg_price"]) * max_pct
                    max_weight = min(1.0, max_dollar / request.portfolio_value)
                    lo, hi = bounds_list[i]
                    bounds_list[i] = (lo, min(hi, max_weight))
            bounds = tuple(bounds_list)

        # ---- ESG constraints: min ESG score and/or max carbon intensity ----
        esg_excluded = set()
        if request.min_esg_score is not None or request.max_carbon_intensity is not None:
            with get_cursor(dict_cursor=True) as (_, cur):
                cur.execute(
                    "SELECT ticker, esg_score, carbon_intensity FROM stocks WHERE ticker = ANY(%s)",
                    (aligned_tickers,),
                )
                esg_rows = cur.fetchall()

            esg_map = {r["ticker"]: r for r in esg_rows}

            bounds_list = list(bounds)
            for i, t in enumerate(aligned_tickers):
                esg = esg_map.get(t, {})
                score = esg.get("esg_score")
                carbon = esg.get("carbon_intensity")

                excluded = False
                if request.min_esg_score is not None:
                    if score is None or float(score) < request.min_esg_score:
                        excluded = True
                if request.max_carbon_intensity is not None:
                    if carbon is not None and float(carbon) > request.max_carbon_intensity:
                        excluded = True

                if excluded:
                    bounds_list[i] = (0.0, 0.0)  # force weight to zero
                    esg_excluded.add(t)
            bounds = tuple(bounds_list)

        # Warm-start: use previous weights if available, else equal-weight
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
            # Infeasibility detection: distinguish contradictory constraints
            # from convergence issues
            msg = str(result_opt.message)
            is_infeasible = any(kw in msg.lower() for kw in [
                "positive directional derivative",
                "inequality constraints incompatible",
                "singular matrix",
            ])
            if is_infeasible:
                raise HTTPException(
                    status_code=422,
                    detail=f"Optimization infeasible: constraints are contradictory. "
                           f"Relax max_sector_active_weight, max_turnover, or target_return. "
                           f"Solver message: {msg}",
                )

            # Non-infeasible failure — fall back to equal weight with warning
            equal_weight = 100.0 / len(request.tickers)
            result = [{"ticker": ticker, "weight": round(equal_weight, 2)} for ticker in request.tickers]
            return {
                "weights": result,
                "total_tickers": len(result),
                "optimized": False,
                "warning": {
                    "code": "OPTIMIZATION_FAILED",
                    "reason": msg,
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
                "max_volume_pct": float(request.max_volume_pct) if request.max_volume_pct is not None else None,
                "min_esg_score": float(request.min_esg_score) if request.min_esg_score is not None else None,
                "max_carbon_intensity": float(request.max_carbon_intensity) if request.max_carbon_intensity is not None else None,
                "esg_excluded_tickers": sorted(esg_excluded) if esg_excluded else [],
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

        def _walk_forward_weights(price_history_slice: np.ndarray, current_tw: np.ndarray) -> np.ndarray:
            """Re-estimate minimum-variance weights using only past data.

            Uses a simplified approach: re-compute covariance from the
            available history slice and find the min-vol portfolio
            (constrained to be close to target weights).
            Falls back to current target weights if insufficient data.
            """
            if price_history_slice.shape[0] < 60:
                return current_tw
            try:
                rets = np.diff(price_history_slice, axis=0) / price_history_slice[:-1]
                # Forward-fill any NaN in returns
                rets = np.nan_to_num(rets, nan=0.0)
                cov_method = _get_covariance_method()
                if cov_method == "ledoit_wolf":
                    cov = LedoitWolf().fit(rets).covariance_ * 252
                elif cov_method == "oas":
                    cov = OAS().fit(rets).covariance_ * 252
                else:
                    cov = np.cov(rets, rowvar=False) * 252

                n = cov.shape[0]
                # Minimum variance with shrinkage toward target
                inv_cov = np.linalg.inv(cov + np.eye(n) * 1e-6)
                ones = np.ones(n)
                mv_weights = inv_cov @ ones / (ones @ inv_cov @ ones)
                mv_weights = np.clip(mv_weights, 0.0, None)
                mv_weights = mv_weights / mv_weights.sum()
                # Blend: 70% target + 30% min-variance (walk-forward adjustment)
                blended = 0.7 * current_tw + 0.3 * mv_weights
                blended = np.clip(blended, 0.0, None)
                blended = blended / blended.sum()
                return blended
            except Exception:
                return current_tw

        # Determine rebalance schedule using actual business dates
        freq = req.rebalance_frequency.lower()

        # Build set of rebalance dates from actual business calendar
        all_dates = prices.index.tolist()
        date_index = pd.DatetimeIndex(all_dates)
        if freq == "none":
            rebal_dates = set()
        elif freq == "daily":
            rebal_dates = set(all_dates)
        elif freq == "weekly":
            # Last trading day of each week
            week_groups = date_index.to_series().groupby(date_index.isocalendar().week).last()
            rebal_dates = set(week_groups.values)
        elif freq == "quarterly":
            # Last trading day of each quarter
            qtr_groups = date_index.to_series().groupby(date_index.to_period("Q")).last()
            rebal_dates = set(qtr_groups.values)
        else:  # monthly (default)
            # Last trading day of each month — proper BMonthEnd
            month_groups = date_index.to_series().groupby(date_index.to_period("M")).last()
            rebal_dates = set(month_groups.values)

        # Walk-forward simulation
        portfolio_value = req.initial_value
        shares = tw * portfolio_value / price_mat[0]  # initial share count per asset
        rebalance_log = []
        cost_rate = req.cost_bps / 10_000  # convert bps to decimal

        # Simplified Almgren-Chriss market impact: impact ≈ k * σ * sqrt(trade_fraction)
        # where k is a market impact coefficient and trade_fraction is the
        # fraction of portfolio being traded.  This penalises large rebalances
        # more than proportionally, reflecting real market microstructure.
        market_impact_k = 0.1  # impact coefficient (conservative)

        # Pre-compute per-asset trailing volatility for impact estimation
        asset_daily_rets = np.diff(price_mat, axis=0) / price_mat[:-1]
        asset_trailing_vol = np.std(asset_daily_rets[-min(60, asset_daily_rets.shape[0]):], axis=0, ddof=1) if asset_daily_rets.shape[0] > 1 else np.full(n_assets, 0.01)

        total_cost = 0.0

        dates = prices.index.tolist()
        series = [{"date": dates[0].isoformat() if hasattr(dates[0], "isoformat") else str(dates[0]),
                    "value": round(portfolio_value, 2)}]

        for day in range(1, n_days):
            # Mark-to-market
            portfolio_value = float(np.sum(shares * price_mat[day]))

            # Should we rebalance? Check if this date is a rebalance date
            current_date = dates[day]
            # Convert to Timestamp for comparison if needed
            current_ts = pd.Timestamp(current_date)
            if current_ts in rebal_dates and day < n_days - 1:
                # Walk-forward: re-estimate weights using only data up to this point
                rebal_tw = _walk_forward_weights(price_mat[:day + 1], tw)

                # Rebalance: redistribute to re-estimated target weights
                new_shares = rebal_tw * portfolio_value / price_mat[day]
                trade_notional = np.abs(new_shares * price_mat[day] - shares * price_mat[day])
                trade_value = float(np.sum(trade_notional))
                turnover = trade_value / portfolio_value

                # Flat transaction cost
                flat_cost = trade_value * cost_rate

                # Market impact: k * σ_i * sqrt(trade_fraction_i) per asset
                trade_fractions = trade_notional / max(portfolio_value, 1.0)
                impact_per_asset = market_impact_k * asset_trailing_vol * np.sqrt(trade_fractions) * (trade_notional)
                market_impact_cost = float(np.sum(impact_per_asset))

                rebal_cost = flat_cost + market_impact_cost
                total_cost += rebal_cost
                portfolio_value -= rebal_cost

                # Recalculate shares after cost deduction
                shares = rebal_tw * portfolio_value / price_mat[day]

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
    # --- Historically calibrated scenarios ---
    "gfc_2008": {
        "label": "2008 Global Financial Crisis (Oct 07–Mar 09)",
        "shocks": {"equity_factor": -0.55, "bond_factor": 0.12, "vol_multiplier": 3.5},
    },
    "covid_crash_2020": {
        "label": "COVID-19 Crash (Feb–Mar 2020)",
        "shocks": {"equity_factor": -0.34, "bond_factor": 0.05, "vol_multiplier": 4.0},
    },
    "taper_tantrum_2013": {
        "label": "2013 Taper Tantrum (May–Sep 2013)",
        "shocks": {"equity_factor": -0.06, "bond_factor": -0.05, "vol_multiplier": 1.4},
    },
    "rate_hike_2022": {
        "label": "2022 Rate Hike Cycle (Jan–Oct 2022)",
        "shocks": {"equity_factor": -0.25, "bond_factor": -0.17, "vol_multiplier": 1.5},
    },
    "dot_com_bust_2000": {
        "label": "Dot-Com Bust (Mar 2000–Oct 2002)",
        "shocks": {"equity_factor": -0.49, "bond_factor": 0.15, "vol_multiplier": 2.0},
    },
    "euro_debt_crisis_2011": {
        "label": "European Debt Crisis (Jul–Oct 2011)",
        "shocks": {"equity_factor": -0.19, "bond_factor": 0.06, "vol_multiplier": 2.2},
    },
    # --- Generic factor-based scenarios ---
    "rate_shock_up_200bps": {
        "label": "Interest rate shock +200 bps",
        "shocks": {"bond_factor": -0.08, "equity_factor": -0.05},
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

        # ----- Predictive drift forecast (30-day) -----
        forecast = None
        try:
            prices_90, _ = _fetch_price_matrix(tickers, 90)
            if not prices_90.empty and prices_90.shape[0] >= 20:
                present_90 = [t for t in tickers if t in prices_90.columns]
                # Compute annualized daily return trend & volatility
                daily_returns = prices_90[present_90].pct_change().dropna()
                if len(daily_returns) >= 10:
                    mean_daily = daily_returns.mean()
                    std_daily = daily_returns.std()

                    # Project 30 trading days forward using drift = mean * 30
                    projected_change = np.array(
                        [float(1.0 + mean_daily.get(t, 0.0) * 30) if t in present_90 else 1.0
                         for t in tickers],
                        dtype=float,
                    )
                    projected_drifted = target_weights * projected_change
                    proj_sum = projected_drifted.sum()
                    projected_weights = projected_drifted / proj_sum if proj_sum > 0 else target_weights.copy()

                    proj_drift_abs = projected_weights - target_weights
                    forecast_drift_score = float(math.sqrt(np.sum(proj_drift_abs ** 2))) * 100

                    # Rebalance urgency: low / medium / high
                    if forecast_drift_score >= threshold * 2:
                        urgency = "high"
                    elif forecast_drift_score >= threshold:
                        urgency = "medium"
                    else:
                        urgency = "low"

                    forecast_assets = []
                    for i, t in enumerate(tickers):
                        vol_30d = float(std_daily.get(t, 0.0) * math.sqrt(30) * 100) if t in present_90 else 0.0
                        forecast_assets.append({
                            "ticker": t,
                            "projected_weight_pct": round(float(projected_weights[i]) * 100, 4),
                            "projected_drift_pct": round(float(proj_drift_abs[i]) * 100, 4),
                            "volatility_30d_pct": round(vol_30d, 4),
                        })

                    forecast = {
                        "horizon_days": 30,
                        "forecast_drift_score": round(forecast_drift_score, 4),
                        "rebalance_urgency": urgency,
                        "assets": forecast_assets,
                    }
        except Exception:
            logger.debug("Predictive drift forecast unavailable", exc_info=True)

        return {
            "drift_score": round(drift_score, 4),
            "rebalance_threshold_pct": threshold,
            "needs_rebalance": needs_rebalance,
            "n_assets": len(tickers),
            "assets": assets,
            "recommendations": recommendations,
            "forecast": forecast,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing drift monitor")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Phase 2 — Portfolio-level FF5 factor attribution
# ---------------------------------------------------------------------------

@router.post("/api/portfolio/factor-attribution")
async def factor_attribution(req: RiskDecompositionRequest):
    """
    Aggregate individual stock FF5 betas into portfolio-level factor
    exposures.  Returns weighted beta to each Fama-French factor,
    the portfolio alpha, and per-asset factor detail.
    """
    try:
        tickers = [h.ticker.upper() for h in req.holdings]
        weights_raw = np.array([h.weight for h in req.holdings], dtype=float)
        w_sum = weights_raw.sum()
        if w_sum <= 0:
            raise HTTPException(status_code=400, detail="Weights must sum to a positive number")
        weights = weights_raw / w_sum

        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT ticker, beta_mkt, beta_smb, beta_hml, beta_rmw, beta_cma,
                       alpha, r2, expected_return, volatility
                FROM asset_metrics
                WHERE ticker = ANY(%s)
                """,
                (tickers,),
            )
            rows = cur.fetchall()

        metric_map = {r["ticker"]: r for r in rows}

        factor_names = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
        beta_keys = ["beta_mkt", "beta_smb", "beta_hml", "beta_rmw", "beta_cma"]

        # Per-asset detail
        asset_detail = []
        portfolio_betas = np.zeros(5)
        portfolio_alpha = 0.0

        for i, t in enumerate(tickers):
            m = metric_map.get(t, {})
            betas = [float(m.get(k) or 0.0) for k in beta_keys]
            asset_alpha = float(m.get("alpha") or 0.0)

            # Weight contributions
            for j in range(5):
                portfolio_betas[j] += weights[i] * betas[j]
            portfolio_alpha += weights[i] * asset_alpha

            asset_detail.append({
                "ticker": t,
                "weight": round(float(weights[i]), 6),
                "betas": {name: round(b, 4) for name, b in zip(factor_names, betas)},
                "alpha": round(asset_alpha * 12 * 100, 4),  # annualised %
                "r2": round(float(m.get("r2") or 0.0), 4),
            })

        # Annualise monthly alpha → yearly %
        portfolio_alpha_annual = portfolio_alpha * 12

        return {
            "n_assets": len(tickers),
            "tickers_missing_metrics": [t for t in tickers if t not in metric_map],
            "portfolio_factor_exposures": {
                name: round(float(portfolio_betas[j]), 4)
                for j, name in enumerate(factor_names)
            },
            "portfolio_alpha_annual_pct": round(portfolio_alpha_annual * 100, 4),
            "assets": asset_detail,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing factor attribution")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Phase 2 — Value-at-Risk (VaR) and Expected Shortfall (CVaR)
# ---------------------------------------------------------------------------

@router.post("/api/portfolio/var-cvar")
async def var_cvar(req: CovarianceMetricsRequest):
    """
    Compute parametric and historical VaR / CVaR (Expected Shortfall)
    at 95% and 99% confidence levels.
    """
    try:
        tickers = [h.ticker for h in req.holdings if h.ticker]
        if not tickers:
            raise HTTPException(status_code=400, detail="No valid tickers provided")

        weights_raw = np.array([h.weight for h in req.holdings], dtype=float)
        weights_raw = np.clip(weights_raw, 0.0, None)
        if float(np.nanmax(weights_raw)) > 1.5:
            weights_raw = weights_raw / 100.0
        w_sum = float(weights_raw.sum())
        if w_sum <= 0:
            raise HTTPException(status_code=400, detail="Holdings must have positive weights")
        weights = weights_raw / w_sum

        # Fetch 1 year of daily prices
        prices, missing = _fetch_price_matrix(tickers, 365)
        if prices.empty or prices.shape[0] < 30:
            raise HTTPException(status_code=422, detail="Insufficient price data for VaR calculation")

        present = [t for t in tickers if t in prices.columns]
        if not present:
            raise HTTPException(status_code=422, detail="No matching tickers in price data")

        present_idx = [tickers.index(t) for t in present]
        w = weights[present_idx]
        w = w / w.sum()

        daily_rets = prices[present].pct_change().dropna()
        port_rets = (daily_rets.values @ w).flatten()

        mu = float(np.mean(port_rets))
        sigma = float(np.std(port_rets, ddof=1))

        from scipy.stats import norm

        results = {}
        for conf, z in [("95", 1.6449), ("99", 2.3263)]:
            # Parametric VaR (assumes normal distribution)
            param_var = -(mu - z * sigma)
            # Parametric CVaR
            param_cvar = -(mu - sigma * float(norm.pdf(z) / (1 - norm.cdf(z))))

            # Historical VaR
            alpha = 1.0 - float(conf) / 100.0
            sorted_rets = np.sort(port_rets)
            var_idx = int(np.floor(alpha * len(sorted_rets)))
            hist_var = -float(sorted_rets[var_idx])
            # Historical CVaR (average of losses beyond VaR)
            tail = sorted_rets[:var_idx + 1]
            hist_cvar = -float(np.mean(tail)) if len(tail) > 0 else hist_var

            results[f"var_{conf}"] = {
                "parametric_daily_pct": round(param_var * 100, 4),
                "parametric_annual_pct": round(param_var * math.sqrt(252) * 100, 4),
                "historical_daily_pct": round(hist_var * 100, 4),
                "historical_annual_pct": round(hist_var * math.sqrt(252) * 100, 4),
            }
            results[f"cvar_{conf}"] = {
                "parametric_daily_pct": round(param_cvar * 100, 4),
                "parametric_annual_pct": round(param_cvar * math.sqrt(252) * 100, 4),
                "historical_daily_pct": round(hist_cvar * 100, 4),
                "historical_annual_pct": round(hist_cvar * math.sqrt(252) * 100, 4),
            }

        return {
            "n_observations": len(port_rets),
            "tickers_missing": missing,
            "daily_mean_return_pct": round(mu * 100, 6),
            "daily_volatility_pct": round(sigma * 100, 6),
            "risk_metrics": results,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing VaR/CVaR")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Phase 2 — Returns-based Style Analysis (Large/Small, Value/Growth)
# ---------------------------------------------------------------------------

@router.post("/api/portfolio/style-analysis")
async def style_analysis(req: RiskDecompositionRequest):
    """
    Sharpe returns-based style analysis.  Regresses portfolio returns
    against size (SMB) and value (HML) FF5 factor betas to classify
    the portfolio along Large/Small and Value/Growth dimensions.
    Also provides per-asset style classification.
    """
    try:
        tickers = [h.ticker.upper() for h in req.holdings]
        weights_raw = np.array([h.weight for h in req.holdings], dtype=float)
        w_sum = weights_raw.sum()
        if w_sum <= 0:
            raise HTTPException(status_code=400, detail="Weights must sum to a positive number")
        weights = weights_raw / w_sum

        # Load FF5 betas from asset_metrics
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT ticker, beta_smb, beta_hml, beta_mkt, market_cap,
                       pe_ratio, expected_return, volatility
                FROM asset_metrics am
                LEFT JOIN stocks s ON s.ticker = am.ticker
                WHERE am.ticker = ANY(%s)
                """,
                (tickers,),
            )
            rows = cur.fetchall()

        metric_map = {r["ticker"]: r for r in rows}

        # Per-asset style classification
        asset_styles = []
        port_smb = 0.0
        port_hml = 0.0
        port_mkt = 0.0

        for i, t in enumerate(tickers):
            m = metric_map.get(t, {})
            smb = float(m.get("beta_smb") or 0.0)
            hml = float(m.get("beta_hml") or 0.0)
            mkt = float(m.get("beta_mkt") or 1.0)

            port_smb += weights[i] * smb
            port_hml += weights[i] * hml
            port_mkt += weights[i] * mkt

            # Classify individual stock
            size_label = "Small" if smb > 0.15 else ("Large" if smb < -0.15 else "Mid")
            value_label = "Value" if hml > 0.15 else ("Growth" if hml < -0.15 else "Blend")

            asset_styles.append({
                "ticker": t,
                "weight": round(float(weights[i]), 6),
                "beta_smb": round(smb, 4),
                "beta_hml": round(hml, 4),
                "size": size_label,
                "value_growth": value_label,
                "style": f"{size_label} {value_label}",
            })

        # Portfolio-level style
        port_size = "Small" if port_smb > 0.1 else ("Large" if port_smb < -0.1 else "Mid")
        port_vg = "Value" if port_hml > 0.1 else ("Growth" if port_hml < -0.1 else "Blend")

        # Style composition percentages
        style_counts = {}
        for a in asset_styles:
            s = a["style"]
            style_counts[s] = style_counts.get(s, 0.0) + a["weight"]

        style_composition = [
            {"style": name, "weight_pct": round(w * 100, 2)}
            for name, w in sorted(style_counts.items(), key=lambda x: -x[1])
        ]

        return {
            "n_assets": len(tickers),
            "tickers_missing_metrics": [t for t in tickers if t not in metric_map],
            "portfolio_style": {
                "size": port_size,
                "value_growth": port_vg,
                "label": f"{port_size} {port_vg}",
                "beta_smb": round(port_smb, 4),
                "beta_hml": round(port_hml, 4),
                "beta_mkt": round(port_mkt, 4),
            },
            "style_composition": style_composition,
            "assets": asset_styles,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing style analysis")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Phase 2 — Brinson-Fachler Performance Attribution
# ---------------------------------------------------------------------------

@router.post("/api/portfolio/brinson-attribution")
async def brinson_attribution(req: BenchmarkAnalyticsRequest):
    """
    Brinson-Fachler performance attribution: decomposes active return into
    allocation effect, selection effect, and interaction effect by sector.

    Requires:
    - Portfolio holdings with weights and an implied period
    - Benchmark ticker (default SPY) used to derive sector returns
    """
    try:
        tickers = [h.ticker.upper() for h in req.holdings]
        weights_raw = np.array([h.weight for h in req.holdings], dtype=float)
        w_sum = weights_raw.sum()
        if w_sum <= 0:
            raise HTTPException(status_code=400, detail="Weights must sum to a positive number")
        weights = weights_raw / w_sum

        period = getattr(req, "period", "1Y") or "1Y"
        period_days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730}.get(period, 365)

        # Load sector assignments for portfolio tickers
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                "SELECT ticker, sector FROM stocks WHERE ticker = ANY(%s)",
                (tickers,),
            )
            rows = cur.fetchall()

        sector_map = {r["ticker"]: r["sector"] or "Other" for r in rows}

        # Fetch portfolio ticker prices
        prices, missing = _fetch_price_matrix(tickers, period_days)
        if prices.empty or prices.shape[0] < 10:
            raise HTTPException(status_code=422, detail="Insufficient price history for attribution")

        present = [t for t in tickers if t in prices.columns]
        if not present:
            raise HTTPException(status_code=422, detail="No matching tickers in price history")

        # Fetch benchmark prices
        bm_ticker = getattr(req, "benchmark_ticker", "SPY") or "SPY"
        bm_prices, _ = _fetch_price_matrix([bm_ticker], period_days)
        if bm_prices.empty or bm_ticker not in bm_prices.columns:
            raise HTTPException(status_code=422, detail=f"No price data for benchmark {bm_ticker}")

        # Compute total-period returns per ticker
        ticker_returns = {}
        for t in present:
            first_p = float(prices[t].dropna().iloc[0])
            last_p = float(prices[t].dropna().iloc[-1])
            ticker_returns[t] = (last_p / first_p - 1.0) if first_p > 0 else 0.0

        bm_total_return = float(
            bm_prices[bm_ticker].dropna().iloc[-1] / bm_prices[bm_ticker].dropna().iloc[0] - 1.0
        )

        # --- Group by sector ---
        # Portfolio: weight and return per sector
        sector_data = {}
        for i, t in enumerate(tickers):
            sec = sector_map.get(t, "Other")
            if sec not in sector_data:
                sector_data[sec] = {"port_weight": 0.0, "port_weighted_return": 0.0}
            sector_data[sec]["port_weight"] += float(weights[i])
            ret = ticker_returns.get(t, 0.0)
            sector_data[sec]["port_weighted_return"] += float(weights[i]) * ret

        # Compute portfolio sector returns
        for sec in sector_data:
            pw = sector_data[sec]["port_weight"]
            sector_data[sec]["port_return"] = (
                sector_data[sec]["port_weighted_return"] / pw if pw > 0 else 0.0
            )

        # Use S&P 500 sector weights as benchmark sector weights
        # (approximate GICS weights — updated periodically)
        sp500_sector_weights = {
            "Technology": 0.30, "Healthcare": 0.13, "Financials": 0.13,
            "Consumer Cyclical": 0.10, "Communication Services": 0.09,
            "Industrials": 0.08, "Consumer Defensive": 0.06,
            "Energy": 0.04, "Utilities": 0.03, "Real Estate": 0.02,
            "Basic Materials": 0.02,
        }
        # Ensure all portfolio sectors have a benchmark weight
        all_sectors = set(sector_data.keys())
        total_bm_w = sum(sp500_sector_weights.get(s, 0.0) for s in all_sectors)
        # For sectors not in S&P map, assign equal share of residual
        unmapped = [s for s in all_sectors if s not in sp500_sector_weights]
        residual = max(0.0, 1.0 - total_bm_w)
        for s in unmapped:
            sp500_sector_weights[s] = residual / len(unmapped) if unmapped else 0.0

        # Normalise benchmark weights to portfolio's sector universe
        bm_weights = {s: sp500_sector_weights.get(s, 0.0) for s in all_sectors}
        bm_sum = sum(bm_weights.values())
        if bm_sum > 0:
            bm_weights = {s: w / bm_sum for s, w in bm_weights.items()}

        # Benchmark sector return → use benchmark total return for all sectors
        # (single-index approach since we don't have sector ETF prices)
        bm_sector_return = bm_total_return

        # --- Brinson-Fachler decomposition ---
        total_port_return = sum(
            sector_data[s]["port_weight"] * sector_data[s]["port_return"]
            for s in sector_data
        )

        sectors_detail = []
        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        for sec in sorted(all_sectors):
            wp = sector_data[sec]["port_weight"]
            wb = bm_weights.get(sec, 0.0)
            rp = sector_data[sec]["port_return"]
            rb = bm_sector_return  # benchmark sector return

            # Brinson-Fachler formulas
            allocation = (wp - wb) * (rb - bm_total_return)
            selection = wb * (rp - rb)
            interaction = (wp - wb) * (rp - rb)

            total_allocation += allocation
            total_selection += selection
            total_interaction += interaction

            sectors_detail.append({
                "sector": sec,
                "port_weight_pct": round(wp * 100, 2),
                "bench_weight_pct": round(wb * 100, 2),
                "port_return_pct": round(rp * 100, 4),
                "bench_return_pct": round(rb * 100, 4),
                "allocation_pct": round(allocation * 100, 4),
                "selection_pct": round(selection * 100, 4),
                "interaction_pct": round(interaction * 100, 4),
            })

        active_return = total_port_return - bm_total_return

        return {
            "period": period,
            "benchmark": bm_ticker,
            "n_assets": len(tickers),
            "tickers_missing": missing,
            "portfolio_return_pct": round(total_port_return * 100, 4),
            "benchmark_return_pct": round(bm_total_return * 100, 4),
            "active_return_pct": round(active_return * 100, 4),
            "total_allocation_pct": round(total_allocation * 100, 4),
            "total_selection_pct": round(total_selection * 100, 4),
            "total_interaction_pct": round(total_interaction * 100, 4),
            "sectors": sectors_detail,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing Brinson-Fachler attribution")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Phase 4 — Smart Rebalancing Calendar (ex-dividend date avoidance)
# ---------------------------------------------------------------------------

@router.post("/api/portfolio/smart-rebalance-calendar")
async def smart_rebalance_calendar(req: DriftMonitorRequest):
    """
    Generate a smart rebalancing calendar for the next 90 days.
    Avoids rebalancing near estimated ex-dividend dates (±2 business days)
    and weekends. Suggests optimal rebalance windows.
    """
    try:
        tickers = [h.ticker.upper() for h in req.holdings]
        if not tickers:
            raise HTTPException(status_code=400, detail="No tickers provided")

        # Fetch dividend yields to estimate ex-div frequency
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                "SELECT ticker, dividend_yield FROM stocks WHERE ticker = ANY(%s)",
                (tickers,),
            )
            rows = cur.fetchall()

        div_map = {r["ticker"]: float(r["dividend_yield"] or 0.0) for r in rows}
        dividend_payers = [t for t in tickers if div_map.get(t, 0.0) > 0.005]

        # Generate business days for next 90 days
        from datetime import timedelta
        today = datetime.utcnow().date()
        cal_days = []
        d = today
        for _ in range(130):  # generate ~90 business days
            d += timedelta(days=1)
            if d.weekday() < 5:  # Mon-Fri
                cal_days.append(d)
            if len(cal_days) >= 90:
                break

        # Estimate ex-dividend dates: most US stocks go ex-div quarterly
        # Common months: Mar/Jun/Sep/Dec (for Q1-Q4) and Jan/Apr/Jul/Oct
        # Approximate: stocks typically go ex-div in the 2nd-3rd week of
        # quarterly months. We mark ±2 business days around mid-month of
        # quarter-end months as ex-div risk windows.
        quarter_months = {3, 6, 9, 12}  # standard quarterly
        alt_quarter_months = {1, 4, 7, 10}  # alt quarterly cycle
        ex_div_risk_dates = set()

        for bd in cal_days:
            # Mark mid-month of quarterly months as potential ex-div periods
            if bd.month in quarter_months and 10 <= bd.day <= 22:
                ex_div_risk_dates.add(bd)
            elif bd.month in alt_quarter_months and 10 <= bd.day <= 22:
                ex_div_risk_dates.add(bd)

        # Expand risk window ±2 business days
        expanded_risk = set()
        for rd in ex_div_risk_dates:
            expanded_risk.add(rd)
            d_minus = rd
            d_plus = rd
            for _ in range(2):
                d_minus -= timedelta(days=1)
                while d_minus.weekday() >= 5:
                    d_minus -= timedelta(days=1)
                expanded_risk.add(d_minus)
                d_plus += timedelta(days=1)
                while d_plus.weekday() >= 5:
                    d_plus += timedelta(days=1)
                expanded_risk.add(d_plus)

        # Build calendar with recommendations
        calendar = []
        rebalance_windows = []
        current_window = None

        for bd in cal_days:
            is_ex_div_risk = bd in expanded_risk and len(dividend_payers) > 0
            is_month_end = bd == cal_days[-1] or (
                len(calendar) < len(cal_days) - 1 and
                bd.month != (bd + timedelta(days=3)).month
            )
            is_quarter_end = is_month_end and bd.month in {3, 6, 9, 12}

            # Scoring: higher = better rebalance day
            score = 50  # baseline
            if is_ex_div_risk:
                score -= 40  # avoid ex-div windows
            if is_month_end:
                score += 20  # prefer month-end alignment
            if is_quarter_end:
                score += 10  # prefer quarter-end
            if bd.weekday() in (0, 4):
                score -= 5  # slight penalty for Mon/Fri (higher vol)

            status = "recommended" if score >= 50 else ("caution" if score >= 30 else "avoid")

            entry = {
                "date": bd.isoformat(),
                "weekday": bd.strftime("%A"),
                "status": status,
                "score": score,
                "is_ex_div_risk": is_ex_div_risk,
                "is_month_end": is_month_end,
                "is_quarter_end": is_quarter_end,
            }
            calendar.append(entry)

            # Track recommended windows
            if status == "recommended":
                if current_window is None:
                    current_window = {"start": bd.isoformat(), "end": bd.isoformat(), "days": 1}
                else:
                    current_window["end"] = bd.isoformat()
                    current_window["days"] += 1
            else:
                if current_window and current_window["days"] >= 2:
                    rebalance_windows.append(current_window)
                current_window = None

        if current_window and current_window["days"] >= 2:
            rebalance_windows.append(current_window)

        # Next recommended rebalance date
        next_recommended = next(
            (e["date"] for e in calendar if e["status"] == "recommended"), None
        )

        return {
            "n_tickers": len(tickers),
            "dividend_payers": dividend_payers,
            "n_dividend_payers": len(dividend_payers),
            "next_recommended_date": next_recommended,
            "rebalance_windows": rebalance_windows[:8],
            "calendar": calendar,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing smart rebalance calendar")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Personal Performance Dashboard
# ---------------------------------------------------------------------------

@router.get("/api/portfolio-performance/{portfolio_id}")
async def get_portfolio_performance(
    portfolio_id: int,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Compute actual vs projected performance for a saved portfolio.

    Uses historical prices from creation date to now, comparing actual
    portfolio value (holding weights × real prices) against projected value
    (compounding expected return from creation date).
    """
    from security import get_user_from_token, resolve_auth_token

    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                "SELECT id, data, created_at FROM saved_portfolios WHERE id = %s AND user_id = %s",
                (portfolio_id, user["id"]),
            )
            portfolio = cur.fetchone()
            if not portfolio:
                raise HTTPException(status_code=404, detail="Portfolio not found")

            pdata = portfolio["data"]
            if isinstance(pdata, str):
                import json as _json
                pdata = _json.loads(pdata)

            holdings = pdata.get("holdings", [])
            if not holdings:
                raise HTTPException(status_code=400, detail="Portfolio has no holdings")

            investment_amount = float(pdata.get("investment_amount", 0))
            if investment_amount <= 0:
                investment_amount = sum(float(h.get("value", 0)) for h in holdings)
            if investment_amount <= 0:
                investment_amount = 10000.0

            # Compute weights
            tickers = [h["ticker"] for h in holdings if h.get("ticker")]
            weights = {}
            total_weight = sum(float(h.get("weight", 0)) for h in holdings)
            for h in holdings:
                t = h.get("ticker")
                if t and total_weight > 0:
                    weights[t] = float(h.get("weight", 0)) / total_weight

            # Expected annual return (weighted average)
            expected_annual = 0.0
            for h in holdings:
                t = h.get("ticker")
                er = h.get("expected_return")
                if t and er is not None:
                    expected_annual += weights.get(t, 0) * float(er) / 100.0

            created_date = portfolio["created_at"]
            if hasattr(created_date, "date"):
                created_date = created_date.date()

            # Fetch historical prices from creation date
            cur.execute(
                """
                SELECT date, ticker, close FROM price_history
                WHERE ticker = ANY(%s) AND date >= %s
                ORDER BY date ASC
                """,
                (tickers, created_date),
            )
            rows = cur.fetchall()

        if not rows:
            return {"error": "No price data available after portfolio creation date", "series": []}

        import pandas as pd

        pdf = pd.DataFrame(rows)
        pivot = pdf.pivot(index="date", columns="ticker", values="close")
        pivot = pivot.ffill().bfill()

        # Normalize prices to base-1 on first available date
        base_prices = pivot.iloc[0]
        normalized = pivot.div(base_prices)

        # Compute portfolio value series
        series = []
        daily_expected = (1 + expected_annual) ** (1 / 252)
        for i, (date, row) in enumerate(normalized.iterrows()):
            actual_val = 0.0
            for t in tickers:
                if t in row.index and pd.notna(row[t]):
                    actual_val += weights.get(t, 0) * float(row[t])
            actual_val *= investment_amount

            projected_val = investment_amount * (daily_expected ** i)

            series.append({
                "date": date.isoformat() if hasattr(date, "isoformat") else str(date),
                "actual": round(actual_val, 2),
                "projected": round(projected_val, 2),
            })

        # Summary stats
        if len(series) >= 2:
            total_return_pct = (series[-1]["actual"] / investment_amount - 1) * 100
            projected_return_pct = (series[-1]["projected"] / investment_amount - 1) * 100
            alpha = total_return_pct - projected_return_pct
        else:
            total_return_pct = 0
            projected_return_pct = 0
            alpha = 0

        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": pdata.get("name", f"Portfolio #{portfolio_id}"),
            "investment_amount": investment_amount,
            "created_date": str(created_date),
            "days_tracked": len(series),
            "current_actual_value": series[-1]["actual"] if series else investment_amount,
            "current_projected_value": series[-1]["projected"] if series else investment_amount,
            "total_return_pct": round(total_return_pct, 2),
            "projected_return_pct": round(projected_return_pct, 2),
            "alpha_pct": round(alpha, 2),
            "series": series,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing portfolio performance")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Aggregate Dashboard Performance — all portfolios vs S&P 500
# ---------------------------------------------------------------------------

@router.get("/api/dashboard-performance")
async def get_dashboard_performance(
    months: int = Query(6, ge=1, le=12),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Compute aggregate actual performance of all saved portfolios vs SPY (S&P 500).

    Returns a time series of the combined portfolio value and SPY benchmark value,
    both starting from the total invested amount on the earliest portfolio creation date.
    """
    from security import get_user_from_token, resolve_auth_token
    import pandas as pd
    from datetime import timedelta

    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                "SELECT id, data, created_at FROM saved_portfolios WHERE user_id = %s ORDER BY created_at ASC",
                (user["id"],),
            )
            all_portfolios = cur.fetchall()

            if not all_portfolios:
                return {"series": [], "total_invested": 0, "current_value": 0, "sp500_value": 0}

            # Parse each portfolio's holdings and compute per-portfolio info
            portfolio_infos = []
            all_tickers = set()
            for port in all_portfolios:
                pdata = port["data"]
                if isinstance(pdata, str):
                    import json as _json
                    pdata = _json.loads(pdata)

                holdings = pdata.get("holdings", [])
                if not holdings:
                    continue

                investment = float(pdata.get("investment_amount", 0))
                if investment <= 0:
                    investment = sum(float(h.get("value", 0)) for h in holdings)
                if investment <= 0:
                    investment = 10000.0

                tickers = [h["ticker"] for h in holdings if h.get("ticker")]
                total_weight = sum(float(h.get("weight", 0)) for h in holdings)
                weights = {}
                for h in holdings:
                    t = h.get("ticker")
                    if t and total_weight > 0:
                        weights[t] = float(h.get("weight", 0)) / total_weight

                created = port["created_at"]
                if hasattr(created, "date"):
                    created = created.date()

                portfolio_infos.append({
                    "investment": investment,
                    "tickers": tickers,
                    "weights": weights,
                    "created_date": created,
                })
                all_tickers.update(tickers)

            if not portfolio_infos:
                return {"series": [], "total_invested": 0, "current_value": 0, "sp500_value": 0}

            # Determine date range: use the months param back from today
            from datetime import date as date_type
            end_date = date_type.today()
            start_date = end_date - timedelta(days=months * 30)

            # Use the earliest portfolio creation as an alternative start if all portfolios are newer
            earliest_created = min(p["created_date"] for p in portfolio_infos)
            if earliest_created > start_date:
                start_date = earliest_created

            all_tickers_list = list(all_tickers)
            all_tickers_list.append("SPY")  # Always include SPY for benchmark

            cur.execute(
                """
                SELECT date, ticker, close FROM price_history
                WHERE ticker = ANY(%s) AND date >= %s
                ORDER BY date ASC
                """,
                (all_tickers_list, start_date),
            )
            rows = cur.fetchall()

        if not rows:
            return {"series": [], "total_invested": 0, "current_value": 0, "sp500_value": 0}

        pdf = pd.DataFrame(rows)
        pivot = pdf.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
        pivot = pivot.sort_index().ffill().bfill()

        if pivot.empty:
            return {"series": [], "total_invested": 0, "current_value": 0, "sp500_value": 0}

        # Build aggregate portfolio value for each date
        total_invested = sum(p["investment"] for p in portfolio_infos)
        dates = pivot.index.tolist()

        series = []
        for date in dates:
            row = pivot.loc[date]

            # Sum each portfolio's actual value on this date
            agg_value = 0.0
            for pinfo in portfolio_infos:
                # Only include portfolio if it was created on or before this date
                if pinfo["created_date"] > (date.date() if hasattr(date, "date") else date):
                    # Portfolio not yet created — add its investment at face value
                    agg_value += pinfo["investment"]
                    continue

                # Get base prices for this portfolio (first date on or after creation)
                port_base_date = None
                for d in dates:
                    d_date = d.date() if hasattr(d, "date") else d
                    if d_date >= pinfo["created_date"]:
                        port_base_date = d
                        break
                if port_base_date is None:
                    agg_value += pinfo["investment"]
                    continue

                base_row = pivot.loc[port_base_date]
                port_val = 0.0
                for t in pinfo["tickers"]:
                    if t in row.index and t in base_row.index:
                        base_price = float(base_row[t]) if pd.notna(base_row[t]) else 0
                        cur_price = float(row[t]) if pd.notna(row[t]) else 0
                        if base_price > 0:
                            port_val += pinfo["weights"].get(t, 0) * (cur_price / base_price)
                        else:
                            port_val += pinfo["weights"].get(t, 0)
                    else:
                        port_val += pinfo["weights"].get(t, 0)

                agg_value += port_val * pinfo["investment"]

            # SPY benchmark: invest total_invested at SPY on start_date, track growth
            spy_value = total_invested
            if "SPY" in row.index and "SPY" in pivot.loc[dates[0]].index:
                spy_base = float(pivot.loc[dates[0]]["SPY"])
                spy_cur = float(row["SPY"]) if pd.notna(row["SPY"]) else spy_base
                if spy_base > 0:
                    spy_value = total_invested * (spy_cur / spy_base)

            date_str = date.isoformat() if hasattr(date, "isoformat") else str(date)
            series.append({
                "date": date_str,
                "portfolio": round(agg_value, 2),
                "sp500": round(spy_value, 2),
            })

        current_value = series[-1]["portfolio"] if series else total_invested
        sp500_value = series[-1]["sp500"] if series else total_invested

        return {
            "total_invested": round(total_invested, 2),
            "current_value": round(current_value, 2),
            "sp500_value": round(sp500_value, 2),
            "portfolio_return_pct": round((current_value / total_invested - 1) * 100, 2) if total_invested > 0 else 0,
            "sp500_return_pct": round((sp500_value / total_invested - 1) * 100, 2) if total_invested > 0 else 0,
            "series": series,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error computing dashboard performance")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Goals & Targets with Auto-Rebalancing Suggestions
# ---------------------------------------------------------------------------

@router.get("/api/goals")
async def get_goals(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Get all portfolio goals for the current user."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """SELECT g.id, g.name, g.portfolio_id, g.target_allocations,
                      g.rebalance_threshold, g.created_at, g.updated_at,
                      sp.name AS portfolio_name
               FROM portfolio_goals g
               LEFT JOIN saved_portfolios sp ON sp.id = g.portfolio_id
               WHERE g.user_id = %s ORDER BY g.created_at DESC""",
            (user["id"],),
        )
        goals = cur.fetchall()

    return {
        "goals": [
            {
                "id": g["id"],
                "name": g["name"],
                "portfolio_id": g["portfolio_id"],
                "portfolio_name": g["portfolio_name"],
                "target_allocations": g["target_allocations"],
                "rebalance_threshold": g["rebalance_threshold"],
                "created_at": g["created_at"].isoformat(),
                "updated_at": g["updated_at"].isoformat(),
            }
            for g in goals
        ]
    }


@router.post("/api/goals")
async def create_goal(
    body: PortfolioGoalRequest,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Create a portfolio goal with target allocations."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    total_weight = sum(body.target_allocations.values())
    if abs(total_weight - 100.0) > 1.0:
        raise HTTPException(status_code=400, detail=f"Target allocations must sum to ~100% (got {total_weight:.1f}%)")

    with get_cursor(dict_cursor=True) as (conn, cur):
        # Limit goals per user
        cur.execute("SELECT COUNT(*) AS cnt FROM portfolio_goals WHERE user_id = %s", (user["id"],))
        if cur.fetchone()["cnt"] >= 20:
            raise HTTPException(status_code=400, detail="Maximum 20 goals allowed")

        if body.portfolio_id:
            cur.execute(
                "SELECT id FROM saved_portfolios WHERE id = %s AND user_id = %s",
                (body.portfolio_id, user["id"]),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Portfolio not found")

        cur.execute(
            """INSERT INTO portfolio_goals (user_id, name, portfolio_id, target_allocations, rebalance_threshold)
               VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at""",
            (user["id"], body.name, body.portfolio_id, Json(body.target_allocations), body.rebalance_threshold),
        )
        row = cur.fetchone()
        conn.commit()

    return {"id": row["id"], "name": body.name, "created_at": row["created_at"].isoformat()}


@router.delete("/api/goals/{goal_id}")
async def delete_goal(
    goal_id: int,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Delete a portfolio goal."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_cursor(dict_cursor=True) as (conn, cur):
        cur.execute(
            "DELETE FROM portfolio_goals WHERE id = %s AND user_id = %s RETURNING id",
            (goal_id, user["id"]),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Goal not found")
        conn.commit()

    return {"success": True}


@router.get("/api/goals/{goal_id}/rebalance")
async def get_rebalance_suggestions(
    goal_id: int,
    portfolio_value: float = 100000.0,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Compute rebalancing trades to bring portfolio back to target allocations.

    Compares current market-value weights vs target weights and returns
    suggested buy/sell trades with dollar amounts and share counts.
    """
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            "SELECT target_allocations, rebalance_threshold, portfolio_id FROM portfolio_goals WHERE id = %s AND user_id = %s",
            (goal_id, user["id"]),
        )
        goal = cur.fetchone()
        if not goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        targets = goal["target_allocations"]  # {ticker: weight_pct}
        threshold = goal["rebalance_threshold"]
        tickers = list(targets.keys())

        # Get current prices
        cur.execute(
            """SELECT DISTINCT ON (ticker) ticker, close
               FROM price_history WHERE ticker = ANY(%s)
               ORDER BY ticker, date DESC""",
            (tickers,),
        )
        prices = {r["ticker"]: float(r["close"]) for r in cur.fetchall()}

        # If linked to a portfolio, get current holdings
        current_weights = {}
        if goal["portfolio_id"]:
            cur.execute(
                "SELECT data FROM saved_portfolios WHERE id = %s AND user_id = %s",
                (goal["portfolio_id"], user["id"]),
            )
            prow = cur.fetchone()
            if prow:
                pdata = prow["data"]
                if isinstance(pdata, str):
                    pdata = json.loads(pdata)
                holdings = pdata.get("holdings", [])
                total_w = sum(float(h.get("weight", 0)) for h in holdings)
                if total_w > 0:
                    for h in holdings:
                        t = h.get("ticker")
                        if t:
                            current_weights[t] = float(h.get("weight", 0)) / total_w * 100

    # If no current weights from portfolio, assume equal weights at current prices
    if not current_weights:
        if prices:
            equal = 100.0 / len(prices)
            current_weights = {t: equal for t in prices}

    trades = []
    needs_rebalance = False
    max_drift = 0.0

    for ticker in tickers:
        target_pct = targets.get(ticker, 0)
        current_pct = current_weights.get(ticker, 0)
        drift = target_pct - current_pct
        abs_drift = abs(drift)
        max_drift = max(max_drift, abs_drift)

        if abs_drift > threshold:
            needs_rebalance = True

        price = prices.get(ticker, 0)
        trade_value = portfolio_value * drift / 100.0
        shares = int(trade_value / price) if price > 0 else 0

        trades.append({
            "ticker": ticker,
            "target_pct": round(target_pct, 2),
            "current_pct": round(current_pct, 2),
            "drift_pct": round(drift, 2),
            "action": "buy" if drift > 0 else "sell" if drift < 0 else "hold",
            "trade_value": round(abs(trade_value), 2),
            "shares": abs(shares),
            "price": round(price, 2),
        })

    trades.sort(key=lambda t: abs(t["drift_pct"]), reverse=True)

    return {
        "goal_id": goal_id,
        "portfolio_value": portfolio_value,
        "needs_rebalance": needs_rebalance,
        "max_drift_pct": round(max_drift, 2),
        "threshold_pct": threshold,
        "trades": trades,
    }
