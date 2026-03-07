"""
FastAPI backend for Portfolio Optimization Web Application.
Modularized entrypoint with pooled DB and router registration.
"""

from datetime import datetime, UTC
import logging
import secrets
import threading
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_allowed_origins
from db import init_db_pool, close_db_pool, check_db_health
from services import initialize_services
from migrations_runner import run_migrations
from startup_validation import validate_startup_config
from logging_config import configure_logging
from rate_limit import SlidingWindowRateLimiter, get_request_client_id
from config import (
    AUTH_RATE_LIMIT,
    ADMIN_RATE_LIMIT,
    RATE_LIMIT_WINDOW_SECONDS,
    SESSION_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_PROTECTION_ENABLED,
)
from security import get_session_csrf_token
from routers.auth import router as auth_router
from routers.portfolio import router as portfolio_router
from routers.market_data import router as market_data_router
from routers.admin import router as admin_router

configure_logging()
logger = logging.getLogger(__name__)

START_TIME = time.time()
_metrics_lock = threading.Lock()
_request_count = 0
_error_count = 0
_total_latency_ms = 0.0
_auth_limiter = SlidingWindowRateLimiter(limit=AUTH_RATE_LIMIT, window_seconds=RATE_LIMIT_WINDOW_SECONDS)
_admin_limiter = SlidingWindowRateLimiter(limit=ADMIN_RATE_LIMIT, window_seconds=RATE_LIMIT_WINDOW_SECONDS)

CSRF_EXEMPT_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/password-reset/request",
    "/api/auth/password-reset/confirm",
    "/api/auth/verify-email/confirm",
}
CSRF_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

app = FastAPI(
    title="Portfolio Optimizer API",
    description="Professional portfolio optimization engine",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    validate_startup_config()
    init_db_pool()
    run_migrations()
    if not check_db_health():
        raise RuntimeError("Database connectivity check failed during startup")
    initialize_services()
    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    close_db_pool()
    logger.info("Application shutdown complete")


@app.get("/health")
async def health_check():
    db_ok = check_db_health()
    return {
        "status": "healthy" if db_ok else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "services": {
            "database": "connected" if db_ok else "disconnected",
            "builder": "ready",
        },
    }


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    global _request_count, _error_count, _total_latency_ms

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()

    status_code = 500
    client_id = get_request_client_id(request)

    if request.url.path.startswith("/api/auth"):
        result = _auth_limiter.check(client_id)
        if not result.allowed:
            return JSONResponse(
                status_code=429,
                headers={"X-Request-ID": request_id, "Retry-After": str(result.reset_seconds)},
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many authentication requests. Try again later.",
                    "code": "RATE_LIMIT_AUTH",
                    "status_code": 429,
                    "request_id": request_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

    if request.url.path.startswith("/api/admin"):
        result = _admin_limiter.check(client_id)
        if not result.allowed:
            return JSONResponse(
                status_code=429,
                headers={"X-Request-ID": request_id, "Retry-After": str(result.reset_seconds)},
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many admin requests. Try again later.",
                    "code": "RATE_LIMIT_ADMIN",
                    "status_code": 429,
                    "request_id": request_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

    if (
        CSRF_PROTECTION_ENABLED
        and request.url.path.startswith("/api")
        and request.method.upper() in CSRF_PROTECTED_METHODS
        and request.url.path not in CSRF_EXEMPT_PATHS
    ):
        session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        if session_cookie:
            cookie_csrf = request.cookies.get(CSRF_COOKIE_NAME)
            header_csrf = request.headers.get("X-CSRF-Token")
            expected_csrf = get_session_csrf_token(session_cookie)

            csrf_valid = (
                bool(cookie_csrf)
                and bool(header_csrf)
                and bool(expected_csrf)
                and secrets.compare_digest(str(cookie_csrf), str(header_csrf))
                and secrets.compare_digest(str(header_csrf), str(expected_csrf))
            )

            if not csrf_valid:
                return JSONResponse(
                    status_code=403,
                    headers={"X-Request-ID": request_id},
                    content={
                        "error": "CSRF validation failed",
                        "message": "Missing or invalid CSRF token",
                        "code": "CSRF_VALIDATION_FAILED",
                        "status_code": 403,
                        "request_id": request_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        with _metrics_lock:
            _error_count += 1
        logger.exception("Unhandled request error", extra={"request_id": request_id})
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        with _metrics_lock:
            _request_count += 1
            _total_latency_ms += duration_ms
            if status_code >= 500:
                _error_count += 1

        logger.info(
            "%s %s completed with %s in %.2fms",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            extra={"request_id": request_id},
        )

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/metrics")
async def metrics():
    with _metrics_lock:
        requests_total = _request_count
        errors_total = _error_count
        total_latency_ms = _total_latency_ms

    avg_latency_ms = round(total_latency_ms / requests_total, 2) if requests_total else 0.0

    return {
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "requests_total": requests_total,
        "errors_total": errors_total,
        "average_latency_ms": avg_latency_ms,
    }


app.include_router(auth_router)
app.include_router(portfolio_router)
app.include_router(market_data_router)
app.include_router(admin_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    request_id = getattr(request.state, "request_id", None)
    error_message = exc.detail if exc.status_code < 500 else "Internal server error"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": error_message,
            "message": error_message,
            "code": f"HTTP_{exc.status_code}",
            "status_code": exc.status_code,
            "request_id": request_id,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    request_id = getattr(request.state, "request_id", None)
    logger.error("Unhandled exception: %s", exc, extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "Internal server error",
            "code": "INTERNAL_ERROR",
            "status_code": 500,
            "request_id": request_id,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
