# Monitoring Thresholds (Launch Baseline)

These are the minimum alert thresholds for v1 production.

## Health and Uptime
- API health endpoint (`/health`) failure rate > 0 for 2 consecutive checks (1 min cadence): **Page**
- Uptime drop/restart loop (more than 3 restarts in 10 minutes): **Page**

## Error Rate
- 5xx rate > 2% over 5 minutes: **Page**
- 4xx rate > 15% over 15 minutes: **Warn**

## Latency
- p95 latency > 800 ms over 10 minutes: **Warn**
- p95 latency > 1500 ms over 10 minutes: **Page**

## Database
- DB health check disconnected for 2 consecutive checks: **Page**
- Connection pool exhaustion events > 0 in 5 minutes: **Page**

## Security Signals
- Auth rate-limit events > 100 in 10 minutes from distinct clients: **Warn**
- Admin rate-limit events > 20 in 10 minutes: **Warn**
- CSRF validation failures > 20 in 5 minutes: **Warn**

## Operational Response
- **Warn**: acknowledge within 30 minutes, triage same day.
- **Page**: acknowledge within 5 minutes, mitigation or rollback within 30 minutes.
