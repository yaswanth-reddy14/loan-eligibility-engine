import csv
from collections.abc import Iterator
from decimal import Decimal
from typing import TextIO

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

HEADERS = ["user_id", "name", "email", "monthly_income", "credit_score", "employment_status", "age"]
EMPLOYMENT = {
    "business": "BUSINESS",
    "salaried": "SALARIED",
    "employed": "SALARIED",
    "self-employed": "SELF_EMPLOYED",
    "self employed": "SELF_EMPLOYED",
    "self_employed": "SELF_EMPLOYED",
    "unemployed": "UNEMPLOYED",
    "student": "STUDENT",
    "retired": "RETIRED",
}


class UserRow(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    user_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(max_length=254)
    monthly_income: Decimal = Field(ge=0, le=999999999999, max_digits=14, decimal_places=2)
    credit_score: int = Field(ge=300, le=900)
    employment_status: str
    age: int = Field(ge=18, le=100)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value: str) -> str:
        try:
            return validate_email(value, check_deliverability=False, test_environment=True).normalized
        except EmailNotValidError as exc:
            raise ValueError("Invalid email syntax") from exc

    @field_validator("employment_status")
    @classmethod
    def employment(cls, value: str) -> str:
        result = EMPLOYMENT.get(value.lower())
        if result is None:
            raise ValueError("Unsupported employment category")
        return result


def rows(stream: TextIO) -> Iterator[tuple[int, UserRow | None, str | None]]:
    reader = csv.DictReader(stream, strict=True)
    if reader.fieldnames != HEADERS:
        raise ValueError("CSV headers must exactly match: " + ",".join(HEADERS))
    for number, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()):
            yield number, None, "Malformed column count"
            continue
        try:
            yield number, UserRow.model_validate(row), None
        except ValidationError as exc:
            # Never retain input values or PII in error logs.
            fields = sorted({str(error["loc"][0]) for error in exc.errors()})
            yield number, None, "Invalid fields: " + ",".join(fields)


def safe_csv_cell(value: str) -> str:
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value
