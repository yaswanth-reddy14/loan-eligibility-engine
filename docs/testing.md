# Local verification

Run from the repository root with the virtual environment installed and PostgreSQL running. Use an explicitly disposable `loan_test` database, never the application or production database. The fixture creates and drops unique test schemas; it does not reset application history.

```powershell
$env:PYTHONPATH = 'backend;.'
$env:LLM_ENABLED = 'false'
$env:N8N_SES_ENABLED = 'false'
# Read the local connection privately and select the disposable database.
$env:TEST_DATABASE_URL = & .\.venv\Scripts\python.exe -c "from dotenv import dotenv_values; from sqlalchemy.engine import make_url; print(make_url(dotenv_values('.env')['DATABASE_URL']).set(database='loan_test').render_as_string(hide_password=False))"
.\.venv\Scripts\python.exe -m pytest -q -k "not test_10000_ingestion_and_idempotency and not test_supplied_csv_inspection and not test_actual_mailpit_preview"
.\.venv\Scripts\python.exe -m ruff check backend scripts migrations
.\.venv\Scripts\python.exe -m mypy backend/app scripts/validate_ses_preparation.py
.\.venv\Scripts\python.exe scripts/validate_workflows.py
.\.venv\Scripts\python.exe scripts/validate_ses_preparation.py
.\.venv\Scripts\python.exe scripts/validate_config.py
docker compose config --quiet
docker compose -f docker-compose.yml -f n8n/ses-test/compose.preparation.yml --profile ses-preparation config --quiet
node frontend/build.mjs
.\.venv\Scripts\python.exe scripts/audit_secrets.py
git diff --check
```

The bounded selection excludes full 10,000-user ingestion, supplied-file inspection and the opted-in SMTP test. Notification tests use mocks or isolated database state. Serverless checks validate static invariants; they do not resolve AWS parameters or prove deployment. The secret check compares Git-visible files to known local secret values and is not a universal credential detector.

Full demonstration commands in the [script index](../scripts/README.md) can create uploads and notifications, change workflow installation or overwrite reports. Run them only when that work is intended. Do not run `import_n8n.py` as a regression check: it rotates a local credential. Existing [historical reports](../reports/README.md) describe their own dated runs, not the latest source automatically.
