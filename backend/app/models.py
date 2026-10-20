import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    file_key: Mapped[str] = mapped_column(String(256), unique=True)
    checksum: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    object_version: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(24), default="UPLOADING", index=True)
    accepted: Mapped[int] = mapped_column(default=0)
    rejected: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("size > 0"),)


class User(Base):
    """Immutable per-job snapshots: repeated uploads retain historical match inputs."""

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("ingestion_jobs.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(14, 2), index=True)
    credit_score: Mapped[int] = mapped_column(Integer, index=True)
    employment_status: Mapped[str] = mapped_column(String(30), index=True)
    age: Mapped[int] = mapped_column(Integer, index=True)
    source_row: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("job_id", "external_id"),
        CheckConstraint("monthly_income >= 0"),
        CheckConstraint("credit_score BETWEEN 300 AND 900"),
        CheckConstraint("age BETWEEN 18 AND 100"),
    )


class IngestionError(Base):
    __tablename__ = "ingestion_errors"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("ingestion_jobs.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))


class Product(Base):
    __tablename__ = "loan_products"
    id: Mapped[int] = mapped_column(primary_key=True)
    lender: Mapped[str] = mapped_column(String(150))
    product_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(1000), unique=True)
    rate_min: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    rate_max: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    rate_type: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    rate_representation: Mapped[str] = mapped_column(String(200), default="Not published")
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED")
    criteria_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (
        CheckConstraint("rate_min IS NULL OR rate_min >= 0"),
        CheckConstraint("rate_max IS NULL OR rate_max >= rate_min"),
    )


class Criteria(Base):
    __tablename__ = "product_criteria"
    product_id: Mapped[int] = mapped_column(ForeignKey("loan_products.id"), primary_key=True)
    minimum_monthly_income: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    minimum_credit_score: Mapped[int | None] = mapped_column(Integer)
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    employment_requirements: Mapped[list[str] | None] = mapped_column(JSON)
    qualitative_requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (
        CheckConstraint("minimum_monthly_income IS NULL OR minimum_monthly_income >= 0"),
        CheckConstraint("age_max IS NULL OR age_max >= age_min"),
    )


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("ingestion_jobs.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("loan_products.id"))
    matching_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30))
    matched_criteria: Mapped[dict[str, Any]] = mapped_column(JSON)
    uncertainty: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("job_id", "user_id", "product_id", "matching_version"),)


class Notification(Base):
    __tablename__ = "notification_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("ingestion_jobs.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    matching_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    destination: Mapped[str] = mapped_column(String(254))
    attempts: Mapped[int] = mapped_column(default=0)
    provider_id: Mapped[str | None] = mapped_column(String(256))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("job_id", "user_id", "matching_version"),)


class Outbox(Base):
    __tablename__ = "workflow_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("ingestion_jobs.id"))
    workflow: Mapped[str] = mapped_column(String(1))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    attempts: Mapped[int] = mapped_column(default=0)
    progress_count: Mapped[int] = mapped_column(default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_error: Mapped[str | None] = mapped_column(String(200))
    __table_args__ = (
        UniqueConstraint("job_id", "workflow"),
        Index("outbox_due", "status", "next_attempt_at"),
    )


class CrawlRun(Base):
    __tablename__ = "crawler_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_url: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Audit(Base):
    __tablename__ = "workflow_run_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("ingestion_jobs.id"), index=True)
    workflow: Mapped[str] = mapped_column(String(1))
    status: Mapped[str] = mapped_column(String(30))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("job_id", "workflow"),)
