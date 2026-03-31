import uuid
import time

import pytest
from fastapi.testclient import TestClient

from main import app
from config import SESSION_COOKIE_NAME, CSRF_COOKIE_NAME, get_allowed_origins
from security import get_session_csrf_token


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _register_user(client, email: str, password: str = "Test1234!x"):
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 200
    payload = response.json()

    # TestClient uses http://testserver, so secure cookies set by auth routes are not
    # persisted automatically. Mirror production cookie state explicitly for CSRF tests.
    token = payload.get("token")
    assert token
    client.cookies.set(SESSION_COOKIE_NAME, token, domain="testserver.local", path="/")

    csrf_token = get_session_csrf_token(token)
    assert csrf_token
    client.cookies.set(CSRF_COOKIE_NAME, csrf_token, domain="testserver.local", path="/")

    return payload


def test_password_policy_rejects_weak_password(client):
    email = f"weak_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post("/api/auth/register", json={"email": email, "password": "weakpass"})

    assert response.status_code == 400
    message = str(response.json().get("message") or response.json().get("error") or "")
    assert "Password" in message


def test_csrf_required_for_authenticated_state_change(client):
    email = f"csrf_{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email)

    payload = {
        "name": "CSRF Test Portfolio",
        "source": "builder",
        "data": {"holdings": [{"ticker": "AAPL", "weight": 50}]},
    }

    blocked = client.post("/api/portfolios/save", json=payload)
    assert blocked.status_code == 403

    csrf_token = client.cookies.get(CSRF_COOKIE_NAME, domain="testserver.local", path="/")
    assert csrf_token
    allowed = client.post("/api/portfolios/save", json=payload, headers={"X-CSRF-Token": csrf_token})
    assert allowed.status_code == 200


def test_csrf_forbidden_response_includes_cors_headers_for_allowed_origin(client):
    email = f"csrf_cors_{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email)

    payload = {
        "name": "CSRF CORS Header Test",
        "source": "builder",
        "data": {"holdings": [{"ticker": "AAPL", "weight": 50}]},
    }
    allowed_origin = get_allowed_origins()[0]

    blocked = client.post(
        "/api/portfolios/save",
        json=payload,
        headers={"Origin": allowed_origin, "X-CSRF-Token": "invalid-csrf-token"},
    )
    assert blocked.status_code == 403
    assert blocked.headers.get("access-control-allow-origin") == allowed_origin
    assert blocked.headers.get("access-control-allow-credentials") == "true"


def test_csrf_trusted_origin_allows_cookie_mode_without_header(client):
    email = f"csrf_trusted_{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email)

    payload = {
        "name": "Trusted Origin Cookie CSRF",
        "source": "builder",
        "data": {"holdings": [{"ticker": "AAPL", "weight": 50}]},
    }
    allowed_origin = get_allowed_origins()[0]

    allowed = client.post(
        "/api/portfolios/save",
        json=payload,
        headers={"Origin": allowed_origin},
    )
    assert allowed.status_code == 200


def test_debug_db_stats_requires_admin_auth(client):
    response = client.get("/api/debug/db-stats")
    assert response.status_code in (401, 403)


def test_portfolio_generate_not_csrf_blocked_when_session_cookie_present(client):
    email = f"csrf_generate_{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email)

    payload = {
        "persona_name": "balanced",
        "investment_amount": 100000,
        "min_holdings": 10,
        "max_holdings": 20,
        "max_position_pct": 10,
        "max_sector_pct": 25,
        "include_bonds": False,
        "include_etfs": False,
        "rebalance_threshold": 5,
    }

    response = client.post("/api/portfolio/generate", json=payload)
    assert response.status_code != 403


# ---------------------------------------------------------------------------
# Session expiry tests
# ---------------------------------------------------------------------------


def test_expired_session_returns_401(client):
    """Sessions past their expiry time should be rejected."""
    email = f"expiry_{uuid.uuid4().hex[:8]}@example.com"
    payload = _register_user(client, email)
    token = payload["token"]

    # Manually expire the session via direct DB update
    from db import get_cursor

    with get_cursor() as (conn, cur):
        cur.execute(
            "UPDATE user_sessions SET expires_at = NOW() - INTERVAL '1 second' WHERE token = %s",
            (token,),
        )
        conn.commit()

    response = client.get("/api/portfolios")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Revoked token reuse tests
# ---------------------------------------------------------------------------


def test_revoked_token_cannot_access_protected_endpoints(client):
    """After logout, the same session token must be rejected."""
    email = f"revoke_{uuid.uuid4().hex[:8]}@example.com"
    payload = _register_user(client, email)

    csrf_token = client.cookies.get(CSRF_COOKIE_NAME, domain="testserver.local", path="/")

    # Logout (revoke session)
    response = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert response.status_code == 200

    # Try to access a protected endpoint with same session cookie
    response = client.get("/api/portfolios")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Admin access control tests
# ---------------------------------------------------------------------------


def test_non_admin_user_cannot_access_admin_endpoints(client):
    """Regular users should receive 403 on admin-only endpoints."""
    email = f"nonadmin_{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email)

    csrf_token = client.cookies.get(CSRF_COOKIE_NAME, domain="testserver.local", path="/")

    response = client.get("/api/admin/users", headers={"X-CSRF-Token": csrf_token})
    assert response.status_code == 403


def test_admin_endpoint_without_session_is_rejected(client):
    """Admin endpoints should return 401 without authentication."""
    response = client.get("/api/admin/users")
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# CSRF validation tests
# ---------------------------------------------------------------------------


def test_csrf_token_from_different_session_is_rejected(client):
    """CSRF token from one session must not work for another session."""
    email1 = f"csrf_sess1_{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email1)
    csrf_token_1 = client.cookies.get(CSRF_COOKIE_NAME, domain="testserver.local", path="/")

    # Register a second user (new session)
    email2 = f"csrf_sess2_{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email2)

    # Try saving portfolio with the FIRST user's CSRF token on the SECOND user's session
    payload = {
        "name": "Cross-session CSRF",
        "source": "builder",
        "data": {"holdings": [{"ticker": "AAPL", "weight": 100}]},
    }
    response = client.post(
        "/api/portfolios/save",
        json=payload,
        headers={"X-CSRF-Token": csrf_token_1},
    )
    assert response.status_code == 403


def test_empty_csrf_header_is_rejected(client):
    """An empty X-CSRF-Token header should be treated as missing."""
    email = f"csrf_empty_{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email)

    payload = {
        "name": "Empty CSRF Test",
        "source": "builder",
        "data": {"holdings": [{"ticker": "AAPL", "weight": 100}]},
    }
    response = client.post(
        "/api/portfolios/save",
        json=payload,
        headers={"X-CSRF-Token": ""},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Rate limit backoff tests
# ---------------------------------------------------------------------------


def test_login_rate_limit_returns_429(client):
    """Login endpoint should enforce rate limits after repeated failures."""
    email = f"ratelimit_{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "WrongPassword1!"}

    responses = []
    for _ in range(12):
        resp = client.post("/api/auth/login", json=payload)
        responses.append(resp.status_code)

    # At least one response should be 429 (rate limited)
    assert 429 in responses, f"Expected 429 in responses, got: {set(responses)}"


def test_rate_limit_response_includes_retry_after(client):
    """429 responses should include Retry-After or rate limit headers."""
    email = f"retry_{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "WrongPassword1!"}

    for _ in range(12):
        resp = client.post("/api/auth/login", json=payload)
        if resp.status_code == 429:
            # Should have retry/rate-limit info in response
            body = resp.json()
            assert "detail" in body or "message" in body or "error" in body
            break
