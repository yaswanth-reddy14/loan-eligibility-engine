# Post-cleanup report

Date: 20 October 2026. Branch: `refactor/submission-cleanup`.

**Result: the local fixture pipeline is ready for a technical walkthrough, subject to manual browser rehearsal. The full assignment remains incomplete.** No AWS deployment, real SES receipt, permitted live crawl, browser interaction or recorded demo is claimed.

## Before and after

| Measure | Before | After |
|---|---:|---:|
| Project files, excluding `.git` and `.venv` | 2,219 | 140 |
| Git-visible submission files | 111 | 137 |
| Original tests passing with PostgreSQL and Mailpit | 69 | 69 |
| Source/build files refined | - | 7 |
| Generated files safely removed | - | 2,109 |
| Application/test/migration/workflow source files deleted | - | 0 |
| Historical reports preserved in an archive | - | 28 |

The submission file count increased because historical evidence is separated from fresh reports and explicit cleanup/index documents were added. The physical file count fell after removing caches and duplicate build/log output. The 2,109 removals include generated files recreated during verification; they are not 2,109 deleted source files.

## Backup and preservation

Baseline commit **`7f79b0c`** preserves the original Git-visible state. A checked local backup at `C:\Users\DELL\.codex\backups\loan-eligibility-engine\submission-cleanup-20261020` also preserves ignored private inputs, reports and the prior Lambda artifact. Installed `.venv` files and named Docker volumes were not deleted. `.env` and `users.csv` still match the backup exactly.

The sole matching Downloads folder, `C:\Users\DELL\Downloads\docs`, still contains all 13 original documents with unchanged SHA-256 hashes, including the demo script, final audit and checklist. It was not edited or moved.

This cleanup used coding-agent assistance. The commits record the actual baseline and cleanup work; no past history or exclusive authorship was invented.

## Files removed and why

| `.mypy_cache` | 2,033 | Regenerable Python or tool cache |
| `.pytest_cache` | 6 | Regenerable Python or tool cache |
| `.ruff_cache` | 7 | Regenerable Python or tool cache |
| `frontend/dist` | 3 | Regenerable static build output |
| `backend/app/__pycache__` | 12 | Regenerable Python or tool cache |
| `backend/tests/__pycache__` | 6 | Regenerable Python or tool cache |
| `migrations/__pycache__` | 3 | Regenerable Python or tool cache |
| `migrations/versions/__pycache__` | 2 | Regenerable Python or tool cache |
| `scripts/__pycache__` | 1 | Regenerable Python or tool cache |
| `reports/*.txt` | 36 | Regenerable command logs; copied to private local backup, structured reports preserved |

Detailed paths and sizes are in the private backup's `removed-files.json`; non-cache logs/build output were also saved to `removed-generated-output.zip`. [Removal summary](../reports/cleanup-removals.json) records the checked workspace scope and counts. Recursive targets were resolved and verified inside the project before deletion. Tool caches and `frontend/dist` will regenerate when checks/builds run again.

Fifteen obsolete root report paths were relocated to the archive rather than discarded. All 28 archived JSON/XML files match their original committed bytes. The initial Docker-startup failure and the successful baseline are retained separately. No report was rewritten to turn a failed execution into success.

## Source, configuration and dependency changes

| Files | Change / reason |
|---|---|
| `backend/app/cloud.py` | Replace a one-iteration loop with one dispatcher call; invocation count and result remain the same. |
| `backend/app/notifications.py` | Count pending rows in SQL instead of materializing their IDs. Job locking, states, limits, recipient selection and deduplication are unchanged. |
| `frontend/app.js`, `build.mjs`, `index.html`, `style.css`, `package.json` | Format the compressed existing source for readable functions, markup and styles. No new UI behavior or framework. Prettier 3.6.2 was used as a temporary formatting tool, not a runtime dependency. |
| `docker-compose.yml` | Remove the unused n8n WORKFLOW_SECRET environment entry. All stored workflows were checked for references; header credentials still authenticate A/B/C. The app secret and encrypted n8n credential remain. |
| `backend/requirements-dev.txt`, `pyproject.toml` | Remove unused `pytest-asyncio` and its configuration option. No async tests/marks/imports exist; its installed distribution was uninstalled, and the same 69 test cases pass. |
| `.gitattributes`, `.gitignore` | Define repository line endings and exclude common coverage output. Private inputs, artifacts and caches remain ignored. |

