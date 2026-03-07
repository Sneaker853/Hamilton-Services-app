import uuid

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _register_user(client, email: str, password: str = "Test1234!x"):
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


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

    csrf_token = client.cookies.get("portfolio_csrf_token")
    allowed = client.post("/api/portfolios/save", json=payload, headers={"X-CSRF-Token": csrf_token})
    assert allowed.status_code == 200


def test_debug_db_stats_requires_admin_auth(client):
    response = client.get("/api/debug/db-stats")
    assert response.status_code in (401, 403)
