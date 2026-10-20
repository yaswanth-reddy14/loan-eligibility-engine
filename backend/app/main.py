import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import session
from app.discovery import extract, fixture_html, seed_fixtures, store_extraction
from app.matching import complete_matching, run_matching
from app.models import Audit, CrawlRun, Job, Match, Notification, Outbox, Product, uid
from app.notifications import notify
from app.storage import s3

app = FastAPI(title="Loan Eligibility Engine", version="1.0.0")
Db = Annotated[Session, Depends(session)]
limits: dict[str, deque[float]] = defaultdict(deque)


def authenticated(request: Request, authorization: Annotated[str | None, Header()] = None) -> None:
    if not authorization or not secrets.compare_digest(authorization, "Bearer " + settings().api_token):
        raise HTTPException(401, "Valid API bearer token required")
    key = request.client.host if request.client else "unknown"
    times = limits[key]
    current = time.monotonic()
    while times and times[0] < current - 60:
        times.popleft()
    if len(times) >= 120:
        raise HTTPException(429, "Rate limit exceeded; retry after 60 seconds")
    times.append(current)


def internal(x_workflow_secret: Annotated[str | None, Header()] = None) -> None:
    if not x_workflow_secret or not secrets.compare_digest(x_workflow_secret, settings().workflow_secret):
        raise HTTPException(401, "Invalid workflow secret")


@app.exception_handler(ValueError)
async def invalid(request: Request, exc: ValueError) -> Any:
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Any:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    cfg = settings()
    endpoint = cfg.s3_public_endpoint or cfg.s3_endpoint
    if endpoint:
        parsed = urlsplit(endpoint)
        upload_origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme in {"http", "https"} else ""
    else:
        # The shared S3 adapter uses path-style addressing; retain bucket-style origins too.
        upload_origin = (
            f"https://s3.{cfg.aws_region}.amazonaws.com https://s3.amazonaws.com "
            f"https://{cfg.s3_bucket}.s3.{cfg.aws_region}.amazonaws.com https://{cfg.s3_bucket}.s3.amazonaws.com"
        )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        f"connect-src 'self' {upload_origin}; frame-ancestors 'none'"
    )
    return response


@app.get("/health")
def health(db: Db) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


class UploadInit(BaseModel):
    filename: str = Field(min_length=1, max_length=200, pattern=r"(?i)^[^/\\]+\.csv$")
    size: int = Field(gt=0, le=20 * 1024 * 1024)
    checksum: str = Field(pattern="^[0-9a-f]{64}$")


@app.post("/api/uploads", dependencies=[Depends(authenticated)])
def upload_init(value: UploadInit, db: Db) -> dict[str, Any]:
    if value.size > settings().max_upload_bytes:
        raise HTTPException(413, "Upload too large")
    job_id = uid()
    key = f"uploads/{job_id}/users.csv"
    db.add(Job(id=job_id, file_key=key, checksum=value.checksum, size=value.size))
    db.commit()
    url = s3(public=True).generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings().s3_bucket,
            "Key": key,
            "ContentType": "text/csv",
            "ContentLength": value.size,
            "IfNoneMatch": "*",
        },
        ExpiresIn=300,
    )
    return {
        "job_id": job_id,
        "url": url,
        "headers": {"Content-Type": "text/csv", "If-None-Match": "*"},
        "expires_in": 300,
    }


@app.post("/api/uploads/{job_id}/complete", dependencies=[Depends(authenticated)])
def complete(job_id: str, db: Db) -> dict[str, str]:
    job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if not job:
        raise HTTPException(404, "Unknown job")
    if job.status != "UPLOADING":
        return {"job_id": job.id, "status": job.status}
    head = s3().head_object(Bucket=settings().s3_bucket, Key=job.file_key)
    if head["ContentLength"] != job.size:
        raise HTTPException(400, "Object size mismatch")
    job.object_version = head.get("VersionId")
    job.status = "READY"
    db.commit()
    return {"job_id": job.id, "status": job.status}