Seven source/build files were refined, plus five configuration/dependency files. No runtime dependency was removed. Naive matching, the legacy authenticated fixture route, security helpers, verification scripts, fixtures and immutable migration metadata were retained after checking their roles. They were not deleted merely for looking duplicated or generated.

The original 69 test cases and every original test file are unchanged. Byte checks also confirm unchanged matching SQL/rules, ingestion/validation/models/worker, migrations and A/B/C exports. [Source checks](../reports/cleanup-source-checks.json) identify the preserved files.

## Documentation consolidation

README is now the entry point. `IMPLEMENTATION_STATUS.md` links to current verification rather than repeating stale job/timing tables. `DELIVERY_AUDIT.md` groups requirements and points to the detailed recruiter review. The final recruiter audit remains a clearly dated snapshot with links to immutable archived evidence. Current commands write to `reports/`, never into the archive.

The working demo checklist and eight-minute script remain practical and explicit about job IDs, fictional products, timing limits and Mailpit. Stale artifact byte sizes and an obsolete nine-minute reference were removed. Deployment/security documentation keeps all external prerequisites and limitations. [Scripts](../scripts/README.md) and [evidence](../reports/README.md) now have concise purpose indexes. Nine existing documentation files were improved; four new planning/index/report files were added.

The original delivery/audit text remains available in the baseline commit and the untouched Downloads backup. No implementation or authorship evidence was concealed.

## Tests and actual runtime results

| Verification | Observed result / evidence |
|---|---|
| Complete suite | **69 passed, zero failures/errors/skips**. Original test names match the baseline. Existing TestClient/botocore deprecation warnings remain. [checks.json](../reports/checks.json), [JUnit](../reports/pytest.xml). |
| Quality/configuration | Ruff, mypy, workflow graph validation, Compose configuration, static Serverless invariants, frontend syntax/build, Alembic upgrade and drift all passed. Cold migration downgrade/re-upgrade remains covered. |
| Dependency consistency/security | `pip check` passed. Runtime requirement audit found zero known findings; it is not an image or production security certification. |
| Supplied CSV | 10,000 valid rows, zero duplicate external IDs, same SHA-256. Repeated email values are expected input characteristics, not duplicate user IDs. |
| Fresh ingestion | Job **`cf5351fc-21b4-476e-a990-63c7fdb92cf0`**, accepted 10,000, rejected 0. [E2E report](../reports/e2e.json). |
| Matching | **13,302** outcomes: 10,000 REVIEW_REQUIRED and 3,302 POSSIBLY_ELIGIBLE. Independent per-pair oracle agrees; no duplicate matches. |
| n8n | A fixture execution **85**, B **86**, delivery batch executions through **120**, and successful B/C replay recorded. The independent report also includes final C replay **123** and sums actual batch sends. All exports imported/published on 2.43.6; stored nodes/connections match the files. |
| Optimization | 30,000 -> 13,302 advanced candidates: **55.66%**. Five measured comparison runs retain equal outcomes; medians were naive **0.570607 s**, optimized **0.537874 s**. These local measurements exclude n8n/persistence/delivery and do not establish a stable whole-pipeline speedup. |
| Controlled notifications | **3,302** SENT events matched to this job's Mailpit Message-IDs. Allowlist verified; sample HTML/plain-text content checked. Actual AWS SES receipt remains unverified. |
| Replay safety | B/C replay added **zero** SENT events. Original completed jobs still each have 10,000 users and 3,302 SENT events. |
| Docker/API/assets | **Seven healthy services** after rebuild. Authenticated job-scoped counts match the DB; root/HTML/JS/CSS load over HTTP and match source; unauthenticated API rejected, `.env` URL 404. |
| Linux Lambda | Build passed; **36,704,572 bytes** zipped. Current sources/native modules imported in the AWS Python 3.12 base container; root 200, unauthenticated API 401, empty SQS batch passed. [Artifact report](../reports/lambda-artifact.json). No AWS service calls. |
| Browser/media | Available inventory was `apps=[]`, `browsers=[]`. No drag/drop interaction, visual/accessibility QA, screenshot or recording was fabricated. |

