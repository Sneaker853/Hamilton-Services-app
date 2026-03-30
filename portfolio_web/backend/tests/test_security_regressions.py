import uuid

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
