import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import engine
from app.llm import qualitative_quotes
from app.models import CrawlRun, Criteria, Product, now


class Extraction(BaseModel):
    lender: str = Field(min_length=1, max_length=150)
    product_name: str = Field(min_length=1, max_length=200)
    interest_rate_min: float | None = Field(default=None, ge=0, le=100)
    interest_rate_max: float | None = Field(default=None, ge=0, le=100)
    minimum_monthly_income: float | None = Field(default=None, ge=0)
    minimum_credit_score: int | None = Field(default=None, ge=300, le=900)
    age_min: int | None = Field(default=None, ge=18, le=100)
    age_max: int | None = Field(default=None, ge=18, le=100)
    employment_requirements: list[str] | None = None
    source_url: HttpUrl
    evidence: dict[str, str]
    confidence: float = Field(ge=0, le=1)
    unknown_fields: list[str]
    qualitative_requirements: list[str] = Field(default_factory=list)
    llm_status: str = "DISABLED"

    @field_validator("employment_requirements")
    @classmethod
    def employment_values(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (
            not value
            or set(value) - {"SALARIED", "SELF_EMPLOYED", "BUSINESS", "STUDENT", "RETIRED", "UNEMPLOYED"}
        ):
            raise ValueError("Unsupported or empty employment requirements")
        return value

    @model_validator(mode="after")
    def supported(self) -> "Extraction":
        for key in [
            "interest_rate_min",
            "interest_rate_max",
            "minimum_monthly_income",
            "minimum_credit_score",
            "age_min",
            "age_max",
            "employment_requirements",
        ]:
            if getattr(self, key) is not None and not self.evidence.get(key):
                raise ValueError(f"Missing evidence for {key}")
        if self.age_min is not None and self.age_max is not None and self.age_min > self.age_max:
            raise ValueError("Invalid age bounds")
        if (
            self.interest_rate_min is not None
            and self.interest_rate_max is not None
            and self.interest_rate_min > self.interest_rate_max
        ):
            raise ValueError("Invalid rate bounds")
        return self


def extract(markup: str, source: dict[str, Any]) -> Extraction:
    """Conservative deterministic parser. Never infers requirements from marketing language."""
    soup = BeautifulSoup(markup, "html.parser")
    node = soup.select_one("script#eligibility-fixture")
    if source.get("fixture") and node:
        return Extraction.model_validate(json.loads(node.get_text()))
    text_value = soup.get_text(" ", strip=True)
    evidence: dict[str, str] = {}
    values: dict[str, Any] = {}
    # Only these explicit labelled statements are supported. Source-specific changes need review.
    patterns = {
        "minimum_monthly_income": r"Minimum monthly income\s*[:\-]?\s*(?:Rs\.?|INR|₹)?\s*([\d,]+)",
        "minimum_credit_score": r"Minimum credit score\s*[:\-]?\s*(\d{3})",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text_value, flags=re.I)
        if match:
            values[key] = int(match.group(1).replace(",", ""))
            evidence[key] = match.group(0)
    age = re.search(r"Age(?: requirement)?\s*:\s*(\d{2})\s*(?:to|[-–])\s*(\d{2})\s*years", text_value, re.I)
    if age:
        values.update(age_min=int(age[1]), age_max=int(age[2]))
        evidence.update(age_min=age[0], age_max=age[0])
    employment = re.search(
        r"Employment(?: requirements?)?\s*:\s*(salaried|self[- ]employed|business)\b", text_value, re.I
    )
    if employment:
        values["employment_requirements"] = [
            {
                "salaried": "SALARIED",
                "self-employed": "SELF_EMPLOYED",
                "self employed": "SELF_EMPLOYED",
                "business": "BUSINESS",
            }[employment[1].lower()]
        ]
        evidence["employment_requirements"] = employment[0]
    rate = re.search(
        r"Interest rate\s*:\s*(?:starting (?:from|at)\s*)?(\d+(?:\.\d+)?)\s*%\s*(?:p\.?a\.?|per annum)",
        text_value,
        re.I,
    )
    interval = re.search(
        r"Interest rate\s*:\s*(\d+(?:\.\d+)?)\s*%?\s*(?:to|[-–])\s*(\d+(?:\.\d+)?)\s*%\s*(?:p\.?a\.?|per annum)",
        text_value,
        re.I,
    )
    if interval:
        values.update(interest_rate_min=float(interval[1]), interest_rate_max=float(interval[2]))
        evidence.update(interest_rate_min=interval[0], interest_rate_max=interval[0])
    elif rate and re.search(r"starting (from|at)", rate[0], re.I):
        values["interest_rate_min"] = float(rate[1])
        evidence["interest_rate_min"] = rate[0]
    fields = [
        "interest_rate_min",
        "interest_rate_max",
        "minimum_monthly_income",
        "minimum_credit_score",
        "age_min",
        "age_max",
        "employment_requirements",
    ]
    quotes, llm_status = qualitative_quotes(text_value, approved=source.get("approved") is True)
    return Extraction(
        lender=source["lender"],
        product_name="Personal Loan",
        source_url=source["url"],
        evidence=evidence,
        confidence=0.5,
        unknown_fields=[key for key in fields if key not in values],
        qualitative_requirements=quotes,
        llm_status=llm_status,
        **values,
    )


def store_extraction(
    value: Extraction, fixture: bool = False, execution_id: str | None = None
) -> dict[str, Any]:
    if not str(value.source_url).startswith("https://"):
        raise ValueError("HTTPS product evidence is required")
    with Session(engine()) as db, db.begin():
        # Extraction alone cannot certify completeness or lender verification.
        record = {
            "lender": value.lender,
            "product_name": value.product_name,
            "source_url": str(value.source_url),
            "rate_min": value.interest_rate_min,
            "rate_max": value.interest_rate_max,
            "rate_type": "STARTING_FROM"
            if value.interest_rate_min is not None and value.interest_rate_max is None
            else "RANGE"
            if value.interest_rate_max is not None
            else "UNKNOWN",
            "rate_representation": f"Starting from {value.interest_rate_min}% p.a. (fictional)"
            if fixture
            else "See official source; rate unverified",
            "verification_status": "DEMO_FIXTURE" if fixture else "UNVERIFIED",
            "criteria_complete": fixture and not value.unknown_fields,
            "retrieved_at": now(),
            "evidence": value.model_dump(mode="json"),
        }
        statement = (
            insert(Product)
            .values(**record)
            .on_conflict_do_update(index_elements=["source_url"], set_=record)
            .returning(Product.id)
        )
        product_id = db.scalar(statement)
        criteria = {
            key: getattr(value, key)
            for key in [
                "minimum_monthly_income",
                "minimum_credit_score",
                "age_min",
                "age_max",
                "employment_requirements",
            ]
        }
        criteria["qualitative_requirements"] = (
            [] if fixture else ["Lender verification and unspecified conditions", *value.qualitative_requirements]
        )
        criteria["evidence"] = {
            key: {"text": text_value, "source_url": str(value.source_url), "retrieved_at": now().isoformat()}
            for key, text_value in value.evidence.items()
        }
        if value.qualitative_requirements:
            criteria["evidence"]["qualitative_requirements"] = {
                "text": "\n".join(value.qualitative_requirements), "source_url": str(value.source_url),
                "retrieved_at": now().isoformat(), "extraction": "LLM verbatim quotes; not lender verification",
            }
        db.execute(
            insert(Criteria)
            .values(product_id=product_id, **criteria)
            .on_conflict_do_update(index_elements=["product_id"], set_=criteria)
        )
        db.add(
            CrawlRun(
                source_url=str(value.source_url),
                status="FIXTURE" if fixture else "REVIEW_REQUIRED",
                detail="Schema validated; source evidence retained"
                + (f"; n8n execution {execution_id}" if execution_id else ""),
            )
        )
        return {"product_id": product_id, "status": record["verification_status"]}


def seed_fixtures() -> list[dict[str, Any]]:
    result = []
    for path in sorted(Path("n8n/fixtures").glob("*.html")):
        value = extract(path.read_text(encoding="utf-8"), {"fixture": True})
        result.append(store_extraction(value, fixture=True))
    return result


FIXTURE_IDS = ("incomplete", "independent", "salaried")


def fixture_html(fixture_id: str) -> str:
    if fixture_id not in FIXTURE_IDS:
        raise ValueError("Unknown fixture ID")
    return Path(f"n8n/fixtures/{fixture_id}.html").read_text(encoding="utf-8")
