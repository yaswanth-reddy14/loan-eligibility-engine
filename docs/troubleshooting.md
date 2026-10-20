# Troubleshooting

- Docker pipe unavailable: start Docker Desktop and select Linux containers, then run `docker info`. Re-run setup; do not delete volumes.
- MinIO image pull denied: use the supplied source-build Dockerfile. It requires network access to upstream GitHub and the Go module proxy. A failed build is an external dependency blocker, not evidence of a working storage service.
- Python missing: `py install 3.12`, recreate `.venv`, install `backend/requirements-dev.txt`.
- API unhealthy: `docker compose logs --tail 100 migrate storage-init api`. Confirm database startup and migrations. Never paste secrets from logs into a public issue.
- Job READY: check ingestion-worker logs and object size/checksum. Fatal validation rolls back; the local worker retries at most five times before FAILED.
- Outbox PENDING: inspect n8n credential import, workflow publication and `dispatcher` logs. A 404 usually means the workflow is not published/active. A 401 means the shared header secret differs. Restart n8n after CLI workflow state changes.
- DEAD event: identify and fix the cause, then explicitly reset that event's attempts/status/next_attempt_at in a transaction. Never bulk reset all events without review. Already completed B/C calls remain idempotent.
- No email: REVIEW_REQUIRED matches are not notified. Check notification status counts. UNKNOWN or stale SENDING requires Mailpit/SES reconciliation before any manual reset; automatic resending could duplicate a message.
- No live products: expected until permission/robots/terms review is complete. Use clearly marked fixture products for the local demonstration.
- Port conflict: use `docker compose ps` and inspect existing listeners; change host-side ports and corresponding browser/settings URLs consistently. Do not stop unrelated services.
- MinIO/browser error: use `http://localhost:8000`, not a different hostname; CORS is restricted to that origin. Signed upload requests must include exactly the returned headers.
- Tests skipped: set TEST_DATABASE_URL to a disposable PostgreSQL database or run `scripts/run_checks.py`. Supplied-data tests need the real users.csv; CI deliberately does not contain it.
