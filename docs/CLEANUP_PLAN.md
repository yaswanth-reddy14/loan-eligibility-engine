# Submission cleanup plan

Date: 20 October 2026. Branch: `refactor/submission-cleanup`.

## Safety and scope

The initial repository had no commits. A truthful baseline commit now preserves all 111 Git-visible files. A separate local backup at `C:\Users\DELL\.codex\backups\loan-eligibility-engine\submission-cleanup-20261020` contains the working files, including ignored CSV, environment, reports and Lambda artifact; it excludes the installed virtual environment, Git internals and regenerable caches. Docker volumes are preserved. The zip was checked for corruption.

The only matching Downloads backup is `C:\Users\DELL\Downloads\docs`. All 13 documents were fingerprinted, including the demo script, final recruiter audit and checklist. That folder will not be edited, moved or removed; hashes will be checked after cleanup.

Counts before cleanup, excluding `.git` and `.venv`: **2,219 physical files**, including **2,070 cache files**. The submission baseline has **111 Git-visible files**. These are different scopes; the final report will compare each consistently. `reports/cleanup-inventory.json` inventories all tracked source/configuration/evidence files, including Python definitions and imports.

The first check started while Docker Desktop was stopped. Start the daemon and existing services, then rerun checks. Infrastructure startup failures are not recorded as passing tests.

## Candidate decisions

| Candidate | Classification | Decision and reference verification |
|---|---|---|
| `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, project `__pycache__` / bytecode | SAFE TO REMOVE | Tool-generated caches, not application/build inputs. Exclude `.venv`; remove only resolved paths inside this workspace after final validation. |
| Ignored `reports/*.txt` | SAFE TO REMOVE | Recreated command output. Preserve the pre-cleanup copies in the external backup; structured JSON/XML evidence and Docker logs remain. Remove after commands stop writing. |
| `frontend/dist` | SAFE TO REMOVE | `build.mjs` copies the three source assets; FastAPI serves `frontend`, not `dist`. Build/test first, then remove the duplicate output. |
| Old JSON/XML reports | MUST PRESERVE | They establish the historical claims and failures. Archive original committed bytes under `reports/archive/pre-cleanup`, update historical documentation references, and regenerate current reports separately. Do not overwrite old measurements with new values. |
| `.serverless/loan.zip` | MUST PRESERVE | Explicit `serverless.yml` package artifact. Rebuild and smoke-test; retain locally and keep ignored. |
| `.env`, `users.csv`, `.venv`, named Docker volumes | MUST PRESERVE | Private configuration/data and working environment; never add to Git or delete. |
| `migrations/schema_v1.py` versus current models | MUST PRESERVE | Deliberate immutable migration snapshot, not duplicate dead code. |
| `n8n/workflows/*.json`, generator, advanced rules, HTML fixtures, source register | MUST PRESERVE | Required imports, build inputs and financial/source evidence. Check graph/import/runtime; preserve matching and node semantics. |
| `seed_fixtures` and legacy fixture API | MUST PRESERVE | Still an authenticated demo API and used by tests; the real demonstration continues to invoke n8n A. Removing an exposed route would change functionality. |
| `naive_pairs`, independent verifier, replay/smoke/packaging scripts | MUST PRESERVE | Distinct correctness or integration checks. Add a script index rather than deleting useful entry points. |
| `safe_csv_cell` | MUST PRESERVE | Explicit security guard with tests; useful for future exports. No export endpoint is claimed. |
| `pytest-asyncio` and its single pytest configuration option | SAFE TO REMOVE | No async tests, asyncio marks or plugin imports exist. Remove the declaration/unused option and verify all original 69 tests without the plugin. |
| Other dependencies | REQUIRES VERIFICATION | Keep: runtime entry points, direct imports, security version constraints and typing/build tools justify them. No speculative dependency removal. |
| n8n container `WORKFLOW_SECRET` environment entry | SAFE TO REMOVE | All webhook/HTTP nodes use the imported header credential; no workflow expression reads this variable. Keep the app setting, importer and credential. Verify authenticated runtime executions after removing this redundant exposure. |
| Compressed frontend assets | REQUIRES VERIFICATION | Format for readability without changing logic. Check JavaScript syntax/build and actual served assets. Browser interaction remains unverified if no browser surface is available. |
| Python simplification | REQUIRES VERIFICATION | Replace the single-iteration cloud dispatcher loop and count pending notification rows in SQL. Keep bounds, state transitions, locking, recipient selection and matching SQL unchanged. Run regression and E2E checks. |
| Repeated status/setup documentation | SAFE TO CONSOLIDATE | README is the entry point; implementation status links to current checks and remaining gaps. Keep the recruiter audit and initial delivery mapping as explicitly dated snapshots. Improve the spoken eight-minute script without changing evidence. |
| Empty `sample-data` directory | REQUIRES VERIFICATION | No files exist. Preserve the ignore exception for permitted future examples; do not manufacture or delete required fixtures. |

## Execution and validation

1. Complete baseline safety checks and preserve the exact original test names and workflow hashes.
2. Archive historical reports; make the bounded source/configuration/dependency/documentation changes above. Use consistent line-ending rules for new changes.
3. Run Ruff, mypy, all original tests, migration upgrade/drift, Compose/static Serverless validation and frontend build. Compare test names and workflow semantics with the baseline.
4. Build/start the local app once, import A/B/C into pinned n8n, and run a fresh supplied-file ingestion and controlled Mailpit pipeline. Verify 10,000 distinct IDs, 13,302 outcomes, 3,302 job-specific captures, candidate equivalence, 55.66% reduction, and replay deduplication.
5. Rebuild the Linux Lambda zip and smoke-test in the AWS base container. This is not an AWS deployment or SES proof.
6. Verify Git ignores/secrets, local documentation links, seven healthy services, retained required files and Downloads hashes. Remove only the generated files classified safe above, then write `POST_CLEANUP_REPORT.md` with actual counts/results and Git status.
7. Commit the reviewed cleanup locally. Do not publish, add a remote, send external email or invite collaborators.

Live lender crawling, AWS deployment, real SES receipt, browser validation and recorded demo evidence remain separate assignment gaps. No cleanup will relabel them as verified.
