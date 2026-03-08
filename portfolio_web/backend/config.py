import os
import re
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_CANDIDATES = [
    BACKEND_DIR.parent.parent,
    BACKEND_DIR.parent,
]
PROJECT_ROOT = next(
    (candidate for candidate in ROOT_CANDIDATES if (candidate / "portfolio_app").is_dir()),
    ROOT_CANDIDATES[0],
)

load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback: construct from individual DB_* variables
    _db_user = os.getenv("DB_USER", "postgres")
    _db_pass = os.getenv("DB_PASSWORD", "")
    _db_host = os.getenv("DB_HOST", "localhost")
    _db_port = os.getenv("DB_PORT", "5432")
    _db_name = os.getenv("DB_NAME", "portfolio_db")
    if _db_pass:
        DATABASE_URL = f"postgresql://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}"
    else:
        raise RuntimeError("Missing required environment variable: DATABASE_URL (or DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME)")

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "portfolio_session")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true" if APP_ENV == "production" else "false").strip().lower() == "true"
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "none" if APP_ENV == "production" else "lax").strip().lower()
if SESSION_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    SESSION_COOKIE_SAMESITE = "none" if APP_ENV == "production" else "lax"
if SESSION_COOKIE_SAMESITE == "none":
    SESSION_COOKIE_SECURE = True
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "portfolio_csrf_token")
CSRF_PROTECTION_ENABLED = os.getenv("CSRF_PROTECTION_ENABLED", "true").strip().lower() == "true"
EMAIL_VERIFICATION_REQUIRED = os.getenv("EMAIL_VERIFICATION_REQUIRED", "false").strip().lower() == "true"
EMAIL_VERIFICATION_TOKEN_TTL_HOURS = int(os.getenv("EMAIL_VERIFICATION_TOKEN_TTL_HOURS", "24"))
PASSWORD_RESET_TOKEN_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_TTL_MINUTES", "30"))
APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "http://localhost:3000").rstrip("/")
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))
AUTH_RATE_LIMIT = int(os.getenv("AUTH_RATE_LIMIT", "30"))
ADMIN_RATE_LIMIT = int(os.getenv("ADMIN_RATE_LIMIT", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
MARKET_DATA_CACHE_TTL_SECONDS = int(os.getenv("MARKET_DATA_CACHE_TTL_SECONDS", "60"))
PORTFOLIO_RISK_FREE_RATE = float(os.getenv("PORTFOLIO_RISK_FREE_RATE", "0.02"))
ADMIN_ALLOWED_EMAIL = os.getenv("ADMIN_ALLOWED_EMAIL", "loris@spatafora.ca").strip().lower()

PRODUCTION_REQUIRED_ORIGINS = [
    "https://hamilton-services.ca",
    "https://www.hamilton-services.ca",
    "https://hamilton-services-frontend.onrender.com",
]
DEFAULT_PRODUCTION_CORS_ORIGIN_REGEX = r"^https://([a-z0-9-]+\.)?hamilton-services\.ca$"


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


def get_allowed_origins() -> list[str]:
    origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    origins: list[str] = []

    if origins_env:
        origins.extend(_normalize_origin(origin) for origin in origins_env.split(",") if origin.strip())
    elif APP_ENV == "production":
        parsed = urlparse(APP_PUBLIC_URL)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            origins.append(f"{parsed.scheme}://{parsed.netloc}")
        else:
            raise RuntimeError("CORS_ALLOWED_ORIGINS must be set when APP_ENV=production or APP_PUBLIC_URL must be a valid URL")
    else:
        origins.extend(["http://localhost:3000", "http://localhost:8080"])

    if APP_ENV == "production":
        origins.extend(PRODUCTION_REQUIRED_ORIGINS)

    deduped = list(dict.fromkeys(_normalize_origin(origin) for origin in origins if origin))
    if APP_ENV == "production" and not deduped:
        raise RuntimeError("CORS_ALLOWED_ORIGINS must be configured in production")
    return deduped


def get_allowed_origin_regex() -> str | None:
    regex_env = os.getenv("CORS_ALLOWED_ORIGIN_REGEX", "").strip()
    if regex_env:
        return regex_env
    if APP_ENV == "production":
        return DEFAULT_PRODUCTION_CORS_ORIGIN_REGEX
    return None


def origin_is_allowed(origin: str) -> bool:
    normalized = _normalize_origin(origin)
    if not normalized:
        return False

    if normalized in get_allowed_origins():
        return True

    regex = get_allowed_origin_regex()
    if regex and re.match(regex, normalized):
        return True

    return False
