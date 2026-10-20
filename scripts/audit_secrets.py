"""Checks known local secret values without printing them; not a general secret scanner."""

import json
import subprocess
from pathlib import Path

from dotenv import dotenv_values


def main() -> None:
    config = dotenv_values(".env")
    secret_keys = [
        "API_TOKEN",
        "WORKFLOW_SECRET",
        "POSTGRES_PASSWORD",
        "MINIO_ROOT_PASSWORD",
        "N8N_ENCRYPTION_KEY",
    ]
    values = [config[key].encode() for key in secret_keys if config.get(key)]
    output = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    files = sorted(set(path.decode() for path in output.split(b"\0") if path))
    findings = []
    for filename in files:
        path = Path(filename)
        if path.is_file() and any(value in path.read_bytes() for value in values):
            findings.append(filename)
    ignored = subprocess.run(
        ["git", "check-ignore", ".env", "users.csv"], capture_output=True, text=True, check=True
    )
    assert set(ignored.stdout.splitlines()) == {".env", "users.csv"}
    result = {
        "files_scanned": len(files),
        "files_with_known_secret_values": findings,
        "env_and_supplied_csv_ignored": True,
        "scope": "Known generated local secrets only; no general dependency/security audit implied",
    }
    Path("reports/secrets-audit.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
