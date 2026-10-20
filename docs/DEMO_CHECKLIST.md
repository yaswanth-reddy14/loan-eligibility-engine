# Reproducible demonstration checklist

This checklist separates an observed local run from the remaining external tests. Use `docs/demo-script.md` for the timed eight-minute narration. Do not show `.env`, CSV records, raw email lists, credential screens, or decrypted n8n credentials on a recording.

## Before recording

- [ ] Keep the supplied `users.csv` in the root. Its expected SHA-256 is `31e4b00ee000ec0478262bcc629073e76920201b05978a816a3ad4c0133d1ec9`; do not generate replacement assignment data.
- [ ] Docker Desktop is running, with sufficient free disk and memory. Use `http://localhost:8000` for the dashboard, matching MinIO's configured browser origin. Open n8n at `http://localhost:5678` and Mailpit at `http://localhost:8025`.
- [ ] Confirm local `.env` has `EMAIL_DELIVERY_MODE=preview`, `DEMO_MODE=true`, and an explicit controlled `NOTIFICATION_TEST_INBOX`. Do not change to SES test mode during this demo.
- [ ] Build once, then start; never run simultaneous Compose builds of the shared app image:

```powershell
$env:PYTHONPATH = 'backend;.'
docker compose build api
docker compose up -d --no-build
.\.venv\Scripts\python.exe scripts/import_n8n.py
docker compose ps
```

On a clean machine run `scripts/setup.ps1` first, then import as above. Source-built MinIO requires network access and a longer first build. Preserve existing volumes; this demonstration does not require resetting data. The importer republishes A/B/C and restarts n8n; wait for its health check before starting a job. It may take several minutes to import all three.

- [ ] Run verification and a full rehearsal. This sends only to local Mailpit and creates a new historical upload job:

```powershell
$env:RUN_MAILPIT_TEST = '1'
.\.venv\Scripts\python.exe scripts/run_checks.py
.\.venv\Scripts\python.exe -m pip_audit -r backend/requirements.txt --format json --output reports/dependency-audit-after.json
.\.venv\Scripts\python.exe scripts/demo.py --timeout 900
.\.venv\Scripts\python.exe scripts/recruiter_verify.py
.\.venv\Scripts\python.exe scripts/benchmark.py
.\.venv\Scripts\python.exe scripts/verify_workflow_replay.py
```

`demo.py` triggers real A discovery, uploads over the API, waits for B/C, and matches every SENT event's Message-ID to a Mailpit capture. It also checks one HTML/plain-text body and every job-specific destination. It is **not browser interaction evidence**. Mailpit retains at most 15,000 messages: archive evidence or increase the local retention before many repeated 3,302-message demos; never delete messages while a verification is running.

- [ ] Read `docs/POST_CLEANUP_REPORT.md` for current checks and remaining gates. Historical review evidence is under `reports/archive/pre-cleanup`; fresh command reports are in `reports/`.
- [ ] Read `reports/e2e.json` and note the rehearsal job ID and captured Mailpit ID. Read the n8n IDs in `reports/recruiter-verification.json`; open their actual executions in the editor. Execution payloads expire after 24 hours, so rerun if needed.
- [ ] Open `reports/checks.json`, `reports/pytest.xml`, `reports/benchmark.json`, and `reports/recruiter-verification.json` in editor tabs. Check their job IDs match. Prepare the architecture diagram and `serverless.yml`.
- [ ] Visual/browser validation remains a manual gate. The review environment exposed no browser surface. Check desktop and narrow-window rendering, keyboard access, password-token input, job selector, discovery status, drag/drop, progress and errors yourself. No automated visual test is claimed.

## Recording: dashboard upload and job evidence

- [ ] Start a timer. Connect the dashboard using API_TOKEN in the password input; clear/hide `.env` before recording. The token stays in page memory.
- [ ] Click **Run n8n A: fictional discovery**. Acceptance is not completion: show three fresh FIXTURE crawl records and a successful A execution with fetch, normalize and extract nodes.
- [ ] Drop the actual `users.csv`; show filename, size and schema preview. Click **Validate & upload**; show progress and the generated job ID. The dashboard automatically scopes results to that job. Do not upload a second time to retry an observation; select the existing job.
- [ ] Observe this browser-created job without another upload:

