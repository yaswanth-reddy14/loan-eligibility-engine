# Local commands

Run from the repository root with `$env:PYTHONPATH = 'backend;.'` and the project virtual environment. Start Docker Desktop before service checks. These entry points have distinct responsibilities; none deploys AWS or publishes the repository.

| Script | Purpose |
|---|---|
| `setup.ps1` | Generate missing local secrets, build once, start existing persistent services. |
| `init_storage.py` | Create/initialize the local bucket; used by Compose bootstrap. |
| `inspect_csv.py` | Inspect the supplied CSV without printing source identities. |
| `import_n8n.py` | Set up restricted local credentials and import/publish A/B/C; restarts n8n. |
| `generate_workflows.py` | Deterministic workflow exports from the shared SQL/source configuration. Run after workflow changes, not during every demo. |
| `validate_ses_preparation.py` | Offline SES draft, gates and policy-template validation; no AWS calls. |
| `validate_workflows.py` | Graph/official-node/auth structure; runtime import remains a separate check. |
| `run_checks.py` | Ruff, mypy, pytest, workflow/configuration/Compose checks, build and migrations. Set `RUN_MAILPIT_TEST=1` for the controlled SMTP test. |
| `smoke_api.py` | Root/assets/health and API authentication over HTTP; not browser interaction. |
| `demo.py` | Real fixture A plus signed upload/B/C, then correlate this job's Mailpit messages. `--job-id` observes an existing upload. Preview mode only. |
| `recruiter_verify.py` | Independent Cartesian oracle, duplicates/allowlist, n8n nodes/imports and summed C batch sends. Requires a fresh E2E report and retained executions. |
| `verify_workflow_replay.py` | Replays B/C for E2E's job and checks no new SENT events. Run after E2E has finished. |
| `benchmark.py` | One warmup plus five default measured equality runs and EXPLAIN ANALYZE. Supports `--job-id` and `--iterations`. |
| `audit_secrets.py` | Check Git-visible files against known local secret values without printing them. |
| `validate_config.py` | Static Serverless invariants; not resolved/deployed AWS verification. |
| `package_lambda.ps1` / `package_lambda.py` | Windows entry point / Linux artifact builder using Docker stdin. These are not duplicate implementations. |
| `verify_lambda_artifact.py` | Check source freshness/native imports/local ASGI in the AWS Python base container; makes no AWS service calls. |

Full command sequences: [README](../README.md), [verification commands](../docs/testing.md), [deployment](../docs/deployment.md). Evidence locations: [reports](../reports/README.md). Preserve database volumes and reconcile ambiguous email events before any manual retry.
