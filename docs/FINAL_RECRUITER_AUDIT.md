> Historical review snapshot from 19 October 2026. Its evidence is preserved in `reports/archive/pre-cleanup`. See [POST_CLEANUP_REPORT.md](POST_CLEANUP_REPORT.md) for the 20 October cleanup, fresh validation and current Git state. The Downloads backup is untouched.

# Final recruiter audit

Review date: 19 October 2026. Scope: local repository, the original attached assignment, README, DELIVERY_AUDIT, code/configuration, PostgreSQL, pinned n8n runtime and controlled Mailpit. This is an independent follow-up to the historical delivery report, with targeted fixes rather than a rebuild.

**Verdict: the local fixture pipeline is demonstrated; the full assignment remains incomplete.** Live permitted lender discovery, deployed AWS integration, actual SES inbox receipt, manual browser validation, and recorded submission media are not proven. Do not present seven healthy containers or passing unit tests as substitutes for those requirements.

## Estimated evaluation score

The compact machine-readable review is `reports/archive/pre-cleanup/final-review.json`.

These are strict engineering estimates using the assignment's four category weights, not an awarded hiring score. A panel's treatment of external integration gaps can change the result materially.

| Category | Estimate | Supporting evidence and deductions |
|---|---:|---|
| n8n automation | **23/30** | All three actual exports imported/published on 2.43.6; stored nodes/connections equal the files. Successful retained A fixture fetch/extract, B SQL/Code/persist/ack and C delivery nodes. Auth rejection and replay deduplication proven. Deduct for zero approved live sources, no successful live discovery, bounded aggregate candidate execution, and C being primarily an authenticated service orchestration wrapper. |
| Cloud architecture | **14/20** | Practical S3/SQS/DLQ/Lambda/private-network parameters, partial failure adapter, scoped application permissions and clear RDS/n8n deployment boundaries. Static checks pass. Deduct for no resolved/deployed Serverless stack, limited local artifact smoke, no RDS/private connectivity evidence, no SES identity/send/receipt evidence, and slow scheduled cloud dispatch. |
| Backend quality | **26/30** | 69 passing tests, real PostgreSQL integration, atomic ingestion, snapshots, independent pair oracle, bounded persistence, idempotency, guarded notification states, migration rollback test and dependency remediation. Deduct for operator-only auth/rate limiting, incomplete operations/retention/recovery automation, a 50,000-candidate n8n ceiling and no concurrent cloud/load qualification. |
| Documentation and demo | **17/20** | Reproducible PowerShell checklist, measured reports, precise source/delivery caveats and an eight-minute spoken script. Deduct for no recorded video/screenshots, unverified browser interaction and no remote CI/submission evidence. Historical docs are explicitly marked superseded. |
| **Total** | **80/100** | Strong local evidence; material discovery/cloud/delivery gaps remain. |

## What was independently verified

Fresh reviewed job: **`a4134ee6-dcfe-445e-bfea-d77d3283af1c`**. Historical baseline job: `83628220-3ebb-4046-8b58-727fd0abdf50`. Repeated uploads deliberately create separate user snapshots. Never sum multiple jobs and call the result one 10,000-user ingestion.

