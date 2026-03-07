# Portfolio Platform — Project Handoff

**Last Updated**: March 1, 2026
**Platform Status**: Launch-hardened MVP with security + financial + accessibility checklist completed and validated.
**Brand Name**: Hamilton Services

## TL;DR for Next AI (Start Here)

1. Read `EXECUTION_CHECKLIST_NEXT.md` first — it is now fully completed and reflects the latest implementation status.
2. Read `portfolio_web/ops/drill_records/2026-03-01_readiness_dry_run.md` for the latest readiness evidence.
3. Backend now uses cookie sessions + CSRF validation for state-changing API calls; frontend Axios auto-sends `X-CSRF-Token` from cookie.
4. Security and financial test suites are expanded and currently passing (`45 passed` backend at last run).
5. Highest-value next work is cleanup/polish: deprecation warnings (`on_event`, `utcnow`), optional router splitting, and deployment/staging rollout.

## March 1, 2026 Hardening Update

- Debug DB stats endpoint now requires admin authentication (`/api/debug/db-stats`).
- Password policy strengthened for register/reset flows (minimum length + uppercase/lowercase/number/symbol).
- CSRF protection added for authenticated state-changing API requests (cookie + header validation).
- Session CSRF token migration added: `portfolio_web/backend/migrations/004_session_csrf_token.sql`.
- Risk-free-rate handling standardized through backend config for optimization/backtest Sharpe calculations.
- Optimizer fallback responses now include explicit warning metadata.
- New backend security regression tests added (`test_security_regressions.py`).
- Financial invariants suite updated and validated.
- CI now enforces backend coverage threshold and uploads backend/frontend test artifacts.
- Added objective-regime and robustness tests (`test_objective_robustness.py`) for `max_sharpe`, `min_vol`, `target_return`, `risk_parity`, and fallback warnings.
- Generator now prefers empirical `asset_metrics` estimates for defensive bonds/ETFs before config fallbacks.
- Builder accessibility improved with keyboard reorder controls, richer semantic labels, and tabpanel semantics/focus handling in analytics.
- Frontend test coverage expanded with analytics empty-state resilience tests and holdings accessibility tests.
- Production readiness dry run recorded in `portfolio_web/ops/drill_records/2026-03-01_readiness_dry_run.md`.

---

## 1. What This Project Is

A full-stack portfolio management platform for stocks, ETFs, bonds, crypto, and commodities. Users can:
- **Generate portfolios** from 5 investment personas (growth, balanced, income, conservative, eco-friendly)
- **Manually build portfolios** with a drag-and-drop builder, live metrics, and 6 chart types
- **Run advanced analytics**: benchmark comparison, historical backtests, stress tests, risk decomposition, drift monitoring
- **Optimize weights** using mean-variance optimization with Sharpe/min-vol/target-return/risk-parity objectives
- **Browse market data** for 1,048 securities across 5 asset classes

---

## 2. Tech Stack

| Layer | Technology | Details |
|---|---|---|
| **Frontend** | React 18.2, React Router 6.20, Recharts 2.10 | Custom CSS (no framework), Zustand for theme, Axios with auth interceptors |
| **Backend** | FastAPI 0.109, Uvicorn 0.27, Python 3.14 | Modular router architecture (4 routers), connection pooling, rate limiting |
| **Database** | PostgreSQL 5432 | 8 tables, ~1.36M price history rows, connection pool via psycopg2 |
| **Data Pipeline** | yfinance, pandas, numpy, scikit-learn, scipy | FF5 factor model, Ledoit-Wolf covariance shrinkage |
| **DevOps** | Docker Compose, Caddy, backup scripts | Production-ready Docker configs exist but not deployed |

---

## 3. Project Structure

