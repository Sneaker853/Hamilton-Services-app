from typing import Optional
import hashlib
import secrets
import re
from datetime import datetime, timedelta, UTC

from fastapi import APIRouter, HTTPException, Header, Response, Cookie

from db import get_cursor
from schemas import (
    AuthRegisterRequest,
    AuthLoginRequest,
    AuthResponse,
    MessageResponse,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
    VerifyEmailConfirmRequest,
)
from security import (
    hash_password,
    verify_password,
    create_session,
    get_session_csrf_token,
    get_user_from_token,
    revoke_session,
    revoke_user_sessions,
    resolve_auth_token,
)
from config import (
    SESSION_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    SESSION_TTL_HOURS,
    SESSION_COOKIE_SECURE,
    EMAIL_VERIFICATION_REQUIRED,
    EMAIL_VERIFICATION_TOKEN_TTL_HOURS,
    PASSWORD_RESET_TOKEN_TTL_MINUTES,
    APP_PUBLIC_URL,
    APP_ENV,
)
from emailer import send_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

PASSWORD_MIN_LENGTH = 10
_PASSWORD_UPPER_RE = re.compile(r"[A-Z]")
_PASSWORD_LOWER_RE = re.compile(r"[a-z]")
_PASSWORD_DIGIT_RE = re.compile(r"\d")
_PASSWORD_SYMBOL_RE = re.compile(r"[^A-Za-z0-9]")


def _validate_password_strength(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {PASSWORD_MIN_LENGTH} characters",
        )

    if not _PASSWORD_UPPER_RE.search(password):
        raise HTTPException(status_code=400, detail="Password must include at least one uppercase letter")
    if not _PASSWORD_LOWER_RE.search(password):
        raise HTTPException(status_code=400, detail="Password must include at least one lowercase letter")
    if not _PASSWORD_DIGIT_RE.search(password):
        raise HTTPException(status_code=400, detail="Password must include at least one number")
    if not _PASSWORD_SYMBOL_RE.search(password):
        raise HTTPException(status_code=400, detail="Password must include at least one symbol")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_HOURS * 3600,
        path="/",
    )


def _set_csrf_cookie(response: Response, csrf_token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_HOURS * 3600,
        path="/",
    )


def _hash_action_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _create_action_token(user_id: int, purpose: str, ttl_minutes: int) -> str:
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_action_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)

    with get_cursor() as (conn, cur):
        cur.execute(
            """
            INSERT INTO auth_action_tokens (user_id, token_hash, purpose, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, token_hash, purpose, expires_at),
        )
        conn.commit()

    return raw_token


def _consume_action_token(raw_token: str, purpose: str) -> Optional[int]:
    token_hash = _hash_action_token(raw_token)
    with get_cursor(dict_cursor=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, user_id
            FROM auth_action_tokens
            WHERE token_hash = %s
              AND purpose = %s
              AND used_at IS NULL
              AND expires_at > NOW()
            LIMIT 1
            """,
            (token_hash, purpose),
        )
        token_row = cur.fetchone()
        if not token_row:
            return None

        cur.execute("UPDATE auth_action_tokens SET used_at = NOW() WHERE id = %s", (token_row["id"],))
        conn.commit()

    return int(token_row["user_id"])


def _send_verification_email(email: str, token: str) -> None:
    verify_link = f"{APP_PUBLIC_URL}/login?verify_token={token}"
    send_email(
        to_email=email,
        subject="Verify your email",
        body_text=f"Please verify your email by opening this link: {verify_link}",
    )


def _send_password_reset_email(email: str, token: str) -> None:
    reset_link = f"{APP_PUBLIC_URL}/login?reset_token={token}"
    send_email(
        to_email=email,
        subject="Reset your password",
        body_text=f"You requested a password reset. Open this link to continue: {reset_link}",
    )