| Assertion | Actual evidence |
|---|---|
| Supplied file | SHA-256 `31e4b00ee000ec0478262bcc629073e76920201b05978a816a3ad4c0133d1ec9`; verifier compares the file with the job checksum. |
| Ingestion | 10,000 accepted, zero rejected, 10,000 distinct external IDs in the fresh job. Ingestion interval 6.694 s; upload-job creation to last SENT record 307.531 s on this run. Those are local observations, not performance guarantees. |
| Outcome consistency | 10,000 REVIEW_REQUIRED for Fictional Incomplete Finance; 1,116 POSSIBLY_ELIGIBLE for Fictional Independent Finance; 2,186 POSSIBLY_ELIGIBLE for Fictional Salaried Finance. Total 13,302. The two complete products have disjoint employment requirements here, so 3,302 distinct eligible users receive 3,302 grouped notifications. Review rows do not email. |
| No accidental duplicates | Zero duplicate persisted pair/status tuples; uniqueness keys include job/user/product/version. The independent verifier checks all pairs and expected distinct notification users. Repeated CSV email values are real input characteristics, not duplicate user IDs. |
| Source integrity | All three loaded products are DEMO_FIXTURE with bundled HTML and criterion evidence. No real lender qualification threshold is invented or marked VERIFIED. Live products remain UNVERIFIED and are excluded from production matching. |
| Genuine n8n | Retained B execution **43**, A fixture execution **71**, and final C execution **84** have successful node metadata. 39 retained C executions (including zero-send replays) report a summed 3,302 sends; `notification_batch_executions` lists each ID and count. Execution 84 is a completed zero-send replay, while the earlier batch executions performed delivery. `reports/archive/pre-cleanup/workflow-import.json` records export hashes, published versions and equality with stored nodes/connections. `reports/archive/pre-cleanup/recruiter-verification.json` links runtime IDs and audits. |
| Received local messages | All 3,302 fresh-job provider Message-IDs found in Mailpit, with controlled recipients. Sample Mailpit ID `J5hMXaYVGeh7XPnieGuboN` has both HTML and plain text with disclaimer. `mailpit_total=6613` includes other jobs and QA mail and is not the job's delivery count. |
| Latest startup and HTTP smoke | `reports/archive/pre-cleanup/setup-reviewed.json`: PowerShell setup exit 0 with existing volumes preserved. `reports/archive/pre-cleanup/reviewer-smoke.json`: seven healthy services; served JS and container app sources match the repository; root 200, unauthenticated API 401, absent workflow payload 422, private .env path 404, correctly scoped counts. This is not browser interaction. |
| Replay/authentication | `reports/archive/pre-cleanup/n8n-replay.json`: unauthenticated webhook rejected; successful B/C replay left database SENT count unchanged at 6,604 across the two completed jobs. |
| Regression | `reports/archive/pre-cleanup/checks.json` and `reports/archive/pre-cleanup/pytest.xml`: **69 passed, zero failed/errors/skipped** with RUN_MAILPIT_TEST=1. Ruff, mypy, workflow structure, frontend syntax/build, Compose validation, Alembic upgrade/drift all pass. |
| Local Lambda artifact | `reports/archive/pre-cleanup/lambda-package.json` and `reports/archive/pre-cleanup/lambda-artifact.json`: 36,701,532-byte zip (85,160,744 bytes uncompressed), native psycopg/pydantic_core imports, ASGI root 200, unauthenticated API 401, empty SQS batch success. Source members match the current repository. AWS base container Python 3.12.15, x86_64; no AWS services called. |
| Migrations | Empty isolated schema upgraded 0001 -> 0002, downgraded to 0001, re-upgraded and checked for drift. Existing local database upgraded in place. No user volumes/databases were reset. |
| Dependency scan | Earlier runtime requirements: seven Starlette findings. FastAPI 0.148.0 / Starlette 1.9.0 now scan with zero known findings in `reports/archive/pre-cleanup/dependency-audit-after.json`. This scans resolved Python runtime requirements; it does not certify container OS images, n8n, or all future transitive resolutions. |

The initial fresh upload's status observer encountered `RemoteProtocolError`; the API remained running and was not OOM-killed. The cause was not established. Resuming with `--job-id` verified the same upload without duplicating it. Read-only polling now retries transport interruptions within the deadline. The E2E report labels its observer elapsed time separately from the original upload-to-last-SENT interval. The observed failure was not rewritten as an uninterrupted success.

## Optimization result and its limits

The SQL pipeline reduced the **distinct candidate pairs reaching advanced rules** from 30,000 to 13,302: **55.66%**. A separate Cartesian oracle implements all known bounds directly, without calling production `advanced` or `naive_pairs`, and compares complete user/product/status sets with persisted outcomes. Both complete and incomplete criteria are checked. This establishes decision equivalence for this dataset and loaded fixtures, not all possible lender policies.

The benchmark also asserts pair/status equality, uses one warmup and five measured runs, and retains EXPLAIN ANALYZE. It shares advanced-rule code with production, which is why the additional independent oracle matters.