```
C:\Database\
├── .env                              # DB credentials (postgres:080770@localhost:5432/portfolio_db)
├── .env.example                      # Template
├── HANDOFF_PROMPT.md                 # THIS FILE
├── FINANCIAL_QUALITY_AUDIT.md        # Quality checklist (all 20 items complete, score 8.2/10)
├── PUBLISH_READINESS_CHECKLIST.md    # Deployment readiness
├── start_backend.bat                 # Quick-start scripts
├── start_frontend.bat
│
├── portfolio_app/                    # Core financial engine (Python modules)
│   ├── config.json                   # 5 personas, asset universe, estimation config (228 lines)
│   ├── config_manager.py             # Config utilities
│   ├── engine_core.py                # Portfolio construction & optimization
│   ├── expand_assets.py              # Asset universe expansion
│   ├── screener.py                   # Stock screening logic
│   ├── ingest_complete_fundamentals.py   # Fundamental data ingestion
│   ├── ingest_yfinance_prices.py     # Price history ingestion
│   ├── compute_asset_metrics_ff5.py  # FF5 metrics computation (expected return, vol, betas)
│   ├── generate_price_history.py     # Price data generation
│   └── update_real_prices.py         # Real price updates
│
├── portfolio_web/
│   ├── backend/                      # FastAPI backend
│   │   ├── main.py                   # App entrypoint (217 lines) — CORS, rate limiting, metrics, error handlers
│   │   ├── db.py                     # ThreadedConnectionPool (psycopg2), get_cursor() context manager
│   │   ├── config.py                 # Environment config (DATABASE_URL, SESSION_TTL, etc.)
│   │   ├── schemas.py               # 20+ Pydantic v2 request/response models (134 lines)
│   │   ├── security.py              # PBKDF2 password hashing, session tokens, auth resolution
│   │   ├── services.py              # ConfigManager + PortfolioBuilder singleton initialization
│   │   ├── rate_limit.py            # Sliding window rate limiter
│   │   ├── cache_store.py           # In-memory cache
│   │   ├── emailer.py               # Email utilities (password reset, verification)
│   │   ├── logging_config.py        # Structured logging
│   │   ├── startup_validation.py    # DB/config health checks on boot
│   │   ├── migrations_runner.py     # SQL migration runner
│   │   ├── requirements.txt         # dependencies incl. pytest-cov
│   │   ├── routers/
│   │   │   ├── portfolio.py         # 15 endpoints, ~1580 lines (main financial logic)
│   │   │   ├── auth.py              # 8 endpoints (register, login, logout, password reset, email verify)
│   │   │   ├── market_data.py       # 8 endpoints (stocks, ETFs, bonds, filters, ticker detail)
│   │   │   └── admin.py             # 2 endpoints (update fundamentals, check status)
│   │   ├── migrations/              # 4 SQL migration files (incl. CSRF session token)
│   │   └── tests/
│   │       ├── test_api.py
│   │       ├── test_financial_invariants.py
│   │       ├── test_objective_robustness.py
│   │       └── test_security_regressions.py
│   │
│   └── frontend/                    # React CRA frontend
│       ├── package.json             # Proxy → http://localhost:8000
│       ├── src/
│       │   ├── App.js               # Routes, auth gate, sidebar (297 lines)
│       │   ├── pages/
│       │   │   ├── Dashboard.js     # User dashboard
│       │   │   ├── PortfolioGenerator.js  # Persona-based portfolio generation
│       │   │   ├── PortfolioBuilder.js    # Manual builder (~1850 lines) — THE main feature page
│       │   │   ├── MarketData.js    # Securities browser
│       │   │   ├── AdminPanel.js    # Admin controls
│       │   │   ├── Login.js         # Authentication
│       │   │   └── Mission.js       # About page
│       │   └── components/
│       │       ├── Charts.js        # PerformanceLineChart, EfficientFrontierChart, RiskReturnScatter, CorrelationHeatmap
│       │       ├── Card.js, Button.js, LoadingSkeleton.js  # UI primitives
│       │       └── ThemeContext.js, ThemeToggle.js          # Dark/light theme
│       └── public/index.html
│
├── docker/                          # Docker deployment configs (not currently deployed)
│   ├── docker-compose.yml / docker-compose.prod.yml
│   ├── Dockerfile.backend / Dockerfile.frontend
│   ├── Caddyfile
│   └── backup/ (backup.sh, restore.sh)
│
└── .venv/                           # Python virtual environment (Python 3.14)
```