@router.post("/register", response_model=AuthResponse)
async def register_user(request: AuthRegisterRequest, response: Response):
    email = request.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    _validate_password_strength(request.password)

    with get_cursor(dict_cursor=True) as (conn, cur):
        cur.execute("SELECT id FROM app_users WHERE email = %s", (email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")

        password_data = hash_password(request.password)
        cur.execute(
            """
            INSERT INTO app_users (email, password_hash, password_salt)
            VALUES (%s, %s, %s)
            RETURNING id, email, is_admin, email_verified, created_at
            """,
            (email, password_data["hash"], password_data["salt"]),
        )
        user = cur.fetchone()
        conn.commit()

    verify_token = _create_action_token(
        user_id=user["id"],
        purpose="email_verify",
        ttl_minutes=EMAIL_VERIFICATION_TOKEN_TTL_HOURS * 60,
    )
    _send_verification_email(email, verify_token)

    token = create_session(user["id"])
    _set_session_cookie(response, token)
    csrf_token = get_session_csrf_token(token)
    if csrf_token:
        _set_csrf_cookie(response, csrf_token)

    return {"token": token, "user": dict(user)}


@router.post("/login", response_model=AuthResponse)
async def login_user(request: AuthLoginRequest, response: Response):
    email = request.email.strip().lower()

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT id, email, is_admin, email_verified, password_hash, password_salt, created_at
            FROM app_users
            WHERE email = %s
            """,
            (email,),
        )
        user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(request.password, user["password_hash"], user["password_salt"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if EMAIL_VERIFICATION_REQUIRED:
        with get_cursor(dict_cursor=True) as (_, cur):
            cur.execute("SELECT email_verified FROM app_users WHERE id = %s", (user["id"],))
            verified_row = cur.fetchone()
            if not verified_row or not verified_row["email_verified"]:
                raise HTTPException(status_code=403, detail="Email not verified")

    token = create_session(user["id"])
    _set_session_cookie(response, token)
    csrf_token = get_session_csrf_token(token)
    if csrf_token:
        _set_csrf_cookie(response, csrf_token)
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "is_admin": user.get("is_admin", False),
            "email_verified": user.get("email_verified", False),
            "created_at": user["created_at"],
        },
    }


@router.post("/verify-email/request", response_model=MessageResponse)
async def request_verify_email(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    user = get_user_from_token(resolve_auth_token(x_auth_token, session_cookie))

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute("SELECT email_verified FROM app_users WHERE id = %s", (user["id"],))
        row = cur.fetchone()
        if row and row["email_verified"]:
            return {"success": True, "message": "Email is already verified."}

    verify_token = _create_action_token(
        user_id=user["id"],
        purpose="email_verify",
        ttl_minutes=EMAIL_VERIFICATION_TOKEN_TTL_HOURS * 60,
    )
    _send_verification_email(user["email"], verify_token)
    return {"success": True, "message": "Verification email sent if account exists."}


@router.post("/verify-email/confirm", response_model=MessageResponse)
async def confirm_verify_email(request: VerifyEmailConfirmRequest):
    user_id = _consume_action_token(request.token, "email_verify")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    with get_cursor() as (conn, cur):
        cur.execute("UPDATE app_users SET email_verified = TRUE WHERE id = %s", (user_id,))
        conn.commit()

    return {"success": True, "message": "Email verified successfully."}


@router.post("/password-reset/request", response_model=MessageResponse)
async def request_password_reset(request: PasswordResetRequest):
    email = request.email.strip().lower()

    user_id = None
    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute("SELECT id, email FROM app_users WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            user_id = row["id"]

    if user_id:
        reset_token = _create_action_token(
            user_id=user_id,
            purpose="password_reset",
            ttl_minutes=PASSWORD_RESET_TOKEN_TTL_MINUTES,
        )
        sent = send_email(
            to_email=email,
            subject="Reset your password",
            body_text=f"You requested a password reset. Open this link to continue: {APP_PUBLIC_URL}/login?reset_token={reset_token}",
        )

        if not sent and APP_ENV != "production":
            return {
                "success": True,
                "message": "SMTP not configured in development. Use the reset link below.",
                "debug_link": f"{APP_PUBLIC_URL}/login?reset_token={reset_token}",
            }

    return {"success": True, "message": "If the account exists, a password reset email has been sent."}


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(request: PasswordResetConfirmRequest):
    _validate_password_strength(request.new_password)

    user_id = _consume_action_token(request.token, "password_reset")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")

    password_data = hash_password(request.new_password)
    with get_cursor() as (conn, cur):
        cur.execute(
            """
            UPDATE app_users
            SET password_hash = %s,
                password_salt = %s
            WHERE id = %s
            """,
            (password_data["hash"], password_data["salt"], user_id),
        )
        conn.commit()

    revoke_user_sessions(user_id)

    return {"success": True, "message": "Password reset successfully."}


@router.get("/me")
async def get_current_user(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    token = resolve_auth_token(x_auth_token, session_cookie)
    return get_user_from_token(token)


@router.post("/logout")
async def logout_user(
    response: Response,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    token = resolve_auth_token(x_auth_token, session_cookie)
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    if not revoke_session(token):
        raise HTTPException(status_code=401, detail="Invalid auth token")

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        samesite="lax",
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        samesite="lax",
    )

    return {"success": True}