@app.get("/api/jobs/{job_id}", dependencies=[Depends(authenticated)])
def job_status(job_id: str, db: Db) -> dict[str, Any]:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    return {
        key: getattr(job, key)
        for key in ["id", "status", "accepted", "rejected", "error_summary", "created_at", "completed_at"]
    }


@app.get("/api/dashboard", dependencies=[Depends(authenticated)])
def dashboard(db: Db, job_id: str | None = None) -> dict[str, Any]:
    recent_jobs = db.scalars(select(Job).order_by(Job.created_at.desc()).limit(20)).all()
    jobs = [job for job in recent_jobs if job_id is None or job.id == job_id]
    match_counts = select(Match.status, func.count()).group_by(Match.status)
    notification_counts = select(Notification.status, func.count()).group_by(Notification.status)
    outbox_counts = select(Outbox.status, func.count()).group_by(Outbox.status)
    audits_query = select(Audit).order_by(Audit.created_at.desc()).limit(20)
    if job_id:
        match_counts = match_counts.where(Match.job_id == job_id)
        notification_counts = notification_counts.where(Notification.job_id == job_id)
        outbox_counts = outbox_counts.where(Outbox.job_id == job_id)
        audits_query = audits_query.where(Audit.job_id == job_id)
    products = db.scalars(select(Product).order_by(Product.id)).all()
    audits = db.scalars(audits_query).all()
    return {
        "demo_mode": settings().demo_mode,
        "email_delivery_mode": settings().email_delivery_mode,
        "selected_job_id": job_id,
        "available_jobs": [{"id": job.id, "status": job.status} for job in recent_jobs],
        "jobs": [
            {key: getattr(job, key) for key in ["id", "status", "accepted", "rejected", "error_summary"]}
            for job in jobs
        ],
        "products": [
            {
                key: getattr(product, key)
                for key in [
                    "id",
                    "lender",
                    "product_name",
                    "verification_status",
                    "rate_representation",
                    "source_url",
                    "criteria_complete",
                ]
            }
            for product in products
        ],
        "matches": {row[0]: row[1] for row in db.execute(match_counts)},
        "notifications": {row[0]: row[1] for row in db.execute(notification_counts)},
        "outbox": {row[0]: row[1] for row in db.execute(outbox_counts)},
        "discovery_runs": [
            {"id": run.id, "status": run.status, "source_url": run.source_url, "detail": run.detail}
            for run in db.scalars(select(CrawlRun).order_by(CrawlRun.created_at.desc()).limit(6))
        ],
        "workflows": [
            {
                "id": audit.id,
                "job_id": audit.job_id,
                "workflow": audit.workflow,
                "status": audit.status,
                "metrics": audit.metrics,
                "created_at": audit.created_at,
            }
            for audit in audits
        ],
    }


@app.get("/internal/jobs/{job_id}", dependencies=[Depends(internal)])
def internal_job(job_id: str, db: Db) -> dict[str, Any]:
    return job_status(job_id, db)


@app.get("/api/products", dependencies=[Depends(authenticated)])
def products_api(db: Db) -> dict[str, Any]:
    return {"products": dashboard(db)["products"]}


@app.get("/api/matches/summary", dependencies=[Depends(authenticated)])
def matches_api(db: Db) -> dict[str, Any]:
    return {"matches": dashboard(db)["matches"]}


@app.get("/api/metrics", dependencies=[Depends(authenticated)])
def metrics_api(db: Db) -> dict[str, Any]:
    return {"workflows": dashboard(db)["workflows"]}


class Evaluation(BaseModel):
    user_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    status: str = Field(pattern="^(POSSIBLY_ELIGIBLE|REVIEW_REQUIRED)$")


class WorkflowExecution(BaseModel):
    execution_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=30)


class Evaluations(WorkflowExecution):
    evaluations: list[Evaluation] = Field(max_length=50000)