---

## 4. Database Schema

**Connection**: `postgresql://postgres:080770@localhost:5432/portfolio_db`

### Tables (8 total)

| Table | Rows | Purpose |
|---|---|---|
| `stocks` | 1,048 | Security master (21 columns: ticker, name, sector, market_cap, pe_ratio, beta, asset_class, etc.) |
| `price_history` | 1,357,779 | Daily OHLCV prices (2021-02-08 to 2026-02-26, 1,048 tickers) |
| `asset_metrics` | 1,048 | FF5-computed metrics (12 columns: expected_return, volatility, beta_mkt/smb/hml/rmw/cma, alpha, r2, sample_months) |
| `app_users` | 15 | User accounts |
| `user_sessions` | 32 | Active sessions |
| `saved_portfolios` | 8 | User-saved portfolio configurations |
| `auth_action_tokens` | 11 | Password reset/email verification tokens |
| `schema_migrations` | 4 | Migration tracking |

### Asset Class Breakdown

| Asset Class | Count |
|---|---|
| stock | 961 |
| etf | 38 |
| crypto | 22 |
| commodity | 14 |
| bond | 13 |

### Key Column Details

**`stocks` table**: id, ticker, name, exchange, sector, industry, market_cap, dividend_yield, pe_ratio, roe, debt_to_equity, eps, eps_growth, beta, revenue, net_income, operating_margin, current_ratio, asset_class, created_at, updated_at

**`asset_metrics` table**: ticker, expected_return, volatility, beta_mkt, beta_smb, beta_hml, beta_rmw, beta_cma, alpha, r2, sample_months, updated_at
- **Note**: Column is `beta_mkt` (NOT `beta`). This caused a bug that was fixed.
- `compute_asset_metrics_ff5.py` can also add `confidence_score`, `residual_std`, `return_estimator` columns when run, but these are not currently used by endpoints.

---

## 5. API Endpoints (33 total)

### Portfolio Router (15 endpoints) — `routers/portfolio.py`
| Method | Path | Description |
|---|---|---|
| GET | `/api/personas` | List 5 investment personas |
| POST | `/api/portfolio/generate` | Generate persona-based portfolio |
| POST | `/api/portfolio/analyze` | Analyze portfolio risk/return |
| POST | `/api/portfolio/optimize-weights` | Mean-variance optimization (4 objectives: max_sharpe, min_vol, target_return, risk_parity) |
| POST | `/api/portfolio/covariance-metrics` | Empirical covariance matrix |
| POST | `/api/portfolio/efficient-frontier` | Compute efficient frontier curve |
| POST | `/api/portfolio/risk-diagnostics` | Risk model diagnostics (condition number, effective holdings, etc.) |
| POST | `/api/portfolio/historical-performance` | Historical performance chart data |
| POST | `/api/portfolio/benchmark-analytics` | Alpha, beta, tracking error, info ratio vs benchmark |
| POST | `/api/portfolio/backtest` | Walk-forward backtest with rebalancing |
| POST | `/api/portfolio/stress-test` | 5 stress scenarios (rate shock, equity crash, vol spike, etc.) |
| POST | `/api/portfolio/risk-decomposition` | Marginal/component/percent contribution to risk |
| POST | `/api/portfolio/drift-monitor` | Portfolio drift detection + rebalance recommendations |
| POST | `/api/portfolios/save` | Save portfolio to DB |
| GET | `/api/portfolios` | List saved portfolios |

### Auth Router (8 endpoints) — `routers/auth.py`
| Method | Path | Description |
|---|---|---|
| POST | `/register` | Create account |
| POST | `/login` | Login (returns session token) |
| POST | `/logout` | End session |
| GET | `/me` | Current user info |
| POST | `/verify-email/request` | Request email verification |
| POST | `/verify-email/confirm` | Confirm email |
| POST | `/password-reset/request` | Request password reset |
| POST | `/password-reset/confirm` | Reset password |

