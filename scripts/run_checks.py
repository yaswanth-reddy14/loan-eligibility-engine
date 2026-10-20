import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from dotenv import dotenv_values


def main() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = "backend;." if os.name == "nt" else "backend:."
    cfg = dotenv_values(".env")
    if cfg.get("DATABASE_URL"):
        env.setdefault("TEST_DATABASE_URL", cfg["DATABASE_URL"].rsplit("/", 1)[0] + "/loan_test")
    commands = {
        "ruff": [sys.executable, "-m", "ruff", "check", "backend", "scripts", "migrations"],
        "mypy": [sys.executable, "-m", "mypy", "backend/app"],
        "pytest": [sys.executable, "-m", "pytest", "-q", "--junitxml=reports/pytest.xml"],
        "workflow_structure": [sys.executable, "scripts/validate_workflows.py"],
        "aws_static_config": [sys.executable, "scripts/validate_config.py"],
        "compose": ["docker", "compose", "config", "--quiet"],
        "frontend": ["node", "frontend/build.mjs"],
        "migration_upgrade": [sys.executable, "-m", "alembic", "upgrade", "head"],
        "migration_drift": [sys.executable, "-m", "alembic", "check"],
    }
    results = {}
    Path("reports").mkdir(exist_ok=True)
    for name, command in commands.items():
        start = time.monotonic()
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        Path(f"reports/{name}.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
        results[name] = {"exit_code": result.returncode, "seconds": time.monotonic() - start}
        print(name, "PASS" if result.returncode == 0 else "FAIL", flush=True)
    if Path("reports/pytest.xml").exists():
        suite = ET.parse("reports/pytest.xml").getroot().find("testsuite")
        if suite is not None:
            results["test_counts"] = {
                key: int(suite.get(key, "0")) for key in ["tests", "failures", "errors", "skipped"]
            }
    Path("reports/checks.json").write_text(json.dumps(results, indent=2))
    failed = any(value.get("exit_code", 0) != 0 for value in results.values())
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
