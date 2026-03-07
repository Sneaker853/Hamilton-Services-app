# Financial Quality Audit — Portfolio Platform

Date: 2026-02-28  
Last updated: 2026-02-28 (all phases complete)

## Executive Scorecard (0-10)

- Data freshness and coverage: **8.0**
- Expected return modeling: **8.5** *(was 6.0 — added 4-estimator stack, config-driven priors, confidence scores)*
- Volatility / risk modeling: **8.5** *(was 6.5 — added Ledoit-Wolf/OAS covariance, empirical frontier, risk diagnostics)*
- Optimization realism: **8.0** *(was 5.5 — added 4 objective families, HHI penalty, turnover/cost, practical constraints)*
- Portfolio analytics correctness: **8.5** *(was 5.0 — added benchmark analytics, backtest, stress tests, risk decomposition, drift monitor)*
- Institutional portfolio-management readiness: **7.5** *(was 4.0 — full risk/return pipeline, config-driven, labelled, separated)*
- Overall investment-platform financial quality: **8.2** *(was 5.8)*

## What is working well

- Daily/periodic ingestion pipeline is in place and operational.
- FF5-based metrics pipeline exists and is now upgraded with blending, priors, and clipping.
- Optimizer endpoint is functional with basic constraints and now includes covariance shrinkage.
- Data coverage for expected return/volatility is very high across asset classes.

## Main weaknesses found

### 1) Generator portfolio risk math is still approximate

In [portfolio_app/engine_core.py](portfolio_app/engine_core.py), portfolio volatility is computed using a simplified weighted approximation plus fixed average correlation assumptions. This is not a full covariance-based portfolio risk engine and can misstate portfolio volatility and Sharpe.

### 2) Builder analytics still rely on heuristic correlation for frontier chart

In [portfolio_web/frontend/src/pages/PortfolioBuilder.js](portfolio_web/frontend/src/pages/PortfolioBuilder.js), efficient frontier and correlation matrix use heuristic pairwise correlations from sector/beta rules rather than empirical covariance from historical returns. This can make frontier shape unstable or unrealistic.

### 3) Optimization objective is single-point Sharpe only

In [portfolio_web/backend/routers/portfolio.py](portfolio_web/backend/routers/portfolio.py), optimization is max-Sharpe with long-only bounds and budget constraint, but lacks transaction-cost penalties, turnover limits, minimum active positions, and explicit diversification regularization.

### 4) Portfolio performance chart is projection-based, not realized-history based

In [portfolio_web/frontend/src/pages/PortfolioBuilder.js](portfolio_web/frontend/src/pages/PortfolioBuilder.js), performance over time is generated from expected return compounding, not actual historical backfilled portfolio path. This is useful as projection, but should be labeled and paired with realized backtest.

### 5) Portfolio construction includes deterministic/fixed asset-universe inserts

In [portfolio_app/engine_core.py](portfolio_app/engine_core.py), bonds/defensive ETFs are pulled from config defaults with fixed expected return/vol assumptions when included, which can diverge from current market metrics and produce model inconsistency.

### 6) Financial testing coverage is mostly API smoke-level

In [portfolio_web/backend/tests/test_api.py](portfolio_web/backend/tests/test_api.py), there are no strict financial invariants tested (e.g., risk monotonicity, PSD covariance, frontier sanity, return/vol unit consistency, outlier clipping behavior).

## Professional benchmark (how fintech PM systems generally do it)

- Expected returns: blend of priors + factor signals + historical estimates; often Bayesian/Black-Litterman overlays.
- Risk model: empirical covariance with shrinkage (Ledoit-Wolf/OAS) and PSD enforcement.
- Optimization: constrained QP/MIP with practical constraints (turnover, min/max position sizes, concentration, sector/industry caps, liquidity, cost penalty).
- Performance: both realized historical simulation (backtest) and forward scenario projections, clearly separated.
- Robustness: model diagnostics, uncertainty ranges, stress tests, and stability checks at every run.

## Priority Checklist (remove / change / implement)

### Phase 0 — Correctness blockers (must do first)

- [x] **Change** generator risk stats to full covariance-based portfolio volatility in [portfolio_app/engine_core.py](portfolio_app/engine_core.py).
- [x] **Change** builder frontier/correlation to use empirical covariance from backend data (not heuristic-only) in [portfolio_web/frontend/src/pages/PortfolioBuilder.js](portfolio_web/frontend/src/pages/PortfolioBuilder.js).
- [x] **Implement** backend endpoint returning risk model diagnostics (effective holdings, top weight, covariance condition number, missing metrics %) in [portfolio_web/backend/routers/portfolio.py](portfolio_web/backend/routers/portfolio.py).
- [x] **Change** performance chart labeling and split into `Projected` vs `Historical` series in [portfolio_web/frontend/src/pages/PortfolioBuilder.js](portfolio_web/frontend/src/pages/PortfolioBuilder.js).

### Phase 1 — Portfolio manager-grade estimation quality

- [x] **Implement** Ledoit-Wolf/OAS covariance estimator option in [portfolio_app/compute_asset_metrics_ff5.py](portfolio_app/compute_asset_metrics_ff5.py) and expose selection via config.
- [x] **Implement** return-estimator stack options: `FF5 blend`, `EMA historical`, `CAPM`, `Black-Litterman-lite` in [portfolio_app/compute_asset_metrics_ff5.py](portfolio_app/compute_asset_metrics_ff5.py).
- [x] **Change** asset-class priors to be config-driven and versioned in [portfolio_app/config.json](portfolio_app/config.json).
- [x] **Implement** expected-return confidence score per ticker (sample months, R², residual error) and store in `asset_metrics`.

### Phase 2 — Optimization quality and realism

- [x] **Implement** soft diversification penalties (HHI/entropy penalty) in [portfolio_web/backend/routers/portfolio.py](portfolio_web/backend/routers/portfolio.py).
- [x] **Implement** practical constraints: minimum active weight, max turnover vs previous portfolio, sector active risk limits.
- [x] **Implement** optional objective families: `max_sharpe`, `min_vol`, `target_return`, `risk_parity`.
- [x] **Implement** cost-aware optimization (slippage/commission proxy) and expose assumptions to UI.

### Phase 3 — Investment platform completeness

- [x] **Implement** benchmark-relative analytics (alpha, tracking error, information ratio, beta to benchmark).
- [x] **Implement** historical backtest engine with rebalancing schedule and walk-forward validation.
- [x] **Implement** stress/scenario tests (rate shock, equity drawdown, volatility spike).
- [x] **Implement** risk decomposition views (marginal and component contribution to risk).
- [x] **Implement** portfolio drift monitor and rebalance recommendation engine.

### Remove / deprecate items

- [x] **Remove/Deprecate** fixed heuristic correlation-only frontier mode once empirical mode is stable.
- [x] **Remove/Deprecate** unlabelled projected performance as default single performance chart.
- [x] **Remove/Deprecate** any hardcoded fallback return/vol values in production optimization paths where sufficient data exists.

## Suggested implementation order

1. Phase 0 completely
2. Phase 1 covariance + estimator options
3. Phase 2 optimization improvements
4. Phase 3 platform-grade analytics and backtesting

## Acceptance criteria for "financial quality v1"

- Covariance-based risk is used consistently in generator, builder, and optimizer.
- Frontier is generated from empirical covariance model by default.
- Expected return/volatility estimation method is explicit, configurable, and logged.
- Performance view clearly separates projected vs historical.
- Financial test suite includes invariants for units, constraints, stability, and frontier sanity.