### Market Data Router (8 endpoints) — `routers/market_data.py`
| Method | Path | Description |
|---|---|---|
| GET | `/api/stocks/summary` | Aggregate market statistics |
| GET | `/api/stocks/all` | All stocks with metrics |
| GET | `/api/etfs/all` | All ETFs |
| GET | `/api/bonds/all` | All bonds |
| GET | `/api/stocks/filters/options` | Filter options (sectors, exchanges) |
| GET | `/api/stocks/{ticker}` | Single stock detail |
| GET | `/api/stocks/{ticker}/history` | Price history for a ticker |
| GET | `/api/debug/db-stats` | Database statistics (admin-protected) |

### Admin Router (2 endpoints) — `routers/admin.py`
| Method | Path | Description |
|---|---|---|
| POST | `/update-fundamentals` | Trigger data pipeline |
| GET | `/update-status` | Check pipeline status |

---

## 6. Frontend Pages

| Route | Component | Description |
|---|---|---|
| `/` | Dashboard | Overview with portfolio summary |
| `/portfolio` | PortfolioGenerator | Select persona → auto-generate portfolio with charts |
| `/portfolio-builder` | PortfolioBuilder | **Main feature page** (~1850 lines). Manual portfolio construction with: asset search, drag-and-drop holdings, live metrics, 6 charts (sector/asset pie, performance, risk-return scatter, frontier, correlation), and 5 analytics tabs |
| `/market-data` | MarketData | Browse/filter 1,048 securities |
| `/mission` | Mission | About page |
| `/admin` | AdminPanel | Data pipeline controls (admin-only in sidebar) |
| `/login` | Login | Authentication |

### PortfolioBuilder Structure (the most important page)

The builder page (`PortfolioBuilder.js`, ~1850 lines) contains:

**Sub-components** (defined in the same file):
- `PortfolioSummary` — stat cards (return, vol, Sharpe, holdings count, investment)
- `MetricsPanel` — detailed metrics display
- `ChartsPanel` — 6 charts (sector pie, asset pie, performance line, risk-return scatter, efficient frontier, correlation heatmap)
- `HoldingsTable` — drag-and-drop holdings with weight sliders
- `AssetSearchSection` — search/add securities
- `AnalyticsPanel` — tabbed container for Phase 3 analytics
- `BenchmarkTab`, `BacktestTab`, `StressTab`, `RiskDecompTab`, `DriftTab` — individual tab content components

**Analytics Panel (Phase 3) — 5 tabs:**
1. **Benchmark** — Alpha, beta, tracking error, information ratio vs SPY
2. **Backtest** — Walk-forward simulation with equity curve chart, Sharpe, max drawdown
3. **Stress Test** — 5 scenario impacts (rate shock, equity crash, vol spike, etc.)
4. **Risk Decomposition** — Marginal/component risk contribution per asset
5. **Drift Monitor** — Current vs target weights, rebalance recommendations

**Helper functions**: `formatPct()`, `formatNum()`, `ANALYTICS_TABS` config array

**State**: Uses React `useState` for all state — holdings, metrics, charts, analytics data, loading flags

---

## 7. Financial Quality Audit Summary

A comprehensive financial quality audit was completed (`FINANCIAL_QUALITY_AUDIT.md`). All 20 checklist items across 4 phases are marked complete.

**Overall Score: 8.2/10** (up from 5.8)

| Phase | What Was Done |
|---|---|
| **Phase 0 — Correctness** | Full covariance-based portfolio vol, empirical covariance for frontier/correlation, risk model diagnostics endpoint, performance chart split into projected vs historical |
| **Phase 1 — Estimation Quality** | Ledoit-Wolf/OAS covariance shrinkage, 4-estimator return stack (FF5, EMA, CAPM, Black-Litterman-lite), config-driven asset-class priors, confidence scoring |
| **Phase 2 — Optimization** | 4 objective families (max_sharpe, min_vol, target_return, risk_parity), HHI concentration penalty, turnover/cost constraints, sector caps |
| **Phase 3 — Platform Completeness** | Benchmark analytics, walk-forward backtest, stress/scenario tests, risk decomposition, drift monitor |

