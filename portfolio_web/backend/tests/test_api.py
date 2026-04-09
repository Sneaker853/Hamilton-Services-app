import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from main import app
import routers.portfolio as portfolio_router


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _csrf_headers(client):
    csrf = client.cookies.get("portfolio_csrf_token")
    return {"X-CSRF-Token": csrf} if csrf else {}


def _register_user(client, email: str, password: str = "Test1234!x"):
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 200
    assert "set-cookie" in {k.lower() for k in response.headers.keys()}
    payload = response.json()
    assert payload.get("token")
    return payload


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in ["healthy", "degraded"]
    assert "services" in payload


def test_auth_register_and_login(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    register = _register_user(client, email)
    assert register["user"]["email"] == email

    login = client.post("/api/auth/login", json={"email": email, "password": "Test1234!x"})
    assert login.status_code == 200
    assert login.json().get("token")


def test_save_and_list_portfolios(client):
    email = f"save_{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email)

    save_payload = {
        "name": "My Test Portfolio",
        "source": "generator",
        "data": {"holdings": [{"ticker": "AAPL", "weight": 50}]},
    }

    save_response = client.post("/api/portfolios/save", json=save_payload, headers=_csrf_headers(client))
    assert save_response.status_code == 200

    list_response = client.get("/api/portfolios")
    assert list_response.status_code == 200
    portfolios = list_response.json().get("portfolios", [])
    assert any(portfolio["name"] == "My Test Portfolio" for portfolio in portfolios)


def test_generate_portfolio_endpoint(client, monkeypatch):
    class FakeConfigManager:
        def get_personas(self):
            return {
                "balanced": {
                    "display_name": "Balanced",
                    "description": "Balanced profile",
                    "risk_level": "medium",
                    "expected_return_range": "7-10%",
                }
            }

    class FakeBuilder:
        def build_portfolio(self, persona_name, custom_overrides=None, exchanges=None):
            stocks_df = pd.DataFrame(
                [
                    {
                        "ticker": "AAPL",
                        "name": "Apple Inc.",
                        "sector": "Technology",
                        "exchange": "NASDAQ",
                        "asset_class": "stock",
                        "weight": 0.6,
                        "expected_return": 0.1,
                        "volatility": 0.2,
                        "total_score": 90.0,
                    },
                    {
                        "ticker": "MSFT",
                        "name": "Microsoft Corp.",
                        "sector": "Technology",
                        "exchange": "NASDAQ",
                        "asset_class": "stock",
                        "weight": 0.4,
                        "expected_return": 0.09,
                        "volatility": 0.18,
                        "total_score": 88.0,
                    },
                ]
            )
            return {
                "weights": {"AAPL": 0.6, "MSFT": 0.4},
                "stocks": stocks_df,
                "stats": {"expected_return": 0.095, "volatility": 0.19, "sector_breakdown": {"Technology": 1.0}},
            }

    monkeypatch.setattr(portfolio_router, "get_config_manager", lambda: FakeConfigManager())
    monkeypatch.setattr(portfolio_router, "get_portfolio_builder", lambda: FakeBuilder())

    payload = {
        "persona_name": "balanced",
        "investment_amount": 100000,
        "min_holdings": 5,
        "max_holdings": 20,
        "max_position_pct": 20,
        "max_sector_pct": 40,
        "include_bonds": False,
        "include_etfs": False,
        "rebalance_threshold": 5,
    }

    response = client.post("/api/portfolio/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["persona"] == "balanced"
    assert len(data["holdings"]) == 2


def test_covariance_metrics_requests_are_cached(client, monkeypatch):
    calls = {"count": 0}

    def fake_load_mean_returns_and_covariance(tickers):
        calls["count"] += 1
        return ["AAPL", "MSFT"], portfolio_router.np.array([0.10, 0.08]), portfolio_router.np.array([
            [0.040, 0.010],
            [0.010, 0.030],
        ])

    monkeypatch.setattr(
        portfolio_router,
        "_load_mean_returns_and_covariance",
        fake_load_mean_returns_and_covariance,
    )

    payload = {
        "holdings": [
            {"ticker": "AAPL", "weight": 60},
            {"ticker": "MSFT", "weight": 40},
        ]
    }

    first = client.post("/api/portfolio/covariance-metrics", json=payload)
    second = client.post("/api/portfolio/covariance-metrics", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1


def test_admin_endpoints_require_auth(client):
    response = client.get("/api/admin/update-status")
    assert response.status_code == 401


def test_password_reset_flow(client):
    email = f"reset_{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email)

    request_response = client.post("/api/auth/password-reset/request", json={"email": email})
    assert request_response.status_code == 200

    from db import get_cursor

    with get_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT id, user_id, token_hash
            FROM auth_action_tokens
            WHERE purpose = 'password_reset'
            ORDER BY id DESC
            LIMIT 1
            """
        )
        token_row = cur.fetchone()

    assert token_row is not None
    # token is hashed in DB; endpoint consumes raw token only, so invalid token must fail
    invalid_confirm = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "invalid-token", "new_password": "NewPass123!"},
    )
    assert invalid_confirm.status_code == 400


def test_verify_email_confirm_invalid_token(client):
    response = client.post("/api/auth/verify-email/confirm", json={"token": "invalid-token"})
    assert response.status_code == 400
