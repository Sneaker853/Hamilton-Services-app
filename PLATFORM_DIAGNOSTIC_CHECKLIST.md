# Hamilton Services — Platform Diagnostic Checklist

> Generated: March 29, 2026  
> Source: Full-platform diagnostic (UX, Financial Engine, Infrastructure)  
> Update this file as each task is completed.
>
> **Progress: Phase 1 — 17/17 complete ✓**

---

## Phase 1 — Critical Fixes (Do First)

### Security
- [x] Add security headers middleware (CSP, HSTS, X-Frame-Options, X-Content-Type-Options) to `main.py`
- [x] Remove debug token from API responses — log `debug_link` instead of returning it in `/password-reset/request`
- [x] Add Pydantic validation schema for `/api/portfolio/analyze` (currently accepts raw `List[Dict]`)
- [x] Add max holdings validation — cap at 100 tickers per request to prevent DoS via massive SQL
- [x] Validate `ADMIN_ALLOWED_EMAIL` is set in production — fail startup if missing instead of falling back to hardcoded email
- [x] Sanitize saved portfolio data — validate `request.data` structure in `/api/portfolios/save` to prevent stored XSS
- [x] Add per-endpoint rate limiting — separate buckets for login (5/5min), password-reset (3/10min), register (10/10min)

### Performance
- [x] Add GZIP compression middleware (`GZIPMiddleware` in FastAPI)
- [x] Add missing database indexes (migration 006): `price_history(ticker, date)`, `user_sessions(token)`, `stocks(sector, exchange)`, `saved_portfolios(user_id, created_at)`
- [x] Add DB connection pool timeout — `getconn()` currently blocks indefinitely
- [x] Add SQL query statement timeouts (`statement_timeout` per cursor)
- [x] Optimize `/api/stocks/all` query — replace `DISTINCT ON` full-table scan with `LATERAL` subquery + TTL cache

### Infrastructure
- [x] Fix Docker healthcheck — replace `python -c "import requests"` with `curl -f`
- [x] Add Gunicorn `--timeout 120`, `--max-requests 1000`, `--graceful-timeout 30`, increase workers to 4
- [x] Add migration advisory locking (`pg_advisory_lock`) to prevent race conditions on concurrent container starts
- [x] Add Docker log rotation config (`max-size: 10m`, `max-file: 3`)

---

## Phase 2 — Financial Model Corrections (16/18 complete ✓)

### Backtesting (Grade: D — Most Critical)
- [x] Implement walk-forward backtesting — re-estimate metrics at each rebalance using only past data (removes 100-300 bps look-ahead bias)
- [x] Add survivorship bias handling — track delisted tickers, include terminal returns in backtest
- [x] Fix rebalancing calendar — use actual business month-end dates (`BMonthEnd`) instead of fixed 21-day intervals
- [x] Improve transaction cost model — add market impact component (Almgren-Chriss simplified) beyond flat basis points

### Expected Return Model (Grade: C+)
- [x] Replace weak FF5 ridge lambda (1e-3) with cross-validated shrinkage (`RidgeCV` with `alphas=np.logspace(-4, 2)`)
- [x] Increase minimum beta lookback from 24 to 36 months — penalize confidence score for shorter history
- [x] Add beta standard error adjustment — penalize confidence when 95% CI width > 50% of beta estimate

### Risk Model (Grade: B-)
- [x] Extend covariance estimation window from 252 to 600+ days
- [x] Fix missing data handling — forward-fill individual stock gaps (max 3 days) instead of dropping entire dates
- [x] Add target return feasibility validation — reject requests where target exceeds max achievable return
- [x] Use S&P 500 sector weights as default benchmark instead of equal-weight for sector active constraints

### Optimization (Grade: B)
- [x] Add optimizer warm-starting from previous weights for faster convergence
- [x] Add infeasibility detection — return clear error when constraints are contradictory instead of silent equal-weight fallback

### New Professional Metrics
- [x] Add portfolio-level FF5 factor attribution — aggregate individual stock betas into portfolio factor exposures
- [x] Add Value-at-Risk (VaR) and Expected Shortfall metrics
- [x] Add Brinson-Fachler performance attribution (allocation effect vs. selection effect)
- [x] Add style analysis (large/small, value/growth regression)

---

## Phase 3 — UX & Customer Features