Fresh upload-to-last-SENT time was **252.408 s**; the observer including discovery and mailbox checks took **260.641 s**. These are one local run, not throughput promises. Mailpit's total mailbox count includes historical jobs and QA; it is not the notification count for this job.

The first check attempt encountered a stopped Docker daemon. It is retained in `cleanup-startup-checks.json`. Starting Docker Desktop and the existing stack resolved the infrastructure failure; baseline and subsequent full checks passed without changing assertions. No application regression remains from this cleanup.

## Functionality and remaining gaps

Direct signed uploads, atomic batched ingestion, job/version snapshots, SQL filtering, conservative unknown handling, B completion gating, durable retry/progress state, safe grouped delivery, source evidence, credentials, validation and auditability are preserved. No lender rules were invented, sample email addresses selected as destinations, or database volumes reset.

Still incomplete: permitted live lender discovery and verified real criteria; deployed AWS/private RDS integration and resolved infrastructure/IAM tests; real SES delivery and controlled external inbox receipt; browser rehearsal/visual QA; recorded demonstration and remote private submission/CI evidence. Production auth/TLS, monitoring/restore/retention, supported PostgreSQL upgrade, larger candidate partitioning and ambiguous-send reconciliation remain operational work. The prior 80/100 estimate is preserved, not presented as an awarded or newly increased score.

**Demonstration readiness:** the local API/n8n/database/Mailpit walkthrough is reproducible. Complete the manual browser checklist and recording before claiming a finished hiring submission. [Checklist](DEMO_CHECKLIST.md) and [spoken script](demo-script.md).

## Exact commands

From the project root in PowerShell, with Docker Desktop running:

```powershell
$env:PYTHONPATH = 'backend;.'
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
.\.venv\Scripts\python.exe scripts/import_n8n.py
# Wait for n8n health after the importer restarts it.
$env:RUN_MAILPIT_TEST = '1'
.\.venv\Scripts\python.exe scripts/run_checks.py
.\.venv\Scripts\python.exe scripts/demo.py --timeout 900
.\.venv\Scripts\python.exe scripts/verify_workflow_replay.py
.\.venv\Scripts\python.exe scripts/recruiter_verify.py
.\.venv\Scripts\python.exe scripts/benchmark.py
powershell -ExecutionPolicy Bypass -File scripts/package_lambda.ps1
.\.venv\Scripts\python.exe scripts/verify_lambda_artifact.py
.\.venv\Scripts\python.exe scripts/audit_secrets.py
docker compose ps
```

`demo.py --job-id <id>` observes an existing dashboard upload instead of creating another. The supplied private CSV and local `.env` are required but remain uncommitted. Setup, import, tests and packaging can be run separately; none deploys paid resources or sends external email.

## Final Git state

The reviewed cleanup is committed locally on `refactor/submission-cleanup`; the working tree is clean. No remote is configured, and no publication or invitation occurred. Baseline `7f79b0c` remains available for comparison/rollback. Inspect the exact final commit and status with:

```powershell
git status --short
git branch --show-current
git log -2 --oneline
git diff 7f79b0c..HEAD --stat
```

Private inputs, local artifacts, caches, raw logs and volumes are not tracked. Known-value secret scanning and local documentation-link checks are recorded with the final verification metadata; their scope does not imply a universal security audit.
