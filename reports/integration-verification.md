# Controlled local integration verification

**Result: PASS within the approved local scope.** No regression was found. The new application and A/B/C workflows remain installed; the default API page size is restored to 1000. No commit or push was performed.

## Observed results

| Stage | Result | Evidence |
|---|---|---|
| Immediate backup and historical preservation gate | PASS | Backup checksums, historical row fingerprints, private-file hashes, idle queues and original Mailpit IDs checked before changes. |
| API/workers and A/B/C installation | PASS | New app image; graphs equal approved exports; existing encrypted credentials and reader password unchanged. |
| Workflow A fictional discovery | PASS | Execution 304; three FIXTURE extraction/persistence results. No live fetch branch. |
| Upload, validation and ingestion | PASS | Three authenticated initialization/presigned PUT/completion sequences; 12 accepted/0 rejected per job; versioned objects and checksums verified. Invalid metadata rejected with 422 before creating a job. |
| Webhook authentication | PASS | Both missing and wrong secrets rejected for B and C (403). |
| Default matching | PASS | One 20-candidate page with configured page size 1000; independent oracle equal. |
| Exact boundary | PASS | 5/5/5/5/0 candidates; empty terminal page before final acknowledgement. |
| Partial final page | PASS | 5/5/5/4 candidates; short terminal page. |
| Completion and duplicate safety | PASS | One B acknowledgement and C outbox event per job; unique match keys; B/C audit COMPLETED and outbox DELIVERED. |
| Workflow C Mailpit capture | PASS | 23 unique messages, only the unchanged configured controlled inbox, correct fictional greetings and exact eligible product lists. |
| Synthetic-only replay | PASS | All three B/C replays preserved entire match/notification rows, including attempts and provider IDs; zero extra messages. |
| Historical preservation and final health | PASS | Seven old 10k jobs, 93114 old matches, 23114 old SENT notifications and all 15000 existing Mailpit IDs unchanged; eight healthy services including the isolated inbox. |
| Regression checks | PASS | 114 passed, 3 deliberately deselected, 2 dependency deprecation warnings; Ruff/MyPy/validators/build checks exit 0. |

## Synthetic jobs and execution IDs

The test reused 12 fictional identities across three job-scoped uploads: **36 new user snapshots**, 59 matching/review outcomes and 23 notification events. External IDs are unique within each job. All 36 REVIEW_REQUIRED outcomes belong to the incomplete fixture; 23 POSSIBLY_ELIGIBLE outcomes produce 23 grouped user notifications. These are observed results, not the historical 10k benchmark.

| Case | Job ID | Users | Matches | Captures | B / C executions | Replay B / C |
|---|---|---:|---:|---:|---|---|
| default | `575961ba-0692-4d8b-8ab0-43dc4105454e` | 12 | 20 | 8 | 305 / 306 | 311 / 312 |
| exact | `e289205a-f8a0-407a-83de-6d9ac4085ea4` | 12 | 20 | 8 | 307 / 308 | 313 / 314 |
| partial | `38406b91-76ae-4aa7-90ea-adb7c2fada9b` | 12 | 19 | 7 | 309 / 310 | 315 / 316 |

All 13 retained n8n executions (304-316) completed successfully. Their node execution metadata, page traces, message/event IDs, object versions and matching metrics are in [integration-verification.json](integration-verification.json). No successful result is inferred merely from webhook acceptance. The independent Cartesian oracle reads actual users and fictional criteria without calling production matching helpers or CANDIDATE_SQL.

The dispatcher stayed paused until all direct synthetic B/C tests and replays passed. This allowed oracle verification before C and prevented automatic backlog sends. It was then restarted and marked the six new, already acknowledged outbox events DELIVERED without sending again.

## Before and after

| Table | Before | After | Approved delta |
|---|---:|---:|---:|
| ingestion_jobs | 8 | 11 | 3 |
| users | 70000 | 70036 | 36 |
| ingestion_errors | 0 | 0 | 0 |
| loan_products | 3 | 3 | 0 |
| product_criteria | 3 | 3 | 0 |
| matches | 93114 | 93173 | 59 |
| notification_events | 23114 | 23137 | 23 |
| workflow_outbox | 14 | 20 | 6 |
| crawler_runs | 33 | 36 | 3 |
| workflow_run_audit | 14 | 20 | 6 |

The three shared fixture products/criteria were upserted by A, refreshing their retrieval evidence without changing historical evaluated-match snapshots. All pre-existing per-job fingerprints were compared independently of global count growth. The original Mailpit retained the same 15000 capture IDs; its container, PostgreSQL and MinIO were not restarted. Existing named-volume mappings were preserved.

## Installed workflow versions

| Workflow | Active version |
|---|---|
| loan-workflow-a | `09c6bfbd-9886-4c21-91db-94219d453bd0` |
| loan-workflow-b | `c090133d-c946-4154-9fcb-e7b0cb126d81` |
| loan-workflow-c | `9ab34225-0629-470b-8eda-8156fd1df182` |

