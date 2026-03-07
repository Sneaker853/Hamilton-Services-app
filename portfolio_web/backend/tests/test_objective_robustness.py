from contextlib import contextmanager

import numpy as np
import pytest
from fastapi.testclient import TestClient

from main import app
import routers.portfolio as portfolio_router


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def deterministic_loader(monkeypatch):
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    mean_returns = np.array([0.12, 0.08, 0.06, 0.10], dtype=float)
    cov_matrix = np.array(
        [
            [0.100, 0.035, 0.020, 0.030],
            [0.035, 0.070, 0.018, 0.025],
            [0.020, 0.018, 0.050, 0.016],
            [0.030, 0.025, 0.016, 0.080],
        ],
        dtype=float,
    )

    def fake_loader(requested_tickers):
        aligned = [t for t in tickers if t in requested_tickers]
        idx = [tickers.index(t) for t in aligned]
        return aligned, mean_returns[idx], cov_matrix[np.ix_(idx, idx)]

    class _FakeCursor:
        def __init__(self):
            self._rows = []

        def execute(self, query, params=None):
            if "FROM stocks" in query and "COALESCE(sector" in query:
                req_tickers = list(params[0]) if params else []
                self._rows = [{"ticker": t, "sector": "Technology" if t in {"AAA", "DDD"} else "Healthcare"} for t in req_tickers]
            else:
                self._rows = []

        def fetchall(self):
            return self._rows

        def close(self):
            return None

    class _FakeConn:
        def commit(self):
            return None

    @contextmanager
    def fake_get_cursor(dict_cursor=False):
        yield _FakeConn(), _FakeCursor()

    monkeypatch.setattr(portfolio_router, "_load_mean_returns_and_covariance", fake_loader)
    monkeypatch.setattr(portfolio_router, "get_cursor", fake_get_cursor)


@pytest.mark.parametrize("objective", ["max_sharpe", "min_vol", "target_return", "risk_parity"])
def test_objectives_produce_valid_long_only_weights(client, deterministic_loader, objective):
    payload = {
        "tickers": ["AAA", "BBB", "CCC", "DDD"],
        "optimize_sharpe": True,
        "objective": objective,
    }
    if objective == "target_return":
        payload["target_return"] = 0.085

    response = client.post("/api/portfolio/optimize-weights", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["optimized"] is True

    weights = [row["weight"] for row in data["weights"]]
    assert all(weight >= 0 for weight in weights)
    assert abs(sum(weights) - 100.0) <= 0.2
    assert max(weights) < 95.0


def test_optimization_falls_back_with_explicit_warning_when_solver_fails(client, deterministic_loader, monkeypatch):
    class _FakeResult:
        success = False
        message = "forced failure"

    def fake_minimize(*args, **kwargs):
        return _FakeResult()

    monkeypatch.setattr(portfolio_router, "minimize", fake_minimize)

    response = client.post(
        "/api/portfolio/optimize-weights",
        json={
            "tickers": ["AAA", "BBB", "CCC", "DDD"],
            "optimize_sharpe": True,
            "objective": "max_sharpe",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["optimized"] is False
    assert payload["warning"]["code"] == "OPTIMIZATION_FAILED"
    assert payload["warning"]["fallback_method"] == "equal_weight"


def test_robustness_rejects_insufficient_assets_for_optimization(client):
    response = client.post(
        "/api/portfolio/optimize-weights",
        json={"tickers": ["AAA"], "optimize_sharpe": True},
    )
    assert response.status_code == 400
    detail = str(response.json().get("message") or response.json().get("error") or "")
    assert (
        "Need at least two" in detail
        or "No price data found" in detail
        or "Insufficient" in detail
    )