### Onboarding & Education
- [x] Add landing page with feature overview before auto-guest mode
- [x] Add onboarding wizard/modal on first visit explaining portfolio tools
- [x] Add financial glossary tooltips throughout UI (Sharpe ratio, HHI, beta, alpha, basis points, etc.)
- [x] Add contextual help icons (?) on complex UI elements with explanations
- [x] Add keyboard shortcuts help overlay (press `?` to toggle)

### Core Missing Features
- [x] Add CSV/PDF export for portfolios and analytics data
- [x] Add portfolio comparison view — side-by-side metrics for 2+ saved portfolios
- [x] Add watchlist/favorites — save stocks for monitoring
- [x] Add progress bars for long operations (portfolio generation, admin updates) with ETA

### UX Improvements
- [x] Add persona descriptions in Portfolio Generator explaining risk/return expectations
- [x] Add help text and tooltips to Generator form fields (`max_position_pct`, `max_sector_pct`, `costBps`)
- [x] Add empty state CTAs — "Create your first portfolio" buttons with links on Dashboard
- [x] Show "Expected Return" source label — clarify if historical, projected, or model-based
- [x] Add retry buttons on error states instead of generic messages
- [x] Replace `window.confirm` in Admin Panel with styled modal
- [x] Fix Contact form — add server-side submission instead of `mailto:` redirect

### Mobile & Accessibility
- [x] Improve mobile table layouts — stack rows vertically or add collapsible detail rows
- [x] Add touch-friendly alternatives for drag-drop holdings on mobile
- [x] Add screen reader descriptions for charts (alt text on Recharts)
- [x] Add skip-to-main-content link for keyboard navigation
- [x] Add `aria-invalid` and error linking on form validation
- [x] Fix color-only feedback — add icons alongside green/red indicators for colorblind users

---

## Phase 4 — Professional-Grade Enhancements

### Financial Engine
- [x] Add GARCH(1,1) volatility model (replaces EWMA — 15% lower forecast error)
- [x] Add factor-based risk model (`Cov = β Cov_factors β' + Σ_residuals`) alongside statistical covariance
- [ ] Add tax-loss harvesting engine (wash-sale rule awareness, cost basis tracking)
- [ ] Add multi-period optimization (CVXPY stochastic programming)
- [x] Add ESG constraints (min ESG score, carbon footprint limits)
- [x] Add liquidity constraints (max % of 20-day volume per position)
- [x] Calibrate stress test scenarios to historical events (2008, COVID, Taper Tantrum)
- [x] Add predictive drift monitoring — forecast 30-day drift and rebalance urgency
- [x] Add smart rebalancing calendar with ex-dividend date avoidance

### Infrastructure & Scalability
- [ ] Migrate to Redis-backed caching (distributed cache across containers)
- [ ] Migrate to Redis-backed rate limiting (distributed rate limits)
- [x] Add audit logging table and log all sensitive operations (password changes, admin actions, portfolio saves)
- [x] Add pagination to `/api/stocks/all` endpoint
- [x] Add caching to persona config endpoint (`GET /api/personas`)
- [x] Add automated PostgreSQL backup container in Docker Compose
- [x] Add Caddy security headers, rate limiting, and request size limits
- [x] Serve frontend with nginx instead of `npm install -g serve`
- [x] Add missing test coverage: session expiry, token reuse, admin access control, CSRF validation, rate limit backoff
- [x] Add constant-time session validation to prevent timing attacks
- [x] Add progressive backoff on password reset token brute-force attempts
- [x] Sanitize URL paths in logs — strip query parameters containing tokens

### Nice-to-Have Features
- [x] Add price alerts / notifications system
- [x] Add portfolio sharing (read-only link)
- [x] Add personal performance dashboard — actual returns vs. projections over time
- [x] Add goals & targets — allocation goals with auto-rebalancing suggestions
- [x] Add password strength indicator with real-time feedback
- [x] Add ticker autocomplete/suggestions in Market Data search
- [x] Add stock comparison — side-by-side view for 2+ tickers
- [x] Add FAQ / help documentation section

---

## Progress Summary

| Phase | Total | Done | Remaining |
|-------|-------|------|-----------|
| Phase 1 — Critical Fixes | 17 | 17 | 0 |
| Phase 2 — Financial Model | 18 | 16 | 2 |
| Phase 3 — UX & Features | 20 | 20 | 0 |
| Phase 4 — Professional | 30 | 19 | 11 |
| **Total** | **85** | **72** | **13** |
