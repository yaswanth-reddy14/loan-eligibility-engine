import io
import json
from pathlib import Path

import pytest
from app.discovery import Extraction, extract
from app.matching import advanced
from app.notifications import destination, render
from app.validation import HEADERS, UserRow, rows, safe_csv_cell
from pydantic import ValidationError

from scripts.validate_workflows import validate


def valid_row(**changes):
    return {
        "user_id": "synthetic-1",
        "name": "Synthetic Person",
        "email": "synthetic@example.com",
        "monthly_income": "30000",
        "credit_score": "700",
        "employment_status": "Salaried",
        "age": "21",
        **changes,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("age", "17"),
        ("age", "101"),
        ("age", "21.5"),
        ("monthly_income", "-1"),
        ("monthly_income", "NaN"),
        ("monthly_income", "Infinity"),
        ("credit_score", "299"),
        ("credit_score", "901"),
        ("credit_score", "abc"),
        ("email", "invalid"),
        ("employment_status", "mystery"),
        ("name", ""),
    ],
)
def test_invalid_rows(field, value):
    with pytest.raises(ValidationError):
        UserRow.model_validate(valid_row(**{field: value}))


def test_headers():
    with pytest.raises(ValueError, match="headers"):
        list(rows(io.StringIO("user_id,name\n1,test\n")))


def test_malformed_rows():
    value = ",".join(HEADERS) + "\n1,name\n"
    assert list(rows(io.StringIO(value)))[0][2] == "Malformed column count"


@pytest.mark.parametrize(
    "employment,expected",
    [("Self-Employed", "SELF_EMPLOYED"), ("salaried", "SALARIED"), ("Unemployed", "UNEMPLOYED")],
)
def test_employment_normalization(employment, expected):
    assert UserRow.model_validate(valid_row(employment_status=employment)).employment_status == expected


@pytest.mark.parametrize("value", ["=1+1", "+formula", "-formula", "@formula", "  =formula"])
def test_export_injection(value):
    assert safe_csv_cell(value).startswith("'")


def test_complete_and_unknown():
    candidate = dict(
        minimum_monthly_income=30000,
        minimum_credit_score=700,
        age_min=21,
        age_max=60,
        employment_requirements=["SALARIED"],
        qualitative_requirements=[],
        criteria_complete=True,
    )
    assert advanced(candidate) == ("POSSIBLY_ELIGIBLE", [])
    for field in [
        "minimum_monthly_income",
        "minimum_credit_score",
        "age_min",
        "age_max",
        "employment_requirements",
    ]:
        assert advanced({**candidate, field: None})[0] == "REVIEW_REQUIRED"
    assert (
        advanced({**candidate, "qualitative_requirements": ["employment tenure unknown"]})[0]
        == "REVIEW_REQUIRED"
    )


def test_email_safety(monkeypatch):
    monkeypatch.setenv("NOTIFICATION_TEST_INBOX", "controlled+demo@example.com")
    from app.config import settings

    settings.cache_clear()
    assert destination() == "controlled+demo@example.com"
    plain, markup = render(
        "<script>",
        [
            {
                "lender": "Synthetic",
                "product_name": "Demo",
                "rate_representation": "12%",
                "source_url": "https://example.org",
            }
        ],
    )
    assert "<script>" not in markup
    assert "not approval" in plain
    settings.cache_clear()


def test_workflow_exports():
    paths = list(Path("n8n/workflows").glob("*.json"))
    assert len(paths) == 3
    for path in paths:
        validate(path)


def test_fixture_extraction():
    for path in Path("n8n/fixtures").glob("*.html"):
        value = extract(path.read_text(), {"fixture": True})
        assert value.lender.startswith("Fictional")
        assert value.interest_rate_max is None


def test_unsupported_extraction():
    value = extract(
        "<p>A good credit score may help.</p>", {"lender": "Official", "url": "https://example.org/product"}
    )
    assert value.minimum_credit_score is None
    data = value.model_dump()
    data["minimum_credit_score"] = 750
    with pytest.raises(ValidationError, match="evidence"):
        Extraction.model_validate(data)


def test_unsafe_delivery_mode(monkeypatch):
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(email_delivery_mode="production")


def test_supplied_csv_inspection(input_csv):
    with input_csv.open(encoding="utf-8-sig", newline="") as stream:
        results = list(rows(stream))
    assert len(results) == 10000
    assert all(row is not None and error is None for _, row, error in results)


def test_sources_fail_closed():
    sources = json.loads(Path("n8n/sources.json").read_text())
    assert 2 <= len(sources) <= 3
    assert all(not value["approved"] for value in sources)


def test_n8n_code_matches_shared_rules():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute the n8n Code rule equivalence check")
    base = dict(
        user_id=1,
        product_id=1,
        minimum_monthly_income=30000,
        minimum_credit_score=700,
        age_min=21,
        age_max=60,
        employment_requirements=["SALARIED"],
        qualitative_requirements=[],
        criteria_complete=True,
    )
    candidates = [
        base,
        {**base, "product_id": 2, "employment_requirements": None},
        {**base, "product_id": 3, "qualitative_requirements": ["Unknown tenure"]},
    ]
    code = (
        "const $json="
        + json.dumps({"job_id": "synthetic", "candidates": candidates})
        + "; const run=()=>{"
        + Path("n8n/advanced_rules.js").read_text()
        + "};process.stdout.write(JSON.stringify(run()[0].json.evaluations));"
    )
    result = subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True)
    assert [item["status"] for item in json.loads(result.stdout)] == [
        advanced(item)[0] for item in candidates
    ]


def test_explicit_labels_extract_age_employment_and_rate():
    value = extract(
        "<p>Minimum monthly income: INR 30,000. Minimum credit score: 700. Age: 21 to 60 years. Employment: salaried. Interest rate: starting from 12.5% p.a.</p>",
        {"lender": "Synthetic parser test", "url": "https://example.org/parser"},
    )
    assert (value.age_min, value.age_max) == (21, 60)
    assert value.employment_requirements == ["SALARIED"]
    assert value.interest_rate_min == 12.5 and value.interest_rate_max is None
    assert "interest_rate_max" in value.unknown_fields
    assert value.evidence["age_min"] == "Age: 21 to 60 years"


def test_explicit_rate_interval_and_unlabelled_marketing():
    value = extract(
        "<p>Interest rate: 12.5% to 18% p.a.</p>",
        {"lender": "Synthetic", "url": "https://example.org/parser"},
    )
    assert (value.interest_rate_min, value.interest_rate_max) == (12.5, 18)
    value = extract(
        "<p>Apply from 18 years! Salaried customers welcome. Enjoy 9%!</p>",
        {"lender": "Synthetic", "url": "https://example.org/parser"},
    )
    assert value.age_min is None and value.employment_requirements is None and value.interest_rate_min is None
