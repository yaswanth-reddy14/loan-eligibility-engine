import html
import smtplib
from email.message import EmailMessage
from typing import Any

import boto3
from botocore.config import Config
from sqlalchemy import String, cast, func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.matching import VERSION
from app.models import Audit, Job, Match, Notification, Product, User, now

DISCLAIMER = "Eligibility is preliminary, not approval, and subject to lender verification. Demo products are fictional."


def destination() -> str:
    # Deliberately accepts no User or email argument; sample data can never choose a recipient.
    return settings().notification_test_inbox


def render(first_name: str, products: list[dict[str, str]]) -> tuple[str, str]:
    plain = f"Hello {first_name},\nPotentially suitable products:\n"
    parts = []
    for product in products:
        plain += f"{product['lender']} - {product['product_name']}: {product['rate_representation']} {product['source_url']}\n"
        parts.append(
            f'<li><strong>{html.escape(product["lender"])}</strong> — {html.escape(product["product_name"])}<br>{html.escape(product["rate_representation"])}<br><a href="{html.escape(product["source_url"], quote=True)}">Product source</a></li>'
        )
    plain += DISCLAIMER
    return (
        plain,
        f"<h2>Hello {html.escape(first_name)},</h2><p>Products you may be eligible for:</p><ul>{''.join(parts)}</ul><p>{DISCLAIMER}</p>",
    )


def deliver(event_id: str, first_name: str, products: list[dict[str, str]]) -> str:
    cfg = settings()
    plain, markup = render(first_name, products)
    recipient = destination()
    if cfg.email_delivery_mode == "preview":
        message = EmailMessage()
        message["From"], message["To"] = "demo@loan.test", recipient
        message["Subject"] = "[DEMO] Preliminary loan eligibility"
        message["Message-ID"] = f"<{event_id}@loan.test>"
        message.set_content(plain)
        message.add_alternative(markup, subtype="html")
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
            smtp.send_message(message, to_addrs=[recipient])
        return message["Message-ID"]
    if not cfg.ses_sender:
        raise ValueError("SES sender is required for test delivery")
    client = boto3.client(
        "ses",
        region_name=cfg.aws_region,
        config=Config(
            # SendEmail has no idempotency token. An SDK retry after a lost
            # acknowledgement could duplicate a submission inside one DB attempt.
            retries={"total_max_attempts": 1, "mode": "standard"}, connect_timeout=5, read_timeout=15
        ),
    )
    response = client.send_email(
        Source=cfg.ses_sender,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": "[TEST] Preliminary loan eligibility"},
            "Body": {"Text": {"Data": plain}, "Html": {"Data": markup}},
        },
    )
    return str(response["MessageId"])


def seed_events(job_id: str) -> None:
    """Shared recipient gate and idempotent event creation for both delivery transports."""
    with Session(engine()) as db, db.begin():
        if db.scalar(select(User.id).where(func.lower(User.email) == destination().lower()).limit(1)):
            raise ValueError("Controlled inbox collides with a source CSV address; select a different inbox")
        audit = db.scalar(select(Audit).where(Audit.job_id == job_id, Audit.workflow == "B"))
        if not audit or audit.status != "COMPLETED":
            raise ValueError("Matching must complete first")
        eligible = select(Match.user_id).where(
            Match.job_id == job_id, Match.matching_version == VERSION, Match.status == "POSSIBLY_ELIGIBLE"
        )
        db.execute(
            insert(Notification)
            .from_select(
                ["id", "job_id", "user_id", "matching_version", "destination"],
                select(
                    cast(func.gen_random_uuid(), String),
                    literal(job_id),
                    User.id,
                    literal(VERSION),
                    literal(destination()),
                ).where(User.id.in_(eligible)),
            )
            .on_conflict_do_nothing()
        )


def notify(job_id: str, limit: int = 100, execution_id: str | None = None) -> dict[str, Any]:
    """Crash after submission is UNKNOWN: never blindly resend ambiguous deliveries."""
    if settings().n8n_ses_enabled:
        raise ValueError("n8n SES transport selected; use the reserved-event workflow")
    seed_events(job_id)
    sent = 0
    for _ in range(limit):
        with Session(engine()) as db, db.begin():
            event = db.scalar(
                select(Notification)
                .where(Notification.job_id == job_id, Notification.status == "PENDING")
                .order_by(Notification.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not event:
                break
            if event.destination != destination():
                raise ValueError("Controlled inbox changed; reconcile pending events before sending")
            event.status, event.updated_at = "SENDING", now()
            event.attempts += 1
            event_id, user_id = event.id, event.user_id
        with Session(engine()) as db:
            selected_user = db.get(User, user_id)
            assert selected_user is not None
            products = db.execute(
                select(Product, Match)
                .join(Match, Match.product_id == Product.id)
                .where(
                    Match.job_id == job_id,
                    Match.user_id == user_id,
                    Match.matching_version == VERSION,
                    Match.status == "POSSIBLY_ELIGIBLE",
                )
            ).all()
            details = []
            for product, match in products:
                snapshot = match.matched_criteria.get("product_snapshot", {})
                fields = ["lender", "product_name", "source_url", "rate_representation"]
                # Historical v1 rows lacked presentation snapshots. New matches retain the evaluated source.
                details.append({key: str(snapshot.get(key, getattr(product, key))) for key in fields})
            first_name = (
                "Synthetic" if settings().email_delivery_mode == "test" else selected_user.name.split()[0]
            )
        try:
            provider_id = deliver(event_id, first_name, details)
        except Exception:
            with Session(engine()) as db, db.begin():
                failed = db.get(Notification, event_id)
                assert failed is not None
                failed.status, failed.updated_at = "UNKNOWN", now()
            raise
        with Session(engine()) as db, db.begin():
            delivered = db.get(Notification, event_id)
            assert delivered is not None
            delivered.status, delivered.provider_id, delivered.updated_at = "SENT", provider_id, now()
        sent += 1
    return summarize(job_id, sent, execution_id)


def summarize(job_id: str, sent: int = 0, execution_id: str | None = None) -> dict[str, Any]:
    with Session(engine()) as db, db.begin():
        db.scalar(select(Job).where(Job.id == job_id).with_for_update())  # Serialize terminal audit counts.
        pending = (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.job_id == job_id, Notification.status == "PENDING")
            )
            or 0
        )
        uncertain = (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.job_id == job_id, Notification.status.in_(["UNKNOWN", "SENDING"]))
            )
            or 0
        )
        status = "RUNNING" if pending else "REVIEW_REQUIRED" if uncertain else "COMPLETED"
        sent_total = (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.job_id == job_id, Notification.status == "SENT")
            )
            or 0
        )
        metrics: dict[str, Any] = {
            "last_batch_sent": sent,
            "pending": pending,
            "uncertain": uncertain,
            "sent_total": sent_total,
        }
        if execution_id:
            metrics["n8n_execution_id"] = execution_id
        db.execute(
            insert(Audit)
            .values(
                job_id=job_id,
                workflow="C",
                status=status,
                metrics=metrics,
            )
            .on_conflict_do_update(
                index_elements=["job_id", "workflow"],
                set_={
                    "status": status,
                    "metrics": metrics,
                },
            )
        )
    return {"sent": sent, "pending": pending}
