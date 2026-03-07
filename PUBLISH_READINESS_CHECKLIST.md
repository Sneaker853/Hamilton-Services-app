# Publish Readiness Checklist (v1)

This checklist is prioritized for getting a **first well-made internet-facing version** online safely.

Legend:
- [ ] Not started
- [~] In progress
- [x] Done

---

## Phase 0 — Critical blockers (must fix before public launch)

### Security
- [x] **S0-1: Protect admin endpoints with auth + role checks**
  - Scope: `POST /api/admin/update-fundamentals`, `GET /api/admin/update-status`
  - Add `is_admin` field in users table
  - Enforce admin validation on backend (not just frontend)

- [x] **S0-2: Remove hardcoded credentials and insecure defaults**
  - Remove plaintext passwords in `docker-compose.yml`
  - Remove hardcoded DB URL fallbacks in `portfolio_app/engine_core.py`
  - Use environment variables + `.env.example` only

- [x] **S0-3: Add session expiration + invalidation**
  - Add expiry for `user_sessions`
  - Reject expired tokens in auth middleware/helper
  - Add logout endpoint to revoke token server-side

- [x] **S0-4: Restrict CORS for production**
  - Replace localhost-only list with env-driven allowed origins
  - Separate dev/prod behavior

### Deployment correctness
- [x] **D0-1: Fix Docker backend import/layout issues**
  - Ensure container includes `portfolio_app` (currently backend image copies only backend folder)
  - Verify backend can import `engine_core` in container

- [x] **D0-2: Fix backend env contract for Docker**
  - Backend currently reads `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`
  - Docker sets `DATABASE_URL` instead
  - Align to one contract and validate on startup

- [x] **D0-3: Fix frontend production API base behavior**
  - CRA proxy works in dev only
  - Production build currently relies on `/api` unless build-time var is set
  - Add explicit production API strategy (same-origin reverse proxy or compile-time API URL)

- [x] **D0-4: Add production process model**
  - Run FastAPI with `gunicorn` + `uvicorn.workers.UvicornWorker`
  - Add reverse proxy (Nginx/Caddy) with TLS and `/api` routing

### Reliability
- [x] **R0-1: Split monolithic backend module**
  - Break `main.py` into routers (`auth`, `portfolio`, `market_data`, `admin`)
  - Add shared `db.py` and `auth.py` utilities

- [x] **R0-2: Introduce DB connection pooling**
  - Replace per-request `psycopg2.connect(...)` open/close pattern
  - Use pooled connections with health checks

- [x] **R0-3: Stop leaking internal exceptions to clients**
  - Replace `detail=str(e)` with safe user-facing error responses
  - Keep detailed stack traces in logs only

---

## Phase 1 — Launch quality baseline (strongly recommended)

### Testing & QA
- [x] **Q1-1: Add backend API tests (pytest)**
  - Minimum: health, auth login/register, save/list portfolios, generate portfolio, admin auth guard

- [x] **Q1-2: Add frontend smoke tests**
  - Login flow, protected routes, portfolio generate flow

- [x] **Q1-3: Add CI pipeline**
  - Run backend tests + frontend tests on PR
  - Fail build on test failure

### Data & schema management
- [x] **M1-1: Add schema migrations (Alembic or SQL migration scripts)**
  - Move table creation out of request app startup path
  - Track schema changes (e.g., `is_admin`, session expiry)

- [x] **M1-2: Add startup validation checks**
  - Validate required env vars and DB connectivity at startup
  - Fail fast with clear messages

### Observability
- [x] **O1-1: Structured logging + request IDs**
  - JSON logs in production
  - Request correlation IDs across errors

- [x] **O1-2: Add basic metrics + uptime monitoring**
  - Health check should actually validate DB
  - Add endpoint latency/error monitoring

---

## Phase 2 — Product hardening (post-launch but valuable)

- [x] **P2-1: Move auth tokens from localStorage to secure cookies (HttpOnly, Secure)**
- [x] **P2-2: Add password reset + email verification (optional for MVP depending on audience)**
- [x] **P2-3: Add rate limiting for auth and admin endpoints**
- [x] **P2-4: Add caching strategy for heavy market data endpoints**
- [x] **P2-5: Improve frontend error UX with standardized API error payloads**
- [x] **P2-6: Add backup/restore and retention policy for PostgreSQL**

---

## Suggested order of execution
1. S0-1, S0-2, D0-1, D0-2, D0-3
2. S0-3, S0-4, R0-3
3. R0-1, R0-2
4. Q1-1, Q1-2, Q1-3
5. M1-1, M1-2, O1-1, O1-2

---

## Acceptance gate for "publish v1"
Only publish once all are true:
- All Phase 0 items are complete
- Backend and frontend run in production topology with TLS
- Admin endpoints are inaccessible to non-admin users
- A minimal test suite passes in CI
- Secrets are fully externalized and rotated