| Local measurement | Naive median | Optimized median | Interpretation |
|---|---:|---:|---|
| `reports/archive/pre-cleanup/benchmark-under-load.json` | 0.605741 s | 0.638355 s | Optimized was slightly slower while the pipeline and checks ran. |
| `reports/archive/pre-cleanup/benchmark.json` | 1.322653 s | 0.869663 s | Follow-up overlapped app image build/startup; highly variable local timings. |

These measurements do **not** establish a stable wall-clock speedup. They exclude n8n execution, persistence and delivery. Production also performs a second SQL pass to validate n8n's proposals, so 55.66% must not be represented as total physical database comparison savings. Its meaningful benefit is fewer pairs transferred to advanced application evaluation. SQL cursor timing includes execute/fetch/client transfer; production metrics exclude persistence from that field. EXPLAIN now runs only in the benchmark. No measured LLM savings exist: the LLM is disabled; “calls avoided” is explicitly a hypothetical one-call-per-Cartesian-pair baseline.

## Defects fixed during this review

| Severity before fix | Defect and resulting behavior | Files / regression evidence |
|---|---|---|
| High | The demo script directly seeded products, so the claimed A demo could bypass n8n. Dashboard and script now invoke A's authenticated fixture webhook; A actually fetches three HTML responses, normalizes each item, and submits validated extraction/upserts with its execution ID. All live sources remain gated. | `scripts/demo.py`, `scripts/generate_workflows.py`, `backend/app/discovery.py`, `backend/app/main.py`, A JSON; successful retained A execution and fresh crawl rows. |
| High | Matching HTTP accepted an absent evaluation payload, permitting direct backend matching. It now requires n8n evaluations plus a valid-shaped execution ID. The trusted shared secret remains the authentication boundary; an ID alone is not cryptographic proof of provenance. Actual execution metadata independently proves the reviewed run. | `backend/app/main.py`; `test_http_matching_requires_orchestrated_payload`. |
| High | C could be enqueued during B persistence, before later B nodes failed. B now records PERSISTED, validates metrics, then acknowledges in its final node; only that acknowledgement completes B and queues C. | `backend/app/matching.py`, B generator/export; `test_c_not_queued_until_final_b_ack`. |
| High | A stale RUNNING audit could repeatedly reset outbox retry attempts. New migration 0002 records a monotonic progress_count; attempts reset only on newly observed sent_total progress. Stalled dispatches exhaust a bounded budget. | `backend/app/worker.py`, models, `migrations/versions/0002_outbox_progress.py`; stale-progress/new-progress tests. |
| High | Runtime dependency scan found seven advisories in the previous Starlette version. Compatible FastAPI/Starlette pins were upgraded; regression tests and follow-up scan passed. CI now includes pip-audit. | `backend/requirements.txt`, requirements-dev, `.github/workflows/ci.yml`, before/after audit JSON. |
| Medium | Live A normalization processed only one source item. Per-item Code processing now preserves source pairing. Conservative labeled extraction supports age, employment and starting/range rates with evidence; unlabeled marketing stays unknown. Fetch failures have an audit branch. | Generator, `backend/app/discovery.py`, extraction tests. Live source failure branch remains unexercised against real permitted lenders. |
| Medium | The n8n read credential had table-wide user SELECT access. It now receives only the six columns needed for candidate generation, excluding names and contact addresses. The existing role was narrowed and tested: candidate count 13,302; name/email query denied. | `scripts/import_n8n.py`, `reports/archive/pre-cleanup/n8n-db-permissions.json`. |
| Medium | Notification presentation could read changed live product fields after matching. New matches retain typed product snapshots, and messages use evaluated presentation/source fields. Legacy rows retain an explicit fallback. | `backend/app/matching.py`, `backend/app/notifications.py`; snapshot immutability test. |
| Medium | Concurrent notification batches could publish inconsistent terminal counts. Final count/audit updates now serialize on the job row. | `backend/app/notifications.py`; concurrent two-batch regression. |
| High | The documented Lambda build failed on Windows after pip installation because nested PowerShell/shell/Python quoting broke. It now uses Python orchestration and Docker stdin, a cached wheel volume, read-only source mounts, and excludes bytecode/frontend build copies. The zip passed a local AWS base-container smoke. | `scripts/package_lambda.ps1`, `scripts/package_lambda.py`, `scripts/verify_lambda_artifact.py`; package/artifact JSON. |
| Medium | SQS returned retryable failures without durable job error state. Registered jobs now record sanitized errors/attempts, RETRY or FAILED at the configured fifth receive, while retaining partial batch failures; recovery clears the old error. No source email is logged. | `backend/app/ingestion.py`; recovery and final-receive regressions. |
| Medium | Duplicate-row reports could point to the wrong row in a batch. Returned external IDs now map to exact source rows. Checksum mismatch rollback also has a direct regression. | `backend/app/ingestion.py`; duplicate-line and bad-hash regressions. |
| Medium | Dashboard aggregated review outcomes as preliminary matches, mixed jobs, and could imply Mailpit for SES mode. It now separates review/possible outcomes, scopes a chosen job, defaults to the latest job and labels the configured delivery mode. Discovery history comes from actual records. | `frontend/app.js`, index, `backend/app/main.py`; API/build checks. Actual browser interaction remains unverified. |
| Medium | Hardcoded localhost CSP would block hosted S3 PUTs. The policy now permits the configured storage origin or regional AWS bucket origins. | `backend/app/main.py`; configured/local/cloud-origin regression. Real cloud browser PUT still unverified. |
| Medium | E2E only checked that any old Mailpit mail existed. It now correlates every job notification Message-ID with captured mail, validates recipients and one multipart body, and supports observing an existing dashboard job. | `scripts/demo.py`, fresh E2E report. |

