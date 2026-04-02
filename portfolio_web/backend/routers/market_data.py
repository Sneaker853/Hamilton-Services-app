from datetime import timedelta
import logging
import math
from typing import Optional

import re

from fastapi import APIRouter, HTTPException, Header, Cookie, Query

from db import get_cursor
from cache_store import TTLCache
from config import MARKET_DATA_CACHE_TTL_SECONDS
from config import SESSION_COOKIE_NAME
from security import require_admin_user, resolve_auth_token, get_user_from_token
from schemas import WatchlistAddRequest, PriceAlertRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["market-data"])
market_data_cache = TTLCache(MARKET_DATA_CACHE_TTL_SECONDS)
_schema_cache: dict[str, set[str]] = {}
_table_cache: dict[str, bool] = {}


EXCHANGE_MAP = {
    "NYQ": "NYSE",
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",   # NASDAQ Capital Market → NASDAQ
    "NCM": "NASDAQ",   # NASDAQ Capital Market (small cap) → NASDAQ
    "NIM": "NASDAQ",   # NASDAQ Global Market → NASDAQ
    "YHD": "OTC",      # Yahoo Finance default → OTC
    "PCX": "NYSE Arca",
    "ASE": "NYSE American",
    "BTS": "CBOE",
    "PNK": "OTC",
    "OQB": "OTC",
    "PINX": "OTC",
    "GREY": "OTC",
}


def _table_exists(table_name: str) -> bool:
    cached = _table_cache.get(table_name)
    if cached is True:
        return True

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            ) AS exists
            """,
            (table_name,),
        )
        exists = bool(cur.fetchone()["exists"])

    _table_cache[table_name] = exists
    return exists


def _table_columns(table_name: str) -> set[str]:
    cached_columns = _schema_cache.get(table_name)
    if cached_columns:
        return cached_columns

    if not _table_exists(table_name):
        _schema_cache.pop(table_name, None)
        _schema_cache[table_name] = set()
        return _schema_cache[table_name]

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            (table_name,),
        )
        columns = {row["column_name"] for row in cur.fetchall()}

    _schema_cache[table_name] = columns
    return columns


def _stock_select_expr(stock_columns: set[str], column: str, fallback: str = "NULL") -> str:
    return f"s.{column}" if column in stock_columns else fallback


def _metric_select_expr(asset_metrics_exists: bool, asset_metric_columns: set[str], column: str) -> str:
    if asset_metrics_exists and column in asset_metric_columns:
        return f"m.{column}"
    return "NULL"


@router.get("/api/stocks/search")
async def search_stocks(q: str = Query(..., min_length=1, max_length=50), limit: int = Query(10, ge=1, le=50)):
    sanitized = re.sub(r'[^a-zA-Z0-9 .\-]', '', q).strip()
    if not sanitized:
        return {"results": []}

    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT ticker, name, exchange, sector
                FROM stocks
                WHERE ticker ILIKE %s OR name ILIKE %s
                ORDER BY
                    CASE WHEN ticker ILIKE %s THEN 0 ELSE 1 END,
                    ticker
                LIMIT %s
                """,
                (f"{sanitized}%", f"%{sanitized}%", f"{sanitized}%", limit),
            )
            results = cur.fetchall()

        suggestions = []
        for row in results:
            r = dict(row)
            if r.get("exchange"):
                r["exchange"] = EXCHANGE_MAP.get(r["exchange"], r["exchange"])
            suggestions.append(r)

        return {"results": suggestions}
    except Exception:
        logger.exception("Error in stock search")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/stocks/summary")