```powershell
.\.venv\Scripts\python.exe scripts/demo.py --job-id '<dashboard-job-id>' --timeout 900
.\.venv\Scripts\python.exe scripts/recruiter_verify.py --job-id '<dashboard-job-id>'
.\.venv\Scripts\python.exe scripts/benchmark.py --job-id '<dashboard-job-id>'
```

The observer also performs another A run, explicitly recorded in its report. New uploads create independent snapshots; repeated IDs across different jobs are expected. Counts and notifications must always be scoped to one job.

- [ ] Show COMPLETED ingestion, accepted 10,000, rejected 0. Show the independent report's 10,000 distinct external IDs, zero duplicate matches, and CSV hash. Do not imply unique email addresses: the supplied CSV contains repeated addresses.
- [ ] Open B's successful n8n execution. Show PostgreSQL candidate generation, actual Code evaluations, bulk persistence, metrics, and final acknowledgement. Verify `persisted_by_n8n_execution_id` and `completed_by_n8n_execution_id` match it.
- [ ] Explain 30,000 Cartesian pairs -> 13,302 advanced candidates (55.66% reduction): 10,000 REVIEW_REQUIRED + 1,116 self-employed possible + 2,186 salaried possible. Unknown criteria never qualify for notifications. Show the median benchmark and its individual samples, including the two-pass production caveat.
- [ ] Open C's successful final execution, job-scoped SENT=3,302, and DELIVERED outbox rows. C executes multiple 100-message batches; the last execution alone is not the whole delivery history.
- [ ] Open the exact `sample_mailpit_id` from this job in Mailpit. Show the controlled To address, fictional product/rate/source, first name and preliminary disclaimer. Show both text and HTML tabs. Say aloud: **Mailpit SMTP capture; AWS SES delivery is unverified.**
- [ ] If the new job is still progressing at the scheduled demonstration moment, say so. Show the explicitly labeled completed rehearsal job and its timestamps for the remaining evidence; do not represent it as the current upload. Keep the observer running and capture the new job's completion afterward.

## Database and logs to capture

```powershell
docker compose exec -T postgres psql -U loan -d loan -c "SELECT job_id,count(*) AS rows,count(DISTINCT external_id) AS distinct_ids FROM users WHERE job_id='<job-id>' GROUP BY job_id;"
docker compose exec -T postgres psql -U loan -d loan -c "SELECT product_id,status,count(*) FROM matches WHERE job_id='<job-id>' GROUP BY product_id,status ORDER BY product_id;"
docker compose exec -T postgres psql -U loan -d loan -c "SELECT status,count(*) FROM notification_events WHERE job_id='<job-id>' GROUP BY status;"
docker compose exec -T postgres psql -U loan -d loan -c "SELECT workflow,status,attempts,progress_count FROM workflow_outbox WHERE job_id='<job-id>';"
docker compose logs --since 15m api ingestion-worker dispatcher n8n > reports/demo-service-logs.txt
```

- [ ] Capture dashboard state, A/B/C execution views, benchmark output, Mailpit message, these aggregate SQL results, and check summary. Keep PII and secrets out of screenshots/log exports. n8n service audit JSON is not a substitute for n8n execution metadata.
- [ ] Store the actual video/screenshots, then replace README placeholders with real private links. Do not label missing captures as complete.
- [ ] Before any separate AWS/SES demonstration, obtain the user's explicit authorization, provision private infrastructure, verify SES identities and the controlled inbox, deploy/review the resolved artifact, and retain actual received-inbox evidence. None of those steps is proven by this local run.

Optional local artifact check (no AWS account calls):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package_lambda.ps1
.\.venv\Scripts\python.exe scripts/verify_lambda_artifact.py
```

This uses cached official SAM/runtime images when available and may download substantial dependencies on a clean machine. Preserve the JSON build/runtime manifests; a successful local container import is separate from deployed Lambda integration.