@app.post("/internal/matching/{job_id}", dependencies=[Depends(internal)])
def matching(job_id: str, value: Evaluations) -> dict[str, Any]:
    return {
        "job_id": job_id,
        **run_matching(job_id, [item.model_dump() for item in value.evaluations], value.execution_id),
    }


@app.post("/internal/matching/{job_id}/complete", dependencies=[Depends(internal)])
def matching_complete(job_id: str, value: WorkflowExecution) -> dict[str, Any]:
    return complete_matching(job_id, value.execution_id)


@app.post("/internal/notifications/{job_id}", dependencies=[Depends(internal)])
def notifications(job_id: str, value: WorkflowExecution) -> dict[str, Any]:
    # One request processes at most 100 recipients. Dispatcher repeats until pending=0.
    return {"job_id": job_id, **notify(job_id, execution_id=value.execution_id)}


@app.post("/internal/discovery/fixtures", dependencies=[Depends(internal)])
def fixtures() -> dict[str, Any]:
    if not settings().demo_mode:
        raise HTTPException(403, "Fixtures disabled")
    return {"products": seed_fixtures()}


class DiscoveryInput(BaseModel):
    html: str = Field(max_length=2_000_000)
    source_id: str | None = None
    fixture_id: str | None = None
    execution_id: str | None = Field(default=None, pattern=r"^[1-9][0-9]*$", max_length=30)


@app.post("/internal/discovery/extract", dependencies=[Depends(internal)])
def discovery(value: DiscoveryInput) -> dict[str, Any]:
    import json

    if value.fixture_id is not None:
        if not settings().demo_mode or value.source_id is not None:
            raise HTTPException(403, "Fixture extraction is only enabled in demo mode")
        if value.html != fixture_html(value.fixture_id):
            raise ValueError("Fixture HTML does not match the bundled evidence")
        return store_extraction(
            extract(value.html, {"fixture": True}), fixture=True, execution_id=value.execution_id
        )

    sources = json.loads(Path("n8n/sources.json").read_text())
    source = next((item for item in sources if item["id"] == value.source_id and item["approved"]), None)
    if not source:
        raise HTTPException(403, "Source has not passed permission review")
    return store_extraction(extract(value.html, source), execution_id=value.execution_id)


@app.get("/internal/discovery/fixture-html/{fixture_id}", dependencies=[Depends(internal)])
def get_fixture_html(fixture_id: str) -> Response:
    if not settings().demo_mode:
        raise HTTPException(403, "Fixtures disabled")
    return Response(fixture_html(fixture_id), media_type="text/html")


@app.post("/api/discovery/demo", dependencies=[Depends(authenticated)], status_code=202)
def start_demo_discovery() -> dict[str, str]:
    import httpx

    if not settings().demo_mode:
        raise HTTPException(403, "Demo discovery disabled")
    try:
        response = httpx.post(
            settings().n8n_url + "/webhook/loan-a-demo",
            headers={"X-Workflow-Secret": settings().workflow_secret},
            json={},
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503, "n8n discovery unavailable; check Workflow A import/publication") from exc
    return {"status": "ACCEPTED", "workflow": "A", "source_kind": "FICTIONAL_FIXTURE"}


class CrawlAuditInput(BaseModel):
    url: str = Field(max_length=1000)
    detail: str = Field(max_length=1000)
    status: str = Field(default="BLOCKED", pattern="^(BLOCKED|FAILED)$")


@app.post("/internal/discovery/audit", dependencies=[Depends(internal)])
def crawl_audit(value: CrawlAuditInput, db: Db) -> dict[str, str]:
    db.add(
        CrawlRun(
            source_url=value.url,
            status=value.status,
            detail=value.detail,
        )
    )
    db.commit()
    return {"status": "recorded"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(settings().frontend_dir) / "index.html")


if Path(settings().frontend_dir).exists():
    app.mount("/assets", StaticFiles(directory=settings().frontend_dir), name="assets")

# ASGI adapter for API Gateway; upload bytes go directly to S3.
from mangum import Mangum  # noqa: E402

handler = Mangum(app, lifespan="off")