async def get_stocks_summary():
    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(DISTINCT exchange) as exchanges,
                    COUNT(DISTINCT sector) as sectors,
                    AVG(pe_ratio) as avg_pe,
                    AVG(roe) as avg_roe,
                    AVG(beta) as avg_beta
                FROM stocks
                """
            )
            stats = cur.fetchone()

            cur.execute("SELECT DISTINCT exchange FROM stocks WHERE exchange IS NOT NULL ORDER BY exchange")
            exchanges = [row["exchange"] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT sector FROM stocks WHERE sector IS NOT NULL ORDER BY sector")
            sectors = [row["sector"] for row in cur.fetchall()]

        return {
            "total_stocks": stats["total"],
            "exchanges": exchanges,
            "sectors": sectors,
            "statistics": {
                "avg_pe": float(stats["avg_pe"]) if stats["avg_pe"] else None,
                "avg_roe": float(stats["avg_roe"]) if stats["avg_roe"] else None,
                "avg_beta": float(stats["avg_beta"]) if stats["avg_beta"] else None,
            },
        }
    except Exception:
        logger.exception("Error fetching stocks summary")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/stocks/all")
async def get_all_stocks(page: Optional[int] = None, page_size: int = 100):
    # When no page is specified, return all stocks (backward-compatible)
    if page is None:
        cached = market_data_cache.get("stocks_all")
        if cached is not None:
            return cached

    if page is not None and page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if page_size < 1 or page_size > 500:
        raise HTTPException(status_code=400, detail="page_size must be between 1 and 500")

    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            base_query = """
                SELECT
                    s.ticker,
                    s.name,
                    s.exchange,
                    s.sector,
                    s.pe_ratio,
                    s.roe,
                    s.beta,
                    s.market_cap,
                    s.revenue,
                    s.dividend_yield,
                    COALESCE(s.asset_class, 'stock') AS asset_class,
                    ph.close AS current_price,
                    m.expected_return,
                    m.volatility
                FROM stocks s
                LEFT JOIN asset_metrics m ON m.ticker = s.ticker
                LEFT JOIN LATERAL (
                    SELECT close FROM price_history
                    WHERE ticker = s.ticker
                    ORDER BY date DESC LIMIT 1
                ) ph ON true
                ORDER BY s.ticker
            """

            if page is not None:
                offset = (page - 1) * page_size
                cur.execute(base_query + " LIMIT %s OFFSET %s", (page_size, offset))
            else:
                cur.execute(base_query)

            stocks = cur.fetchall()

            cur.execute("SELECT COUNT(*) AS total FROM stocks")
            total_count = cur.fetchone()["total"]

            cur.execute(
                """
                SELECT
                    MAX(latest_date) AS latest_price_date,
                    COUNT(*) AS tickers_with_price,
                    COUNT(*) FILTER (
                        WHERE latest_date = (SELECT MAX(date) FROM price_history)
                    ) AS latest_price_ticker_count
                FROM (
                    SELECT ticker, MAX(date) AS latest_date
                    FROM price_history
                    GROUP BY ticker
                ) t
                """
            )
            freshness = cur.fetchone()

        stocks_list = []
        for stock in stocks:
            stock_dict = dict(stock)
            if stock_dict.get("exchange"):
                stock_dict["exchange"] = EXCHANGE_MAP.get(stock_dict["exchange"], stock_dict["exchange"])
            if stock_dict.get("current_price"):
                stock_dict["current_price"] = float(stock_dict["current_price"])

            for key in ["expected_return", "volatility", "pe_ratio", "roe", "beta", "market_cap", "revenue", "dividend_yield", "confidence_score", "residual_std"]:
                if stock_dict.get(key) is not None:
                    val = stock_dict[key]
                    if isinstance(val, (float, int)) and (math.isinf(val) or math.isnan(val)):
                        stock_dict[key] = None

            stocks_list.append(stock_dict)

        result = {
            "stocks": stocks_list,
            "total": total_count,
            "latest_price_date": freshness["latest_price_date"].isoformat() if freshness and freshness.get("latest_price_date") else None,
            "latest_price_ticker_count": int(freshness["latest_price_ticker_count"]) if freshness and freshness.get("latest_price_ticker_count") is not None else 0,
            "tickers_with_price": int(freshness["tickers_with_price"]) if freshness and freshness.get("tickers_with_price") is not None else 0,
        }

        if page is not None:
            result["page"] = page
            result["page_size"] = page_size
            result["total_pages"] = math.ceil(total_count / page_size)
        else:
            market_data_cache.set("stocks_all", result)

        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching securities")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/etfs/all")
async def get_all_etfs():
    cached = market_data_cache.get("etfs_all")
    if cached is not None:
        return cached

    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT
                    s.ticker,
                    s.name,
                    s.exchange,
                    s.sector,
                    s.pe_ratio,
                    s.roe,
                    s.beta,
                    s.market_cap,
                    s.revenue,
                    s.dividend_yield,
                    s.asset_class,
                    ph.close AS current_price,
                    m.expected_return,
                    m.volatility
                FROM stocks s
                LEFT JOIN asset_metrics m ON m.ticker = s.ticker
                LEFT JOIN LATERAL (
                    SELECT close FROM price_history
                    WHERE ticker = s.ticker
                    ORDER BY date DESC LIMIT 1
                ) ph ON true
                WHERE LOWER(COALESCE(s.asset_class, '')) = 'etf'
                ORDER BY s.ticker
                """
            )
            etfs = cur.fetchall()

        etfs_list = []
        for etf in etfs:
            etf_dict = dict(etf)
            if etf_dict.get("current_price"):
                etf_dict["current_price"] = float(etf_dict["current_price"])
            for key in ["expected_return", "volatility", "pe_ratio", "roe", "beta", "market_cap", "revenue", "dividend_yield", "confidence_score", "residual_std"]:
                if etf_dict.get(key) is not None:
                    val = etf_dict[key]
                    if isinstance(val, (float, int)) and (math.isinf(val) or math.isnan(val)):
                        etf_dict[key] = None
            etfs_list.append(etf_dict)

        result = {"etfs": etfs_list, "total": len(etfs_list)}
        market_data_cache.set("etfs_all", result)
        return result
    except Exception:
        logger.exception("Error fetching ETFs")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/bonds/all")
