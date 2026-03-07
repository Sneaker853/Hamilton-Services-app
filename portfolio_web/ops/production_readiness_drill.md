# Production Readiness Drill Runbook

Goal: verify startup, migration safety, and rollback readiness before launch.

## Pre-Drill Inputs
- Production-like `.env` present (no placeholder secrets)
- Database backup taken and verified restorable
- Current commit SHA recorded

## Step 1 — Cold Start Validation
1. Start services with production compose config.
2. Confirm `/health` returns healthy and DB connected.
3. Confirm `/metrics` is reachable.
4. Validate CORS origins are restricted to approved domains.

Pass criteria:
- All containers healthy
- API reachable and returning healthy state

## Step 2 — Migration Validation
1. Run backend startup with migration runner enabled.
2. Confirm no migration errors in logs.
3. Verify `schema_migrations` contains expected migration set.
4. Validate auth/session and portfolio APIs still operate.

Pass criteria:
- Migrations apply cleanly and idempotently
- No schema drift issues in API flows

## Step 3 — Security Regression Checks
1. Confirm admin endpoints reject non-admin users.
2. Confirm debug DB stats endpoint rejects unauthenticated access.
3. Confirm CSRF enforcement blocks state-changing POST without valid token.
4. Confirm password policy rejects weak credentials.

Pass criteria:
- All checks return expected 401/403/400 behavior

## Step 4 — Rollback Drill
1. Deploy previous known-good image/tag in staging.
2. Restore database backup snapshot to rollback target.
3. Re-run smoke checks (`/health`, login, generate portfolio).

Pass criteria:
- Recovery completed within 30 minutes
- No manual DB surgery required

## Drill Completion Record
- Date:
- Owner:
- Commit tested:
- Result: PASS / FAIL
- Notes and follow-ups:
