"""Produces aggregate evidence only, never names or addresses."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from app.validation import HEADERS, rows


def main() -> None:
    path = Path("users.csv")
    if not path.exists():
        raise SystemExit("Copy the supplied users.csv to the project root; never invent it.")
    accepted = rejected = count = 0
    seen = set()
    duplicate_ids = 0
    employments = Counter()
    bounds = {key: [float("inf"), float("-inf")] for key in ["monthly_income", "credit_score", "age"]}
    reasons = Counter()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for _, row, error in rows(stream):
            count += 1
            if error:
                rejected += 1
                reasons[error] += 1
                continue
            assert row is not None
            accepted += 1
            duplicate_ids += row.user_id in seen
            seen.add(row.user_id)
            employments[row.employment_status] += 1
            for key in bounds:
                value = float(getattr(row, key))
                bounds[key] = [min(bounds[key][0], value), max(bounds[key][1], value)]
    with path.open(encoding="utf-8-sig", newline="") as stream:
        raw = list(csv.DictReader(stream))
    result = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
        "headers": HEADERS,
        "rows": count,
        "valid": accepted,
        "invalid": rejected,
        "duplicate_external_ids": duplicate_ids,
        "duplicate_emails": len(raw) - len({row["email"] for row in raw}),
        "missing_by_field": {key: sum(not (row.get(key) or "").strip() for row in raw) for key in HEADERS},
        "normalized_employment": dict(employments),
        "ranges": bounds,
        "invalid_reasons": dict(reasons),
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/csv-inspection.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
