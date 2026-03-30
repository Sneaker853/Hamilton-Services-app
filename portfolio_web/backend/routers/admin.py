import logging
import subprocess
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Cookie

from config import PROJECT_ROOT
from db import get_cursor
from security import require_admin_user, resolve_auth_token
from config import SESSION_COOKIE_NAME

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


def _run_fundamentals_ingestion() -> None:
    try:
        ingest_script = PROJECT_ROOT / "portfolio_app" / "ingest_complete_fundamentals.py"
        result = subprocess.run(
            [sys.executable, str(ingest_script)],
            capture_output=True,
            text=True,
            timeout=3600,
        )
        if result.returncode == 0:
            logger.info("Fundamentals update completed successfully")
        else:
            logger.error("Fundamentals ingestion failed: %s", result.stderr)
    except Exception:
        logger.exception("Error running fundamentals ingestion")


@router.post("/update-fundamentals")
async def update_fundamentals(
    background_tasks: BackgroundTasks,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    require_admin_user(resolve_auth_token(x_auth_token, session_cookie))
    background_tasks.add_task(_run_fundamentals_ingestion)
    return {
        "status": "started",
        "message": "Stock fundamentals update initiated. This will take ~15-20 minutes.",
        "timestamp": datetime.utcnow().isoformat(),
        "note": "Data will be fetched from Yahoo Finance and updated in the database.",
    }


@router.get("/update-status")
async def get_update_status(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    require_admin_user(resolve_auth_token(x_auth_token, session_cookie))

    try:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute(
                """
                SELECT
                    COUNT(*) as total_stocks,
                    COUNT(CASE WHEN revenue IS NOT NULL THEN 1 END) as stocks_with_fundamentals,
                    MAX(updated_at) as last_updated
                FROM stocks
                """
            )
            status = cur.fetchone()

            cur.execute(
                """
                WITH latest_prices AS (
                    SELECT DISTINCT ON (ticker)
                        ticker,
                        date
                    FROM price_history
                    ORDER BY ticker, date DESC
                )
                SELECT
                    MAX(date) AS latest_price_date,
                    COUNT(*) AS tickers_with_price,
                    COUNT(*) FILTER (
                        WHERE date = (SELECT MAX(date) FROM latest_prices)
                    ) AS latest_price_ticker_count
                FROM latest_prices
                """
            )
            price_status = cur.fetchone()

        return {
            "total_stocks": status["total_stocks"],
            "stocks_with_data": status["stocks_with_fundamentals"],
            "coverage_percent": round((status["stocks_with_fundamentals"] / status["total_stocks"] * 100) if status["total_stocks"] > 0 else 0, 2),
            "last_updated": status["last_updated"].isoformat() if status["last_updated"] else None,
            "latest_price_date": price_status["latest_price_date"].isoformat() if price_status and price_status.get("latest_price_date") else None,
            "latest_price_ticker_count": int(price_status["latest_price_ticker_count"]) if price_status and price_status.get("latest_price_ticker_count") is not None else 0,
            "tickers_with_price": int(price_status["tickers_with_price"]) if price_status and price_status.get("tickers_with_price") is not None else 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception:
        logger.exception("Error getting update status")
        raise HTTPException(status_code=500, detail="Internal server error")