async def get_all_bonds():
    cached = market_data_cache.get("bonds_all")
    if cached is not None:
        return cached

    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT
                    s.ticker,
                    s.name,
                    s.exchange,
                    s.sector,
                    s.pe_ratio,
                    s.roe,
                    s.beta,
                    s.market_cap,
                    s.revenue,
                    s.dividend_yield,
                    s.asset_class,
                    ph.close AS current_price,
                    m.expected_return,
                    m.volatility
                FROM stocks s
                LEFT JOIN asset_metrics m ON m.ticker = s.ticker
                LEFT JOIN LATERAL (
                    SELECT close FROM price_history
                    WHERE ticker = s.ticker
                    ORDER BY date DESC LIMIT 1
                ) ph ON true
                WHERE LOWER(COALESCE(s.asset_class, '')) = 'bond'
                ORDER BY s.ticker
                """
            )
            bonds = cur.fetchall()

        bonds_list = []
        for bond in bonds:
            bond_dict = dict(bond)
            if bond_dict.get("current_price"):
                bond_dict["current_price"] = float(bond_dict["current_price"])
            for key in ["expected_return", "volatility", "pe_ratio", "roe", "beta", "market_cap", "revenue", "dividend_yield", "confidence_score", "residual_std"]:
                if bond_dict.get(key) is not None:
                    val = bond_dict[key]
                    if isinstance(val, (float, int)) and (math.isinf(val) or math.isnan(val)):
                        bond_dict[key] = None
            bonds_list.append(bond_dict)

        result = {"bonds": bonds_list, "total": len(bonds_list)}
        market_data_cache.set("bonds_all", result)
        return result
    except Exception:
        logger.exception("Error fetching bonds")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/debug/db-stats")
async def get_db_stats(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    require_admin_user(resolve_auth_token(x_auth_token, session_cookie))
    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute("SELECT COUNT(*) as total FROM stocks")
            total = cur.fetchone()["total"]

            cur.execute(
                """
                SELECT COALESCE(asset_class, 'NULL') as asset_class, COUNT(*) as count
                FROM stocks
                GROUP BY asset_class
                """
            )
            distribution = cur.fetchall()

            cur.execute("SELECT ticker, name, asset_class FROM stocks LIMIT 5")
            samples = cur.fetchall()

        return {
            "total_records": total,
            "asset_class_distribution": distribution,
            "sample_records": samples,
        }
    except Exception:
        logger.exception("Error getting DB stats")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/stocks/filters/options")
async def get_filter_options():
    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT DISTINCT sector
                FROM stocks
                WHERE sector IS NOT NULL AND sector != 'Unknown'
                ORDER BY sector
                """
            )
            sectors = [row["sector"] for row in cur.fetchall()]

            cur.execute(
                """
                SELECT DISTINCT exchange
                FROM stocks
                WHERE exchange IS NOT NULL AND exchange != 'UNKNOWN'
                ORDER BY exchange
                """
            )

            exchanges = []
            seen = set()
            for row in cur.fetchall():
                normalized = EXCHANGE_MAP.get(row["exchange"], row["exchange"])
                if normalized not in seen:
                    exchanges.append(normalized)
                    seen.add(normalized)

        exchanges.sort()
        return {"sectors": sectors, "exchanges": exchanges}
    except Exception:
        logger.exception("Error fetching filter options")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/stocks/{ticker}")