### Remaining Weaknesses (current)
1. Optimization is still single-period (no multi-period / regime-switching).
2. Builder frontier retains a local fallback mode when backend empirical data is insufficient.
3. Runtime/test deprecation warnings remain (`FastAPI on_event`, Python `utcnow`, test framework warnings).
4. Rollback timing was documented and dry-run locally, but a full staged rollback rehearsal is still recommended pre-public launch.

---

## 8. Key Technical Details & Gotchas

### Important Bug Fixes (already applied)
- **Decimal dtype issue**: PostgreSQL returns `Decimal` type for numeric columns. Pandas preserves these as `dtype: object`, which breaks `numpy.cov()` in numpy 2.4.1. Fixed by adding `.astype(float)` to the `_fetch_price_matrix()` helper in `portfolio.py` (~line 1063).
- **Column naming**: The `asset_metrics` table has `beta_mkt` (NOT `beta`). The stress-test SQL was fixed to use `beta_mkt AS beta`.

### Architecture Notes
- Backend was refactored from a monolithic 1477-line `main.py` into 4 routers
- `main.py` is now 217 lines — app setup, middleware, rate limiting, error handlers
- `portfolio.py` at ~1580 lines is the largest router — all financial math lives here
- Two shared helpers in portfolio.py: `_fetch_price_matrix()` and `_build_portfolio_returns()` — used by benchmark, backtest, and other Phase 3 endpoints
- DB connection pooling uses `psycopg2.pool.ThreadedConnectionPool` via `db.py`
- Rate limiting defaults: auth (30 req/min), admin (20 req/min)
- Request metrics (count, errors, latency) exposed via `/metrics`
- Risk-free rate is centralized in backend config (`PORTFOLIO_RISK_FREE_RATE`)
- Optimizer failure/bypass now returns explicit warning metadata in response payload

### Frontend Architecture
- No component library — all custom CSS with CSS variables for theming
- Dark/light theme via Zustand store + ThemeContext
- Auth: cookie-based server sessions + `authUser` localStorage UI cache
- CSRF: Axios request interceptor sends `X-CSRF-Token` from `portfolio_csrf_token` cookie on state-changing methods
- Global 401 handler auto-redirects to `/login`
- CRA proxy: `/api` → `http://localhost:8000` (configured in `package.json`)
- API base URL: `process.env.REACT_APP_API_URL || '/api'`

### Config System
- `portfolio_app/config.json` (228 lines) contains:
  - 5 personas with scoring weights, asset allocation, constraints
  - Bond/defensive ETF universe with expected returns
  - Estimation config (v2-2026-02): covariance estimator, return estimator, asset-class priors/bounds
  - Screening config: S&P 500 universe, 252-day lookback, 504-day min history

---

## 9. Development History

### Before Feb 2026
- Built initial MVP: portfolio generator, builder, market data, auth
- React frontend with 6 chart types
- FastAPI backend (monolithic main.py)
- Data pipeline with yfinance + FF5 factor model

### Feb 2026 — Session 1
- Backend modularization: split main.py into 4 routers
- Completed all 20 FINANCIAL_QUALITY_AUDIT.md items (backend only)
- Added Phases 0-3 backend endpoints
- Score: 5.8 → 8.2

### Feb 28, 2026 — Session 2
- **Problem**: Phase 3 analytics existed as backend endpoints only — no UI
- **Built**: Full AnalyticsPanel component in PortfolioBuilder.js with 5 tabbed views
- **Added**: ~180 lines of CSS for analytics panel (tab pills, stat grids, tables, animations)
- **Fixed**: scikit-learn installation, beta_mkt column naming, Decimal dtype crash
- **Verified**: All 5 analytics endpoints tested and returning correct data
- **Build**: Frontend compiles successfully (230 KB JS, 44 KB CSS gzipped)

### Mar 1, 2026 — Session 3 (Hardening + Completion)
- Closed execution checklist items across security, financial quality, accessibility, tests, CI, and runbook coverage.
- Added CSRF session migration and middleware enforcement.
- Hardened password policy and protected debug endpoint.
- Expanded backend tests to include security regressions + objective robustness.
- Expanded frontend tests for analytics empty states, holdings accessibility, and app shell smoke.
- Added readiness drill artifacts and monitoring threshold docs.

