from urllib.parse import urlparse

from config import (
    DATABASE_URL,
    APP_ENV,
    SESSION_TTL_HOURS,
    DB_POOL_MIN,
    DB_POOL_MAX,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    get_allowed_origins,
)


def validate_startup_config() -> None:
    parsed = urlparse(DATABASE_URL)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("DATABASE_URL must use postgresql:// scheme")
    if not parsed.hostname or not parsed.path or parsed.path == "/":
        raise RuntimeError("DATABASE_URL must include host and database name")

    if SESSION_TTL_HOURS <= 0:
        raise RuntimeError("SESSION_TTL_HOURS must be a positive integer")

    if DB_POOL_MIN <= 0 or DB_POOL_MAX <= 0 or DB_POOL_MIN > DB_POOL_MAX:
        raise RuntimeError("Invalid DB pool configuration: require 0 < DB_POOL_MIN <= DB_POOL_MAX")

    if SESSION_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
        raise RuntimeError("SESSION_COOKIE_SAMESITE must be one of: lax, strict, none")

    if SESSION_COOKIE_SAMESITE == "none" and not SESSION_COOKIE_SECURE:
        raise RuntimeError("SESSION_COOKIE_SECURE must be true when SESSION_COOKIE_SAMESITE=none")

    origins = get_allowed_origins()
    if APP_ENV == "production" and not origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS must be configured in production")
