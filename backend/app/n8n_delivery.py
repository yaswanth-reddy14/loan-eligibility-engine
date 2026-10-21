"""Gated SES-node transport using the same durable notification events as SMTP."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.matching import VERSION
from app.models import Job, Match, Notification, Product, now
from app.notifications import destination, render, seed_events, summarize


def require_ses_gate() -> None:
    cfg = settings()
    if not cfg.n8n_ses_enabled or cfg.email_delivery_mode != "test" or not cfg.ses_sender:
        raise ValueError("n8n SES requires explicit enablement, test mode and a verified sender")


def claim(job_id: str, execution_id: str) -> dict[str, Any]:
    require_ses_gate()
    seed_events(job_id)  # Includes completed-B and source-email collision checks.
    marker = "n8n:" + execution_id
    with Session(engine()) as db, db.begin():
        db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        # A lost claim response must never hand the same in-flight event out again.
        existing = db.scalar(
            select(Notification.id)
            .where(
                Notification.job_id == job_id,
                Notification.provider_id == marker,
            )
            .limit(1)
        )
        if existing:
            return {"job_id": job_id, "ready": False}
        event = db.scalar(
            select(Notification)
            .where(
                Notification.job_id == job_id,
                Notification.status == "PENDING",
                Notification.matching_version == VERSION,
            )
            .order_by(Notification.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not event:
            return {"job_id": job_id, "ready": False}
        if event.destination != destination():
            raise ValueError("Controlled inbox changed; reconcile pending events before sending")
        rows = db.execute(
            select(Product, Match)
            .join(Match, Match.product_id == Product.id)
            .where(
                Match.job_id == job_id,
                Match.user_id == event.user_id,
                Match.matching_version == VERSION,
                Match.status == "POSSIBLY_ELIGIBLE",
            )
        ).all()
        if not rows:
            raise ValueError("No eligible products for notification")
        details = []
        for product, match in rows:
            snapshot = match.matched_criteria.get("product_snapshot", {})
            details.append(
                {
                    key: str(snapshot.get(key, getattr(product, key)))
                    for key in ["lender", "product_name", "source_url", "rate_representation"]
                }
            )
        plain, markup = render("Synthetic", details)
        event.status, event.provider_id, event.updated_at = "SENDING", marker, now()
        event.attempts += 1
        return {
            "job_id": job_id,
            "ready": True,
            "event_id": event.id,
            "from": settings().ses_sender,
            "to": destination(),
            "subject": "[TEST] Preliminary loan eligibility",
            "text": plain,
            "html": markup,
        }


def finish(
    job_id: str, event_id: str, execution_id: str, status: str, provider_id: str | None = None
) -> dict[str, Any]:
    require_ses_gate()
    if status not in {"SENT", "UNKNOWN"} or (status == "SENT" and not provider_id):
        raise ValueError("A successful SES acknowledgement requires its MessageId")
    sent = 0
    with Session(engine()) as db, db.begin():
        event = db.scalar(
            select(Notification)
            .where(
                Notification.id == event_id,
                Notification.job_id == job_id,
            )
            .with_for_update()
        )
        if not event:
            raise ValueError("Unknown notification")
        if event.status == "SENDING" and event.provider_id == "n8n:" + execution_id:
            event.status, event.updated_at = status, now()
            event.provider_id = provider_id if status == "SENT" else event.provider_id
            sent = int(status == "SENT")
        elif not (
            event.status == "SENT"
            and status == "SENT"
            and event.provider_id == provider_id
            or event.status == "UNKNOWN"
            and status == "UNKNOWN"
            and event.provider_id == "n8n:" + execution_id
        ):
            raise ValueError("Receipt does not own this pending attempt or event is terminal")
    return {"job_id": job_id, **summarize(job_id, sent, execution_id)}