async def get_stock_details(ticker: str):
    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT s.ticker, s.name, s.exchange, s.sector, s.pe_ratio, s.roe, s.beta,
                       s.market_cap, s.revenue, s.dividend_yield, s.asset_class,
                       s.debt_to_equity, s.esg_score, s.carbon_intensity,
                       m.expected_return, m.volatility, m.alpha, m.r2,
                       m.beta_mkt, m.sample_months, m.confidence_score
                FROM stocks s
                LEFT JOIN asset_metrics m ON m.ticker = s.ticker
                WHERE s.ticker = %s
                """,
                (ticker.upper(),),
            )
            stock = cur.fetchone()
            if not stock:
                raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

            cur.execute(
                """
                SELECT close, date, volume
                FROM price_history
                WHERE ticker = %s
                ORDER BY date DESC
                LIMIT 1
                """,
                (ticker.upper(),),
            )
            latest_price = cur.fetchone()

        result = dict(stock)
        if result.get("exchange"):
            result["exchange"] = EXCHANGE_MAP.get(result["exchange"], result["exchange"])

        # Sanitise floats
        for key in ["expected_return", "volatility", "alpha", "r2", "beta_mkt",
                    "confidence_score", "pe_ratio", "roe", "beta", "market_cap",
                    "revenue", "dividend_yield", "debt_to_equity", "esg_score",
                    "carbon_intensity"]:
            val = result.get(key)
            if isinstance(val, (float, int)) and (math.isinf(val) or math.isnan(val)):
                result[key] = None

        if latest_price:
            result["current_price"] = float(latest_price["close"])
            result["last_updated"] = latest_price["date"].isoformat()
            result["volume"] = int(latest_price["volume"]) if latest_price["volume"] else None
        else:
            result["current_price"] = None
            result["volume"] = None

        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching stock details")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/stocks/{ticker}/history")
async def get_stock_history(ticker: str, period: str = "1Y"):
    try:
        period_map = {
            "1D": 1,
            "1W": 7,
            "1M": 30,
            "3M": 90,
            "6M": 180,
            "1Y": 365,
            "5Y": 1825,
            "MAX": 3650,
        }

        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT MAX(date) as latest_date, MIN(date) as earliest_date
                FROM price_history
                WHERE ticker = %s
                """,
                (ticker.upper(),),
            )
            date_row = cur.fetchone()
            if not date_row or not date_row["latest_date"]:
                raise HTTPException(status_code=404, detail=f"No price history found for {ticker}")

            latest_date = date_row["latest_date"]
            earliest_date = date_row["earliest_date"]

            days = period_map.get(period.upper(), 365)
            start_date = max(latest_date - timedelta(days=days), earliest_date)

            cur.execute(
                """
                SELECT date, open, high, low, close, volume
                FROM price_history
                WHERE ticker = %s AND date >= %s AND date <= %s
                ORDER BY date ASC
                """,
                (ticker.upper(), start_date, latest_date),
            )
            rows = cur.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail=f"No price history found for {ticker} in the requested period")

        history = [
            {
                "date": row["date"].isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]) if row["volume"] else 0,
            }
            for row in rows
        ]

        return {"ticker": ticker.upper(), "period": period, "data": history}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching price history")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Watchlist / Favorites
# ---------------------------------------------------------------------------

