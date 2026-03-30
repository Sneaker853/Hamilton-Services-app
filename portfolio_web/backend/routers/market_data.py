from datetime import timedelta
import logging
import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Cookie

from db import get_cursor
from cache_store import TTLCache
from config import MARKET_DATA_CACHE_TTL_SECONDS
from config import SESSION_COOKIE_NAME
from security import require_admin_user, resolve_auth_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["market-data"])
market_data_cache = TTLCache(MARKET_DATA_CACHE_TTL_SECONDS)
_schema_cache: dict[str, set[str]] = {}
_table_cache: dict[str, bool] = {}


EXCHANGE_MAP = {
    "NYQ": "NYSE",
    "NMS": "NASDAQ",
    "NGM": "NASDAQ Capital",
    "YHD": "Yahoo",
    "NCM": "NASDAQ",
    "PCX": "NYSE Arca",
    "ASE": "NYSE American",
    "BTS": "CBOE",
    "PNK": "Pink Sheets",
    "OQB": "OTC",
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
async def get_all_stocks():
    cached = market_data_cache.get("stocks_all")
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
            )
            stocks = cur.fetchall()

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
            "total": len(stocks_list),
            "latest_price_date": freshness["latest_price_date"].isoformat() if freshness and freshness.get("latest_price_date") else None,
            "latest_price_ticker_count": int(freshness["latest_price_ticker_count"]) if freshness and freshness.get("latest_price_ticker_count") is not None else 0,
            "tickers_with_price": int(freshness["tickers_with_price"]) if freshness and freshness.get("tickers_with_price") is not None else 0,
        }
        market_data_cache.set("stocks_all", result)
        return result
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
                SELECT ticker, name, exchange, sector, pe_ratio, roe, beta,
                       market_cap, revenue, dividend_yield, asset_class
                FROM stocks
                WHERE ticker = %s
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
