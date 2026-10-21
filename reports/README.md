# Verification evidence

This directory retains dated, sanitized evidence from distinct verification stages. Reports are not interchangeable: the historical 10,000-user run predates the current workflow graphs; the controlled 36-user integration verifies the updated graphs. Later bounded test runs do not repeat either end-to-end run.

Start with [integration verification](integration-verification.md) and [recruiter cleanup verification](recruiter-cleanup.md). The benchmark supports comparison reduction, not a pipeline runtime speedup.

Commands can replace their named reports. Preserve a baseline before rerunning them. `checks.json` and `pytest.xml` describe their recorded historical suite, not the newest bounded run.

| Current report | Producer / purpose |
|---|---|
| `checks.json`, `pytest.xml` | `scripts/run_checks.py`: checks and exact test results. |
| `csv-inspection.json` | `scripts/inspect_csv.py`: aggregate supplied-file inspection. |
| `api-smoke.json` | `scripts/smoke_api.py`: real HTTP status checks. |
| `e2e.json` | `scripts/demo.py`: one job, actual A/B/C work and job-specific Mailpit captures. |
| `recruiter-verification.json`, `workflow-import.json` | `scripts/recruiter_verify.py`: independent decisions and retained n8n/export evidence. |
| `n8n-replay.json` | `scripts/verify_workflow_replay.py`: authenticated replay and unchanged delivery counts. |
| `benchmark.json` | `scripts/benchmark.py`: measured samples, medians, equality and query plan. |
| `lambda-package.json`, `lambda-artifact.json` | Linux builder and AWS base-container smoke; no cloud deployment. |
| `dependency-audit-after.json` | `python -m pip_audit -r backend/requirements.txt --format json --output reports/dependency-audit-after.json`. |
| `secrets-audit.json` | Known configured local secret-value check, not a universal security scan. |
| `runtime-verification.json` | Dated service health, source equality, database privilege checks, documentation links and bounded local-history security review. Reproduce with the commands and SQL recorded in the report. |

The JUnit report omits the local machine hostname; test cases, counts and timings are retained.

No CSV records, personal inbox credentials or local environment values belong in evidence. Raw console logs are ignored and regenerable. n8n execution payloads expire after 24 hours; retained JSON proves the recorded run, while a fresh runtime check needs a new execution. Mailpit capture is separate from real SES/external inbox receipt.

The current E2E evidence re-observes a previously ingested job and reruns fixture discovery; it does not claim a fresh browser upload. The regression suite separately repeats 10,000-row ingestion in an isolated test schema. The independent verifier and safe B/C replay validate existing persisted outcomes without resending the job's messages.

## Current local integration and regression evidence

- `integration-verification.md`, `integration-verification.json`, `integration-pytest.xml`: approved 36-user integration, 59 outcomes, 23 isolated Mailpit captures, workflow export hashes and 114 tests at that stage.
- `recruiter-cleanup.md`, `recruiter-cleanup-checks.json`, `recruiter-cleanup-pytest.xml`: latest bounded local checks, 133 passing tests with three deliberate exclusions. No fresh full-dataset ingestion or external sends.
- `ses-iam-generated-baseline.json`: sanitized fixture consumed by `scripts/validate_ses_preparation.py` and existing tests. It is required for reproducibility, not an IAM policy to apply. The restricted unresolved template and [operator guide](../n8n/ses-test/README.md) remain in the submission.

Superseded technical-fix/preparation reports, installation plans, account-specific AWS diagnostics and raw preservation snapshots remain local and ignored. They are not submission evidence links. No local files were deleted. The latest external status is unchanged: account confirmation and regional identity/permission checks are unresolved; SES delivery, live sources and paid LLM calls are unverified.