The exact approved export SHA-256 values are recorded in the JSON report. Node and connection equality was checked after installation, and active versions were checked again at completion. No credential import or password rotation occurred.

## Commands and exact regression results

The JSON command ledger records executed build, service and import/publication commands, exit codes and durations. Private paths are intentionally replaced by `<private-backup>`. The private test harnesses and diagnostic logs are retained; their SHA-256 hashes and invocation arguments are recorded without exposing the backup location. All recorded commands exited 0. Representative actual installation commands:

```powershell
docker image tag sha256:92ea277eebadc69dd17d134a67eae84d6486d4e3525d4373b4511149e7efe72e loan-engine-app:pre-integration-20261021
docker compose build api
docker compose stop dispatcher ingestion-worker n8n
# Compose operations used the private safety override; only named services were started with --no-deps --no-build.
# Workflow import/publication ran in one-shot n8n containers with the existing credentials/database and no published ports.
docker compose -f docker-compose.yml -f <private-safety-override> run --rm --no-deps --entrypoint n8n n8n import:workflow --separate --input=/workflows/workflows
docker compose -f docker-compose.yml -f <private-safety-override> run --rm --no-deps --entrypoint n8n n8n publish:workflow --id=loan-workflow-a
docker compose -f docker-compose.yml -f <private-safety-override> run --rm --no-deps --entrypoint n8n n8n publish:workflow --id=loan-workflow-b
docker compose -f docker-compose.yml -f <private-safety-override> run --rm --no-deps --entrypoint n8n n8n publish:workflow --id=loan-workflow-c
```

Regression command sequence (the captured test URL is not printed):

```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
$env:PYTHONPATH="backend;."
$env:LLM_ENABLED="false"; $env:N8N_SES_ENABLED="false"
$env:TEST_DATABASE_URL = & .\.venv\Scripts\python.exe -c "from dotenv import dotenv_values; print(dotenv_values('.env')['DATABASE_URL'].rsplit('/',1)[0]+'/loan_test')"
.\.venv\Scripts\python.exe -m pytest -q -k "not test_10000_ingestion_and_idempotency and not test_supplied_csv_inspection and not test_actual_mailpit_preview" --junitxml=reports/integration-pytest.xml
.\.venv\Scripts\python.exe -m ruff check backend scripts migrations
.\.venv\Scripts\python.exe -m mypy backend/app
.\.venv\Scripts\python.exe scripts/validate_workflows.py
.\.venv\Scripts\python.exe scripts/validate_config.py
docker compose config --quiet
node frontend/build.mjs
git diff --check
```

**Pytest:** 114 passed, 3 deselected, 2 warnings, 61.78 seconds, exit 0. The full-dataset ingestion, supplied CSV inspection and opted-in actual-Mailpit test were excluded; integration captures came only from the approved 23-message test. See [integration-pytest.xml](integration-pytest.xml). MyPy checked 16 application source files. All other listed checks exited 0. No migration upgrade or full-data script ran.

## Runtime and rollback status

Not required. Temporary boundary startup override removed; API runtime page size restored to 1000. Updated application/workflows and isolated Mailpit routing retained. Existing data and volumes preserved.

The original seven services and the new integration-mailpit service are healthy. The isolated inbox remains available at http://localhost:18025. API/worker SMTP routing intentionally remains directed to that inbox; the original inbox at port 8025 remains untouched. A future ordinary Compose recreation would lose the private SMTP safety override, so use the retained operator command/configuration rather than blindly recreating services. No additional sends or uploads are authorized by this report.

The five-candidate boundary setting was only a temporary API process startup override. The original uvicorn command and the progress endpoint both verify the restored 1000 default. The application files, .env and supplied users.csv were not modified by integration testing. Updated workflow definitions and synthetic records/captures are retained. Backups and private configuration stay outside Git; their location is deliberately omitted. The backup restoration drill remains unperformed.

## Remaining unverified requirements

- Browser-driven dashboard interaction: the identical upload API/presigned PUT/completion protocol was exercised through HTTP.
- Actual AWS SES delivery/received external email: disabled, not attempted.
- Permitted live lender crawling: disabled, not attempted.
- Live LLM API/provider contract: disabled, not attempted.
- AWS deployment/cloud resources: not attempted.
- Multiple live 1000-candidate pages and larger-data load testing: tiny boundary instrumentation plus isolated regressions only.
- Backup restoration drill: catalogs/checksums verified; no restore performed.

SES remained disabled in the API and in the official n8n node, and no n8n AWS credential exists. No SES-node execution, live-source node execution or LLM request was part of the run. Evidence is transport configuration and executed-node tracing, not packet-level egress monitoring. Mailpit is local SMTP capture and does not demonstrate AWS SES or external inbox delivery.

No AWS deployment, external email delivery, live lender crawling, paid API, supplied-data replay, credential rotation, database reset, volume deletion, commit or push was performed. The controlled local integration gap is closed within this stated scope; full assignment compliance still depends on the external requirements above.
