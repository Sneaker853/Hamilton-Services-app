import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict

from fastapi import HTTPException

from config import SESSION_TTL_HOURS, ADMIN_ALLOWED_EMAIL
from db import get_cursor


def hash_password(password: str, salt_hex: Optional[str] = None) -> Dict[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100_000,
    )
    return {"hash": password_hash.hex(), "salt": salt.hex()}


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    computed = hash_password(password, salt_hex)
    return secrets.compare_digest(computed["hash"], password_hash)


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def ensure_auth_tables() -> None:
    with get_cursor() as (conn, cur):
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS user_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS saved_portfolios (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE")
        cur.execute("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP")
        cur.execute("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMP NULL")
        cur.execute("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS csrf_token TEXT")
        cur.execute(
            "UPDATE user_sessions SET expires_at = created_at + make_interval(hours => %s) WHERE expires_at IS NULL",
            (SESSION_TTL_HOURS,),
        )
        cur.execute("UPDATE user_sessions SET csrf_token = token WHERE csrf_token IS NULL")
        cur.execute("ALTER TABLE user_sessions ALTER COLUMN csrf_token SET NOT NULL")
        cur.execute("ALTER TABLE user_sessions ALTER COLUMN expires_at SET NOT NULL")
        conn.commit()


def create_session(user_id: int) -> str:
    token = create_session_token()
    csrf_token = secrets.token_urlsafe(32)
    session_expires_at = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)

    with get_cursor() as (conn, cur):
        cur.execute(
            "INSERT INTO user_sessions (user_id, token, csrf_token, expires_at) VALUES (%s, %s, %s, %s)",
            (user_id, token, csrf_token, session_expires_at),
        )
        conn.commit()

    return token


def get_session_csrf_token(token: str) -> Optional[str]:
    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT csrf_token
            FROM user_sessions
            WHERE token = %s
              AND revoked_at IS NULL
              AND expires_at > NOW()
            """,
            (token,),
        )
        row = cur.fetchone()

    if not row:
        return None
    return row.get("csrf_token")


def revoke_session(token: str) -> bool:
    with get_cursor() as (conn, cur):
        cur.execute(
            """
            UPDATE user_sessions
            SET revoked_at = NOW()
            WHERE token = %s AND revoked_at IS NULL
            """,
            (token,),
        )
        updated = cur.rowcount
        conn.commit()

    return updated > 0


def revoke_user_sessions(user_id: int) -> None:
    with get_cursor() as (conn, cur):
        cur.execute(
            """
            UPDATE user_sessions
            SET revoked_at = NOW()
            WHERE user_id = %s AND revoked_at IS NULL
            """,
            (user_id,),
        )
        conn.commit()


def get_user_from_token(token: Optional[str]) -> Dict:
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT u.id, u.email, u.is_admin, u.created_at
            FROM app_users u
            JOIN user_sessions s ON s.user_id = u.id
            WHERE s.token = %s
              AND s.revoked_at IS NULL
              AND s.expires_at > NOW()
            """,
            (token,),
        )
        user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid auth token")

    return dict(user)


def resolve_auth_token(header_token: Optional[str], cookie_token: Optional[str]) -> Optional[str]:
    return cookie_token or header_token


def require_admin_user(token: Optional[str]) -> Dict:
    user = get_user_from_token(token)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    if str(user.get("email", "")).strip().lower() != ADMIN_ALLOWED_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access restricted")
    return user
