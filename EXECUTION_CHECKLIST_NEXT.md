# Execution Checklist — Next Work Queue

Purpose: Turn the latest audit findings into a practical checklist we can execute in order.

Legend:
- [ ] Not started
- [~] In progress
- [x] Done

---

## 0) Launch Gate (Must be complete before public release)

### Security blockers
- [x] Remove or protect debug data endpoint
  - Scope: backend market-data router debug DB stats endpoint
  - Target: disable in production OR require admin auth
  - Acceptance: endpoint is inaccessible to public users in production

- [x] Strengthen password policy and enforce on register/reset
  - Scope: auth register + password reset confirm
  - Minimum: increase minimum length and require baseline complexity
  - Acceptance: weak passwords are rejected with clear API message

- [x] Add CSRF protection for authenticated state-changing requests
  - Scope: login session cookie model and protected POST endpoints
  - Acceptance: state-changing requests require valid CSRF token

### Financial correctness blockers
- [x] Add financial invariant tests (backend)
  - Scope: optimizer/frontier/covariance/risk diagnostics behavior
  - Invariants:
    - Weights sum to 1 (or 100%)
    - No negative weights for long-only objectives
    - Covariance matrix is PSD/stable
    - Frontier risk/return sanity under normal input
    - Constraint honoring (turnover/sector/min active)
  - Acceptance: invariants run in CI and fail on regression

---

## 1) High-Impact Hardening (Immediately after launch gate)

### Backend/API hardening
- [x] Standardize risk-free-rate handling (single source of truth)
  - Scope: sharpe calculations in optimization and analytics endpoints
  - Acceptance: no hardcoded mixed assumptions across endpoints

- [x] Make optimizer fallback explicit to users
  - Scope: equal-weight fallback path on optimization failure
  - Acceptance: response clearly includes fallback reason + warning metadata

- [x] Tighten auth protections
  - Scope: session handling and privileged endpoints
  - Acceptance: admin and auth flows include abuse resistance (rate limit + logging + auditability)

### Observability and ops
- [x] Add alert thresholds for core health metrics
  - Scope: uptime, request errors, latency, DB availability
  - Acceptance: clear thresholds documented and testable

- [x] Run production readiness drill
  - Scope: startup validation, migration run, rollback path
  - Acceptance: documented runbook and successful dry-run

---

## 2) Financial Model Quality Upgrades (Professional polish)

### Estimation and optimization quality
- [x] Review and tune generator assumptions for consistency with empirical model
  - Scope: rule-based generator weights and defaults
  - Acceptance: generator outputs remain aligned with backend risk model expectations

- [x] Validate objective behavior across market regimes
  - Scope: max_sharpe, min_vol, target_return, risk_parity
  - Acceptance: no objective produces unstable or pathological allocations on test baskets

- [x] Add robustness tests for missing/noisy data
  - Scope: sparse history, missing metrics, outlier returns
  - Acceptance: predictable degradation with explicit warnings

### Analytics trust and clarity
- [x] Improve confidence/explainability metadata surfaced to UI
  - Scope: confidence score + estimator provenance labels
  - Acceptance: users can see source and quality of each expected-return estimate

- [x] Expand benchmark/backtest sanity checks
  - Scope: alpha/beta/tracking error/info ratio/backtest curves
  - Acceptance: outputs match known-control examples within tolerance

---

## 3) UX, Accessibility, and Investor QoL

### Accessibility baseline
- [x] Add keyboard support for interactive list/select/drag workflows
  - Scope: builder search list and holdings manipulation
  - Acceptance: key flows usable without mouse

- [x] Improve semantic labeling for interactive controls
  - Scope: buttons, row actions, tab controls, chart context
  - Acceptance: screen reader announces intent clearly

- [x] Add focus management and visible focus states
  - Scope: auth, builder, analytics tabs
  - Acceptance: predictable focus order and clear focus ring in all key forms

### Product experience quality
- [x] Add clear user messaging for fallback analytics states
  - Scope: insufficient frontier/history/data conditions
  - Acceptance: actionable messages replace silent/ambiguous chart states

- [x] Add simple first-time guidance in builder flow
  - Scope: add holdings -> weights -> optimize -> analytics
  - Acceptance: first-use friction reduced without adding heavy UI complexity

---

## 4) Testing and CI Expansion

### Backend tests
- [x] Add dedicated financial invariants test module
- [x] Add regression tests for auth policy changes (password + CSRF)
- [x] Add tests for admin-guarded and debug-disabled behavior

### Frontend tests
- [x] Add smoke tests for auth + protected routes + builder core flow
- [x] Add accessibility-oriented tests for key interactions
- [x] Add resilience tests for empty/error API states on major pages

### CI quality gates
- [x] Fail CI on invariant test failures
- [x] Enforce minimum coverage threshold for backend financial modules
- [x] Add artifact/log capture for failed test diagnostics

---

## 5) Suggested Execution Order

1. Launch Gate blockers (Section 0)
2. Backend/API hardening from Section 1
3. Financial model upgrades from Section 2
4. UX/accessibility improvements from Section 3
5. Test and CI expansion from Section 4

---

## 6) Ready-to-Start Batch (What I can execute first)

- [x] Batch A: Close launch blockers
  - Remove/protect debug endpoint
  - Strengthen password policy
  - Add CSRF protection skeleton
  - Add first financial invariant tests

- [x] Batch B: Verification pass
  - Run backend tests and frontend build/tests
  - Validate no regression in auth and portfolio flows

- [x] Batch C: Handoff update
  - Update handoff/readiness docs with completed items and remaining risks
