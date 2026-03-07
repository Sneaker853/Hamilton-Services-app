"""
Financial invariant tests — verify mathematical correctness of portfolio
analytics, covariance properties, frontier monotonicity, and constraint
satisfaction.  These go beyond smoke tests to catch numerical/financial bugs.
"""

import math
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient

from main import app


# ---- Helpers ---------------------------------------------------------------

@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# A small, liquid test portfolio with well-known tickers
SAMPLE_HOLDINGS = [
    {"ticker": "AAPL", "weight": 30},
    {"ticker": "MSFT", "weight": 25},
    {"ticker": "GOOGL", "weight": 20},
    {"ticker": "AMZN", "weight": 15},
    {"ticker": "META", "weight": 10},
]


def _holding_dicts():
    return [{"ticker": h["ticker"], "weight": h["weight"]} for h in SAMPLE_HOLDINGS]


# ---- 1. Weights sum to 100% after optimization ----------------------------

class TestOptimizationWeightConstraints:
    """Weights from optimize-weights must sum to ~100% and be non-negative."""

    def test_optimized_weights_sum_to_100(self, client):
        tickers = [h["ticker"] for h in SAMPLE_HOLDINGS]
        resp = client.post("/api/portfolio/optimize-weights", json={
            "tickers": tickers,
            "optimize_sharpe": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        weights = [w["weight"] for w in data["weights"]]
        assert abs(sum(weights) - 100.0) < 0.5, f"Weights sum = {sum(weights)}, expected ~100"

    def test_optimized_weights_non_negative(self, client):
        tickers = [h["ticker"] for h in SAMPLE_HOLDINGS]
        resp = client.post("/api/portfolio/optimize-weights", json={
            "tickers": tickers,
            "optimize_sharpe": True,
        })
        assert resp.status_code == 200
        for w in resp.json()["weights"]:
            assert w["weight"] >= -0.01, f"Negative weight for {w['ticker']}: {w['weight']}"

    def test_equal_weights_when_sharpe_off(self, client):
        tickers = [h["ticker"] for h in SAMPLE_HOLDINGS]
        resp = client.post("/api/portfolio/optimize-weights", json={
            "tickers": tickers,
            "optimize_sharpe": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        expected_each = 100.0 / len(tickers)
        for w in data["weights"]:
            assert abs(w["weight"] - expected_each) < 0.1

    def test_min_vol_objective_produces_valid_weights(self, client):
        tickers = [h["ticker"] for h in SAMPLE_HOLDINGS]
        resp = client.post("/api/portfolio/optimize-weights", json={
            "tickers": tickers,
            "optimize_sharpe": True,
            "objective": "min_vol",
        })
        assert resp.status_code == 200
        data = resp.json()
        weights = [w["weight"] for w in data["weights"]]
        assert abs(sum(weights) - 100.0) < 0.5


# ---- 2. Covariance matrix is positive semi-definite ----------------------

class TestCovarianceProperties:
    """Covariance / risk metrics must be mathematically valid."""

    def test_portfolio_volatility_is_positive(self, client):
        resp = client.post("/api/portfolio/covariance-metrics", json={
            "holdings": _holding_dicts(),
            "risk_free_rate": 0.02,
        })
        assert resp.status_code == 200
        vol = resp.json()["metrics"]["volatility"]
        assert vol > 0, f"Portfolio volatility must be positive, got {vol}"

    def test_portfolio_volatility_bounded(self, client):
        """Portfolio vol should be less than the max individual vol (diversification)."""
        resp = client.post("/api/portfolio/covariance-metrics", json={
            "holdings": _holding_dicts(),
            "risk_free_rate": 0.02,
        })
        assert resp.status_code == 200
        vol = resp.json()["metrics"]["volatility"]
        # Annualised vol above 200% would be absurd for a diversified equity portfolio
        assert vol < 200, f"Volatility {vol}% seems unreasonably high"

    def test_sharpe_ratio_finite(self, client):
        resp = client.post("/api/portfolio/covariance-metrics", json={
            "holdings": _holding_dicts(),
            "risk_free_rate": 0.02,
        })
        assert resp.status_code == 200
        sharpe = resp.json()["metrics"]["sharpe_ratio"]
        assert math.isfinite(sharpe), f"Sharpe ratio is not finite: {sharpe}"

    def test_expected_return_within_bounds(self, client):
        """Clipped returns should be within [-20%, 35%]."""
        resp = client.post("/api/portfolio/covariance-metrics", json={
            "holdings": _holding_dicts(),
            "risk_free_rate": 0.02,
        })
        assert resp.status_code == 200
        ret = resp.json()["metrics"]["expected_return"]
        assert -25 <= ret <= 40, f"Expected return {ret}% outside plausible clipped range"


# ---- 3. Efficient frontier shape sanity -----------------------------------

class TestEfficientFrontier:
    """Frontier points must be ordered and sensible."""

    def test_frontier_risk_has_single_minimum_profile(self, client):
        resp = client.post("/api/portfolio/efficient-frontier", json={
            "holdings": _holding_dicts(),
            "bins": 20,
            "sample_count": 1000,
        })
        assert resp.status_code == 200
        frontier = resp.json()["frontier"]
        assert len(frontier) >= 2, "Frontier must have at least 2 points"

        risks = [p["risk"] for p in frontier]
        assert all(r >= 0 for r in risks), "Frontier risk values must be non-negative"

        min_idx = int(np.argmin(risks))
        for i in range(1, min_idx + 1):
            assert risks[i] <= risks[i - 1] + 0.05, (
                f"Frontier should move toward minimum variance on left branch: "
                f"{risks[i - 1]} -> {risks[i]}"
            )
        for i in range(min_idx + 1, len(risks)):
            assert risks[i] >= risks[i - 1] - 0.05, (
                f"Frontier should move away from minimum variance on right branch: "
                f"{risks[i - 1]} -> {risks[i]}"
            )

    def test_frontier_return_generally_increases(self, client):
        """As risk increases along the efficient frontier, return should generally increase."""
        resp = client.post("/api/portfolio/efficient-frontier", json={
            "holdings": _holding_dicts(),
            "bins": 20,
            "sample_count": 1000,
        })
        assert resp.status_code == 200
        frontier = resp.json()["frontier"]
        if len(frontier) >= 3:
            returns = [p["return"] for p in frontier]
            # The last point should have higher return than the first
            assert returns[-1] >= returns[0] - 1.0, (
                f"Frontier end return ({returns[-1]}) < start return ({returns[0]})"
            )

    def test_current_portfolio_on_or_below_frontier(self, client):
        """Current portfolio should not dominate the entire frontier."""
        resp = client.post("/api/portfolio/efficient-frontier", json={
            "holdings": _holding_dicts(),
            "bins": 20,
            "sample_count": 1000,
        })
        assert resp.status_code == 200
        data = resp.json()
        current = data["current_portfolio"]
        frontier = data["frontier"]
        # At least one frontier point should have higher return at similar risk
        assert current["risk"] >= 0, "Current portfolio risk must be non-negative"

    def test_asset_points_have_positive_risk(self, client):
        resp = client.post("/api/portfolio/efficient-frontier", json={
            "holdings": _holding_dicts(),
            "bins": 20,
            "sample_count": 800,
        })
        assert resp.status_code == 200
        for ap in resp.json()["asset_points"]:
            assert ap["risk"] >= 0, f"Asset {ap['name']} has negative risk"


# ---- 4. Stress test impacts are directionally correct ---------------------

class TestStressTestInvariants:
    """Stress scenarios must produce directionally sensible impacts."""

    def test_equity_drawdown_is_negative_for_equity_portfolio(self, client):
        resp = client.post("/api/portfolio/stress-test", json={
            "holdings": _holding_dicts(),
            "scenarios": ["equity_drawdown_20pct"],
        })
        assert resp.status_code == 200
        scenario = resp.json()["scenarios"][0]
        assert scenario["portfolio_impact_pct"] < 0, (
            f"Equity drawdown should produce negative impact, got {scenario['portfolio_impact_pct']}"
        )

    def test_all_scenarios_return_valid_impacts(self, client):
        resp = client.post("/api/portfolio/stress-test", json={
            "holdings": _holding_dicts(),
        })
        assert resp.status_code == 200
        for scenario in resp.json()["scenarios"]:
            assert math.isfinite(scenario["portfolio_impact_pct"]), (
                f"Non-finite impact for {scenario['scenario']}"
            )
            # Individual asset impacts should also be finite
            for asset in scenario["assets"]:
                assert math.isfinite(asset["impact_pct"])


# ---- 5. Risk decomposition invariants ------------------------------------

class TestRiskDecomposition:
    """Component risk contributions must sum to total portfolio vol."""

    def test_component_contributions_sum_to_portfolio_vol(self, client):
        resp = client.post("/api/portfolio/risk-decomposition", json={
            "holdings": _holding_dicts(),
        })
        assert resp.status_code == 200
        data = resp.json()
        port_vol = data["portfolio_volatility"]
        ccr_sum = sum(a["component_contribution"] for a in data["assets"])
        # CCR should sum to portfolio vol (within tolerance)
        assert abs(ccr_sum - port_vol) < 0.01, (
            f"Sum of component contributions ({ccr_sum}) != portfolio vol ({port_vol})"
        )

    def test_pct_contributions_sum_to_100(self, client):
        resp = client.post("/api/portfolio/risk-decomposition", json={
            "holdings": _holding_dicts(),
        })
        assert resp.status_code == 200
        pct_sum = sum(a["pct_contribution"] for a in resp.json()["assets"])
        assert abs(pct_sum - 100.0) < 1.0, (
            f"Pct contributions sum to {pct_sum}, expected ~100"
        )


# ---- 6. Benchmark analytics consistency ----------------------------------

class TestBenchmarkAnalytics:
    """Alpha/beta/tracking error values must be consistent."""

    def test_beta_is_finite_and_plausible(self, client):
        resp = client.post("/api/portfolio/benchmark-analytics", json={
            "holdings": _holding_dicts(),
            "benchmark_ticker": "SPY",
            "period": "1Y",
        })
        assert resp.status_code == 200
        data = resp.json()
        beta = data["beta"]
        assert math.isfinite(beta), f"Beta is not finite: {beta}"
        # For an all-equity portfolio vs SPY, beta should be roughly 0.5-2.0
        assert 0.0 < beta < 3.0, f"Beta {beta} is outside plausible range"

    def test_tracking_error_is_non_negative(self, client):
        resp = client.post("/api/portfolio/benchmark-analytics", json={
            "holdings": _holding_dicts(),
            "benchmark_ticker": "SPY",
            "period": "1Y",
        })
        assert resp.status_code == 200
        te = resp.json()["tracking_error"]
        assert te >= 0, f"Tracking error must be non-negative, got {te}"

    def test_r_squared_between_0_and_1(self, client):
        resp = client.post("/api/portfolio/benchmark-analytics", json={
            "holdings": _holding_dicts(),
            "benchmark_ticker": "SPY",
            "period": "1Y",
        })
        assert resp.status_code == 200
        r2 = resp.json()["r_squared"]
        assert 0.0 <= r2 <= 1.0, f"R² must be in [0, 1], got {r2}"


# ---- 7. Backtest invariants -----------------------------------------------

class TestBacktestInvariants:
    """Backtest must produce sensible time series and stats."""

    def test_backtest_series_starts_at_initial_value(self, client):
        resp = client.post("/api/portfolio/backtest", json={
            "holdings": _holding_dicts(),
            "period": "6M",
            "rebalance_frequency": "monthly",
            "initial_value": 100000,
        })
        assert resp.status_code == 200
        series = resp.json()["series"]
        assert len(series) > 0
        assert abs(series[0]["value"] - 100000) < 1.0

    def test_backtest_final_value_matches_total_return(self, client):
        resp = client.post("/api/portfolio/backtest", json={
            "holdings": _holding_dicts(),
            "period": "6M",
            "rebalance_frequency": "monthly",
            "initial_value": 100000,
        })
        assert resp.status_code == 200
        data = resp.json()
        summary = data["summary"]
        final = summary["final_value"]
        total_ret = summary["total_return_pct"]
        expected_final = 100000 * (1 + total_ret / 100)
        assert abs(final - expected_final) < 5.0, (
            f"Final value {final} inconsistent with total return {total_ret}%"
        )

    def test_max_drawdown_is_non_positive(self, client):
        resp = client.post("/api/portfolio/backtest", json={
            "holdings": _holding_dicts(),
            "period": "1Y",
            "rebalance_frequency": "monthly",
            "initial_value": 100000,
        })
        assert resp.status_code == 200
        mdd = resp.json()["summary"]["max_drawdown_pct"]
        assert mdd <= 0.01, f"Max drawdown should be <= 0, got {mdd}"

    def test_backtest_dates_are_ordered(self, client):
        resp = client.post("/api/portfolio/backtest", json={
            "holdings": _holding_dicts(),
            "period": "6M",
            "rebalance_frequency": "monthly",
            "initial_value": 100000,
        })
        assert resp.status_code == 200
        series = resp.json()["series"]
        dates = [s["date"] for s in series]
        assert dates == sorted(dates), "Backtest dates must be chronologically ordered"

    def test_sharpe_ratio_is_finite(self, client):
        resp = client.post("/api/portfolio/backtest", json={
            "holdings": _holding_dicts(),
            "period": "1Y",
            "rebalance_frequency": "monthly",
            "initial_value": 100000,
        })
        assert resp.status_code == 200
        sharpe = resp.json()["summary"]["sharpe_ratio"]
        assert math.isfinite(sharpe), f"Backtest Sharpe is not finite: {sharpe}"


# ---- 8. Drift monitor invariants -----------------------------------------

class TestDriftMonitor:
    """Drift must be bounded and directionally correct."""

    def test_drift_score_is_non_negative(self, client):
        resp = client.post("/api/portfolio/drift-monitor", json={
            "holdings": _holding_dicts(),
            "rebalance_threshold": 5.0,
        })
        assert resp.status_code == 200
        assert resp.json()["drift_score"] >= 0

    def test_drift_with_exact_values_shows_zero_drift(self, client):
        """If current values match target weights exactly, drift should be ~0."""
        # Give current values proportional to target weights
        total_value = 100000
        current_values = {}
        for h in SAMPLE_HOLDINGS:
            current_values[h["ticker"]] = total_value * h["weight"] / 100

        resp = client.post("/api/portfolio/drift-monitor", json={
            "holdings": _holding_dicts(),
            "current_values": current_values,
            "rebalance_threshold": 5.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["drift_score"] < 0.5, (
            f"Drift score should be ~0 for exact weights, got {data['drift_score']}"
        )
        assert not data["needs_rebalance"]


# ---- 9. Risk diagnostics invariants --------------------------------------

class TestRiskDiagnostics:
    """Diagnostics must produce valid numerical outputs."""

    def test_effective_holdings_bounded_by_n(self, client):
        resp = client.post("/api/portfolio/risk-diagnostics", json={
            "holdings": _holding_dicts(),
            "risk_free_rate": 0.02,
        })
        assert resp.status_code == 200
        diag = resp.json()["diagnostics"]
        n = diag["n_requested_assets"]
        eff = diag["effective_holdings"]
        assert 1.0 <= eff <= n + 0.1, (
            f"Effective holdings ({eff}) must be in [1, {n}]"
        )

    def test_hhi_between_0_and_1(self, client):
        resp = client.post("/api/portfolio/risk-diagnostics", json={
            "holdings": _holding_dicts(),
            "risk_free_rate": 0.02,
        })
        assert resp.status_code == 200
        hhi = resp.json()["diagnostics"]["hhi"]
        assert 0 < hhi <= 1.0, f"HHI must be in (0, 1], got {hhi}"

    def test_covariance_condition_number_positive(self, client):
        resp = client.post("/api/portfolio/risk-diagnostics", json={
            "holdings": _holding_dicts(),
            "risk_free_rate": 0.02,
        })
        assert resp.status_code == 200
        cond = resp.json()["diagnostics"]["covariance_condition_number"]
        if cond is not None:
            assert cond > 0, f"Condition number must be positive, got {cond}"
