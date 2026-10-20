"""Local credential/workflow import without persisting plaintext secrets in the repo."""

import json
import secrets
import subprocess

from app.config import settings
from app.db import engine
from psycopg import sql


def command(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], check=True, text=True, **kwargs)


def main() -> None:
    password = secrets.token_hex(24)
    with engine().begin() as connection:
        raw = connection.connection.driver_connection
        with raw.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='loan_n8n_reader'")
            if not cursor.fetchone():
                cursor.execute("CREATE ROLE loan_n8n_reader LOGIN")
            cursor.execute(sql.SQL("ALTER ROLE loan_n8n_reader PASSWORD {}").format(sql.Literal(password)))
            cursor.execute("ALTER ROLE loan_n8n_reader CONNECTION LIMIT 4")
            cursor.execute("GRANT CONNECT ON DATABASE loan TO loan_n8n_reader")
            cursor.execute("GRANT USAGE ON SCHEMA public TO loan_n8n_reader")
            cursor.execute("REVOKE SELECT ON users FROM loan_n8n_reader")
            cursor.execute(
                "GRANT SELECT (id, job_id, monthly_income, credit_score, employment_status, age) ON users TO loan_n8n_reader"
            )
            cursor.execute("GRANT SELECT ON loan_products, product_criteria TO loan_n8n_reader")
    credentials = [
        {
            "id": "loan-internal-header",
            "name": "Loan internal header",
            "type": "httpHeaderAuth",
            "data": {"name": "X-Workflow-Secret", "value": settings().workflow_secret},
        }
    ]
    credentials.append(
        {
            "id": "loan-domain-postgres",
            "name": "Loan domain PostgreSQL",
            "type": "postgres",
            "data": {
                "host": "postgres",
                "port": 5432,
                "database": "loan",
                "user": "loan_n8n_reader",
                "password": password,
                "ssl": "disable",
                "maxConnections": 2,
            },
        }
    )
    command(
        [
            "exec",
            "-T",
            "n8n",
            "sh",
            "-c",
            "umask 077; cat > /tmp/loan-creds.json; n8n import:credentials --input=/tmp/loan-creds.json; result=$?; rm -f /tmp/loan-creds.json; exit $result",
        ],
        input=json.dumps(credentials),
    )
    command(["exec", "-T", "n8n", "n8n", "import:workflow", "--separate", "--input=/workflows/workflows"])
    command(["exec", "-T", "n8n", "n8n", "publish:workflow", "--id=loan-workflow-a"])
    command(["exec", "-T", "n8n", "n8n", "publish:workflow", "--id=loan-workflow-b"])
    command(["exec", "-T", "n8n", "n8n", "publish:workflow", "--id=loan-workflow-c"])
    command(["restart", "n8n"])
    print(
        "A/B/C published. A supports authenticated fictional discovery; unapproved live sources remain gated."
    )


if __name__ == "__main__":
    main()