@router.get("/api/watchlist")
async def get_watchlist(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Get user's watchlist with current prices."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT w.id, w.ticker, w.notes, w.added_at,
                   s.name, s.sector, s.exchange, s.pe_ratio, s.beta,
                   s.market_cap, s.dividend_yield
            FROM user_watchlist w
            LEFT JOIN stocks s ON s.ticker = w.ticker
            WHERE w.user_id = %s
            ORDER BY w.added_at DESC
            """,
            (user["id"],),
        )
        rows = cur.fetchall()

        # Get latest prices for all watchlist tickers
        tickers = [r["ticker"] for r in rows]
        price_map = {}
        if tickers:
            cur.execute(
                """
                SELECT DISTINCT ON (ticker) ticker, close, date
                FROM price_history
                WHERE ticker = ANY(%s)
                ORDER BY ticker, date DESC
                """,
                (tickers,),
            )
            for pr in cur.fetchall():
                price_map[pr["ticker"]] = {
                    "price": float(pr["close"]),
                    "date": pr["date"].isoformat(),
                }

    items = []
    for r in rows:
        item = {
            "id": r["id"],
            "ticker": r["ticker"],
            "name": r.get("name"),
            "sector": r.get("sector"),
            "exchange": r.get("exchange"),
            "pe_ratio": float(r["pe_ratio"]) if r.get("pe_ratio") else None,
            "beta": float(r["beta"]) if r.get("beta") else None,
            "market_cap": float(r["market_cap"]) if r.get("market_cap") else None,
            "dividend_yield": float(r["dividend_yield"]) if r.get("dividend_yield") else None,
            "notes": r.get("notes"),
            "added_at": r["added_at"].isoformat() if r.get("added_at") else None,
        }
        p = price_map.get(r["ticker"])
        if p:
            item["current_price"] = p["price"]
            item["price_date"] = p["date"]
        items.append(item)

    return {"items": items, "count": len(items)}


@router.post("/api/watchlist")
async def add_to_watchlist(
    req: WatchlistAddRequest,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Add a ticker to user's watchlist."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    ticker = req.ticker.upper().strip()

    with get_cursor(dict_cursor=True) as (conn, cur):
        # Check if ticker exists in stocks table
        cur.execute("SELECT ticker FROM stocks WHERE ticker = %s", (ticker,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")

        # Watchlist limit per user (100 max)
        cur.execute("SELECT COUNT(*) as cnt FROM user_watchlist WHERE user_id = %s", (user["id"],))
        count = cur.fetchone()["cnt"]
        if count >= 100:
            raise HTTPException(status_code=400, detail="Watchlist limit reached (100 tickers)")

        cur.execute(
            """
            INSERT INTO user_watchlist (user_id, ticker, notes)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, ticker) DO UPDATE SET notes = EXCLUDED.notes
            RETURNING id, added_at
            """,
            (user["id"], ticker, req.notes),
        )
        row = cur.fetchone()
        conn.commit()

    return {
        "id": row["id"],
        "ticker": ticker,
        "notes": req.notes,
        "added_at": row["added_at"].isoformat(),
    }


@router.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Remove a ticker from user's watchlist."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_cursor(dict_cursor=True) as (conn, cur):
        cur.execute(
            "DELETE FROM user_watchlist WHERE user_id = %s AND ticker = %s RETURNING id",
            (user["id"], ticker.upper().strip()),
        )
        deleted = cur.fetchone()
        conn.commit()

    if not deleted:
        raise HTTPException(status_code=404, detail="Ticker not in watchlist")

    return {"success": True, "ticker": ticker.upper()}


# ---------------------------------------------------------------------------
# Price Alerts
# ---------------------------------------------------------------------------

@router.get("/api/alerts")
async def get_price_alerts(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Get user's price alerts with current prices."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """SELECT id, ticker, condition, threshold, reference_price,
                      is_active, is_triggered, triggered_at, created_at, notes
               FROM price_alerts WHERE user_id = %s
               ORDER BY created_at DESC""",
            (user["id"],),
        )
        alerts = cur.fetchall()

        tickers = list({a["ticker"] for a in alerts})
        price_map = {}
        if tickers:
            cur.execute(
                """SELECT DISTINCT ON (ticker) ticker, close, date
                   FROM price_history WHERE ticker = ANY(%s)
                   ORDER BY ticker, date DESC""",
                (tickers,),
            )
            for pr in cur.fetchall():
                price_map[pr["ticker"]] = {"price": float(pr["close"]), "date": pr["date"].isoformat()}

    items = []
    for a in alerts:
        current = price_map.get(a["ticker"], {})
        items.append({
            "id": a["id"],
            "ticker": a["ticker"],
            "condition": a["condition"],
            "threshold": a["threshold"],
            "reference_price": a["reference_price"],
            "current_price": current.get("price"),
            "price_date": current.get("date"),
            "is_active": a["is_active"],
            "is_triggered": a["is_triggered"],
            "triggered_at": a["triggered_at"].isoformat() if a["triggered_at"] else None,
            "created_at": a["created_at"].isoformat(),
            "notes": a["notes"] or "",
        })

    return {"items": items, "count": len(items)}


@router.post("/api/alerts")
async def create_price_alert(
    body: PriceAlertRequest,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Create a new price alert."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    ticker = body.ticker.upper().strip()
    if body.condition not in ("above", "below", "pct_change"):
        raise HTTPException(status_code=400, detail="Invalid condition: must be above, below, or pct_change")

    with get_cursor(dict_cursor=True) as (conn, cur):
        # Validate ticker exists
        cur.execute("SELECT ticker FROM stocks WHERE ticker = %s", (ticker,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")

        # Limit alerts per user
        cur.execute("SELECT COUNT(*) AS cnt FROM price_alerts WHERE user_id = %s", (user["id"],))
        if cur.fetchone()["cnt"] >= 50:
            raise HTTPException(status_code=400, detail="Maximum 50 alerts allowed")

        # Get current price as reference
        cur.execute(
            """SELECT close FROM price_history
               WHERE ticker = %s ORDER BY date DESC LIMIT 1""",
            (ticker,),
        )
        price_row = cur.fetchone()
        reference_price = float(price_row["close"]) if price_row else None

        cur.execute(
            """INSERT INTO price_alerts (user_id, ticker, condition, threshold, reference_price, notes)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, created_at""",
            (user["id"], ticker, body.condition, body.threshold, reference_price, body.notes or ""),
        )
        row = cur.fetchone()
        conn.commit()

    return {
        "id": row["id"],
        "ticker": ticker,
        "condition": body.condition,
        "threshold": body.threshold,
        "reference_price": reference_price,
        "created_at": row["created_at"].isoformat(),
    }


@router.delete("/api/alerts/{alert_id}")
async def delete_price_alert(
    alert_id: int,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Delete a price alert."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_cursor(dict_cursor=True) as (conn, cur):
        cur.execute(
            "DELETE FROM price_alerts WHERE id = %s AND user_id = %s RETURNING id",
            (alert_id, user["id"]),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Alert not found")
        conn.commit()

    return {"success": True}


@router.patch("/api/alerts/{alert_id}/toggle")
async def toggle_price_alert(
    alert_id: int,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Toggle a price alert active/inactive."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_cursor(dict_cursor=True) as (conn, cur):
        cur.execute(
            """UPDATE price_alerts SET is_active = NOT is_active
               WHERE id = %s AND user_id = %s
               RETURNING id, is_active""",
            (alert_id, user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Alert not found")
        conn.commit()

    return {"id": row["id"], "is_active": row["is_active"]}


@router.post("/api/alerts/check")
async def check_price_alerts(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    """Check all active alerts against current prices and mark triggered ones."""
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_cursor(dict_cursor=True) as (conn, cur):
        cur.execute(
            """SELECT id, ticker, condition, threshold, reference_price
               FROM price_alerts
               WHERE user_id = %s AND is_active = TRUE AND is_triggered = FALSE""",
            (user["id"],),
        )
        alerts = cur.fetchall()
        if not alerts:
            return {"triggered": [], "checked": 0}

        tickers = list({a["ticker"] for a in alerts})
        cur.execute(
            """SELECT DISTINCT ON (ticker) ticker, close
               FROM price_history WHERE ticker = ANY(%s)
               ORDER BY ticker, date DESC""",
            (tickers,),
        )
        prices = {r["ticker"]: float(r["close"]) for r in cur.fetchall()}

        triggered = []
        for a in alerts:
            current_price = prices.get(a["ticker"])
            if current_price is None:
                continue

            fire = False
            if a["condition"] == "above" and current_price >= a["threshold"]:
                fire = True
            elif a["condition"] == "below" and current_price <= a["threshold"]:
                fire = True
            elif a["condition"] == "pct_change" and a["reference_price"]:
                pct = abs((current_price - a["reference_price"]) / a["reference_price"]) * 100
                if pct >= a["threshold"]:
                    fire = True

            if fire:
                cur.execute(
                    """UPDATE price_alerts SET is_triggered = TRUE, triggered_at = NOW()
                       WHERE id = %s""",
                    (a["id"],),
                )
                triggered.append({
                    "id": a["id"],
                    "ticker": a["ticker"],
                    "condition": a["condition"],
                    "threshold": a["threshold"],
                    "current_price": current_price,
                })

        conn.commit()

    return {"triggered": triggered, "checked": len(alerts)}