---

## 10. Future Ideas Discussed

### AI Financial Advisor Chatbot (Medium effort, ~2-3 days)
- Chat panel in frontend that proxies to OpenAI/Anthropic API through backend
- System prompt would include user's current portfolio data, metrics, personas
- Cost: ~$5-20/month for light usage
- Needs: API key, prompt engineering, "not financial advice" disclaimers

### Making the Site Available Online (Easy, 30 min - 6 hours)
- **Recommended**: Cloudflare Tunnel — free, 30-minute setup, works while PC is on
- **Alternative**: DigitalOcean/Hetzner VPS ($6-12/mo) using existing Docker configs
- Docker setup already exists in `docker/` folder

---

## 11. Current Open Items (Recommended Next Tasks)

### High-value engineering cleanup
- [ ] Replace FastAPI `on_event` usage with lifespan handlers.
- [ ] Replace `datetime.utcnow()` usage with timezone-aware UTC datetime usage.
- [ ] Split `routers/portfolio.py` into smaller modules for maintainability.

### Financial/product roadmap
- [ ] Add multi-period optimization or regime-aware objective mode.
- [ ] Expose return-estimator method and confidence provenance more broadly in UI.
- [ ] Evaluate removing local frontier fallback once backend empirical mode is consistently available.

### Deployment & ops
- [ ] Execute staged rollback timing rehearsal using actual deployment artifact/tag.
- [ ] Deploy production topology (Docker + Caddy) with monitored alert thresholds.

---

## 12. How to Run

### Recommended (Windows)
From workspace root:
```powershell
cd c:\Database
start_backend.bat
start_frontend.bat
```

This is the most reliable local startup path for this project.

### Backend
```powershell
Set-Location c:\Database\portfolio_web\backend
$env:DATABASE_URL='postgresql://postgres:080770@localhost:5432/portfolio_db'
c:\Database\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

If backend startup exits with code 1, check:
1. Current working directory is `portfolio_web/backend`.
2. `DATABASE_URL` is set or present in root `.env`.
3. Port 8000 is free.
4. Run startup validation directly:
```powershell
Set-Location c:\Database\portfolio_web\backend
$env:DATABASE_URL='postgresql://postgres:080770@localhost:5432/portfolio_db'
c:\Database\.venv\Scripts\python.exe -c "from startup_validation import validate_startup_config; validate_startup_config(); print('startup config ok')"
```

### Frontend
```powershell
Set-Location c:\Database\portfolio_web\frontend
$env:BROWSER='none'
npm start
# Runs on http://localhost:3000, proxies /api to :8000
```

### Build Frontend for Production
```powershell
Set-Location c:\Database\portfolio_web\frontend
npm run build
```

### Data Pipeline (refresh market data)
```powershell
Set-Location c:\Database
c:\Database\.venv\Scripts\python.exe portfolio_app/ingest_complete_fundamentals.py
c:\Database\.venv\Scripts\python.exe portfolio_app/ingest_yfinance_prices.py
c:\Database\.venv\Scripts\python.exe portfolio_app/compute_asset_metrics_ff5.py
```

### Kill All Servers
```powershell
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force
```

### Run Tests
```powershell
Set-Location c:\Database\portfolio_web\backend
c:\Database\.venv\Scripts\python.exe -m pytest tests/ -v

Set-Location c:\Database\portfolio_web\frontend
npm test -- --watchAll=false
```

### Test Credentials
- Password policy now requires: minimum 10 chars with uppercase/lowercase/number/symbol.
- Use a compliant test password (example pattern only): `TestPass123!`

---

## 13. Validation Snapshot (Latest)

- Backend tests: `45 passed`
- Frontend tests: `4 suites passed`
- Frontend production build: successful
- Readiness dry-run artifact: `portfolio_web/ops/drill_records/2026-03-01_readiness_dry_run.md`