## Missing or only partially satisfied requirements

High means a material explicit assignment gap or serious production risk; medium means an important validation/operational gap; low means a smaller submission or maintainability issue. Intentional limits remain listed even when authorization prevents resolving them here.

| Severity | Requirement / evidence still missing | Exact next step / dependency |
|---|---|---|
| **High** | Two or three permitted, accessible official lender sources and successful real Workflow A discovery. All three configured sources are disabled; fixture discovery is not live discovery. | Review robots and published restrictions, retain dated accessibility/terms evidence, implement reviewed source-specific extraction fixtures/tests, enable only allowed sources, capture actual scheduled executions. `n8n/sources.json`, `docs/source-review.md`. Do not equate accessibility or robots allowance with permission. |
| **High** | Verified real lender eligibility criteria and official product/rate links in a real-product demonstration. Existing fixture thresholds prove mechanics only. | Establish criterion evidence and completeness through source review. Keep unknown rules null/REVIEW_REQUIRED and live products UNVERIFIED until independently verified. |
| **High** | AWS deployment and actual S3 -> SQS -> Lambda -> RDS -> private n8n/API -> SES evidence. A Linux artifact build and local AWS base-container import/ASGI smoke passed; Serverless resolution and deployment have not been tested. | User authorization for paid resources, authenticated account, resolved parameters/SSM secrets, Linux packaging, private RDS/compute/network, deployed events, retries/DLQ and logs. Static YAML validation is insufficient. |
| **High** | Actual AWS SES delivery and controlled external inbox receipt. | User's explicit send authorization, sender/recipient verification, approved SES permissions/network and actual received-inbox evidence. Mailpit and SDK mocks prove neither SES nor external receipt. |
| **Medium** | Dashboard upload performed in a browser, visual/responsive/accessibility QA, screenshots and recorded demo/video link. | Manual checklist in `DEMO_CHECKLIST.md`; the available browser inventory was empty. HTTP API upload and JS/build validation are tested; actual drag/drop/XHR/rendering are not claimed. |
| **Medium** | Runtime validation of A's approved live HTTP branch, timeout/error audit path and daily schedule with permitted real pages. | A fixture path and historical blocked-source path have run; obtain permitted sources and exercise successes/failures separately. Importability is established, not every branch's runtime behavior. |
| **Medium** | Production operability: alarms, heartbeat/progress health, automated ambiguous-send reconciliation, backup restore and data deletion/retention across DB/n8n/Mailpit. | Add a tested runbook and monitoring. UNKNOWN/SENDING events require operator reconciliation; never blanket reset them to PENDING. Worker DB checks prove connectivity, not progress. |
| **Medium** | B scalability beyond 50,000 candidates, stable isolated performance/load measurements. | Partition candidates with durable cursors or batches and measure equivalence/throughput before claiming scale. SQL aggregate is capped at 50,001 to fail safely; 2 MB HTML bounds are checked after n8n fetch, not an asserted download memory cap. |
| **Medium** | Supported n8n PostgreSQL baseline and infrastructure/image vulnerability qualification. | n8n warns PostgreSQL 16 receives compatibility support only. Plan backup/restore and a tested PostgreSQL 17+ upgrade; changing an image tag on the existing volume is unsafe. Scan images separately. MinIO source-build/release provenance and future maintenance remain external dependencies. |
| **Medium** | Production authentication/rate limiting/TLS and least-privilege service/database operation. | Operator bearer token and in-process IP limits are local conveniences. Use identity-aware access, shared throttling, TLS and narrower DB roles; protect n8n editor/credential editing. N8N_BLOCK_ENV_ACCESS_IN_NODE=false is intentional for these workflows and increases editor trust requirements. |
| **Medium** | Timely cloud outbox draining and recovery under real Lambda/network failures. | `backend/app/cloud.py` dispatches one event per one-minute schedule; 34 notification batches can require at least roughly 34 schedule opportunities plus acknowledgements. Replace with a measured bounded drain/event-driven design when deploying. Local polling latency is different. |
| **Low** | Remote GitHub Actions evidence, private repository publication and collaborator access. | CI configuration exists, local equivalents pass. At the original review, repository files were untracked and there is no submitted remote/CI run. Obtain explicit publication/invitation authorization; follow README private submission instructions. |
| **Low** | Exact dependency/image/toolchain reproducibility and deprecation cleanup. | Direct runtime pins exist; transitive packages/image tags and Serverless CLI are not fully locked. Pin/test Linux artifact tooling, maintain lock updates, and address the httpx TestClient deprecation on a tested schedule. |

The optional LLM is disabled. That is not a missing mandatory requirement and no model-call success is claimed. No paid deployment, external email, publication or collaborator invitation was attempted because the original instructions require explicit authorization for those actions.

## Security and reliability assessment

Positive controls: generated keys and five-minute object PUTs, checksum/size/schema enforcement, immutable job inputs, parameterized SQL, bounded insertion batches, job locks, unique match/notification/outbox keys, shared-secret workflow authentication, read-only n8n matching DB credential limited to required user columns, allowlisted recipient construction, HTML escaping and preliminary disclaimers. Compose ports bind to loopback. AWS YAML includes encrypted/private/versioned/TLS-only S3, source-account/ARN-scoped queue access, encrypted queues, DLQ, partial batch responses and visibility timeout 720 s for function timeout 120 s.

Residual risks: local PostgreSQL/application administration shares a powerful DB account; VPC execution managed IAM policy is broader than final least privilege; n8n editor access can reach injected workflow environment values; local HTTP and disabled secure cookies must stay local; the workflow ID header/body is trusted internal data. Match audit decisions and product snapshots are preserved, but product edits during n8n evaluation can cause a safe rejected proposal/retry rather than a consistent long-running product snapshot. No multi-tenant authorization, production security/load audit, container CVE scan, backup restoration, AWS IAM simulation or disaster recovery exercise was performed.

Notification batches are count-bounded, but a slow sequence of successful SMTP calls could exceed n8n's HTTP timeout. Exercise delivery time budgets, overlapping retries and cloud failure alarms before production. An SQS job marked FAILED on its fifth receive needs explicit operator reconciliation and RETRY before DLQ redrive; a DB outage may prevent its failure audit, while the SQS failure response remains authoritative.

The exact configured local secret values were scanned against git-visible files without printing them: zero hits in `reports/archive/pre-cleanup/reviewer-secrets.json`. `.env`, users.csv, .venv and frontend/dist are ignored. This is a bounded exact-value check, not a universal secret-detection claim. At the original review Git had zero tracked files/commits, so the submission must still be assembled and reviewed before publishing.

## Exact reproduction commands and source map

From the repository root in Windows PowerShell, with the local services available:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:RUN_MAILPIT_TEST = '1'
.\.venv\Scripts\python.exe scripts/run_checks.py
.\.venv\Scripts\python.exe -m pip_audit -r backend/requirements.txt --format json --output reports/dependency-audit-after.json
.\.venv\Scripts\python.exe scripts/validate_workflows.py
.\.venv\Scripts\python.exe scripts/import_n8n.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package_lambda.ps1
.\.venv\Scripts\python.exe scripts/verify_lambda_artifact.py
# Wait for n8n health after import/restart; then use a fresh job:
.\.venv\Scripts\python.exe scripts/demo.py --timeout 900
.\.venv\Scripts\python.exe scripts/recruiter_verify.py
.\.venv\Scripts\python.exe scripts/benchmark.py
.\.venv\Scripts\python.exe scripts/verify_workflow_replay.py
docker compose ps
docker compose logs --since 15m api ingestion-worker dispatcher n8n
```

For an existing dashboard job, use `scripts/demo.py --job-id '<id>'` instead of another upload. `recruiter_verify.py` reads E2E's job by default and supports `--job-id`; benchmark supports the same option. The independent oracle uses current criteria; do not edit products between a run and its verification. Execution payload retention is 24 hours; rerun instead of presenting expired history as current evidence. Setup and exact aggregate database commands are in `DEMO_CHECKLIST.md`.

| Concern | Exact implementation / proof |
|---|---|
| Upload/validation/storage | `backend/app/main.py`, `storage.py`, `validation.py`, `ingestion.py`; `reports/archive/pre-cleanup/csv-inspection.json`, E2E and PostgreSQL tests. |
| A discovery | `n8n/workflows/A_loan_product_discovery.json`, `scripts/generate_workflows.py`, `backend/app/discovery.py`, `n8n/fixtures/*.html`, `n8n/sources.json`; crawl rows and retained A nodes. |
| B matching | `n8n/workflows/B_user_loan_matching.json`, `n8n/advanced_rules.js`, `backend/app/matching.py`; independent report, benchmark samples/plan and audit. |
| C delivery | `n8n/workflows/C_user_notification.json`, `backend/app/notifications.py`; job-specific provider IDs, Mailpit sample and replay report. |
| Retry/state/concurrency | `backend/app/worker.py`, `models.py`, `backend/tests/test_review_regressions.py`; bounded progress, B acknowledgement and concurrent delivery tests. |
| Migration | `migrations/schema_v1.py`, versions 0001/0002, `backend/tests/test_migrations.py`; actual upgrade/downgrade/re-upgrade/drift checks. |
| Cloud/security | `serverless.yml`, `backend/app/cloud.py`, `scripts/validate_config.py`, `scripts/package_lambda.py`, `scripts/verify_lambda_artifact.py`, `docs/deployment.md`, `docs/security.md`; static config plus local Linux artifact smoke, without AWS service integration. |
| Demo/submission | `docs/DEMO_CHECKLIST.md`, `docs/demo-script.md`, README; manual capture and publication still pending. |

## Prioritized improvements

1. Complete permitted live source review and source-specific extraction with truthful uncertainty. This is the largest remaining n8n/recruitment gap.
2. Perform and capture the manual dashboard upload/visual check, then record the eight-minute demonstration with matching job IDs and actual n8n/Mailpit evidence.
3. Obtain authorization for an isolated AWS/SES test; verify the artifact on deployment, resolved infrastructure/IAM, private connectivity, event retries/DLQ, migrations and real inbox receipt. Keep costs and cleanup explicit.
4. Add operational heartbeat/alerts and a careful UNKNOWN-delivery reconciliation runbook; test backups/restores and supported PostgreSQL upgrade before production use.
5. Partition B candidate work, improve cloud dispatch throughput and measure isolated/concurrent workloads without overstating local timing samples.
6. Tighten runtime/editor/IAM/DB privileges and production auth/TLS, qualify images/toolchain, then prepare a reviewed private Git submission and remote CI run after authorization.
