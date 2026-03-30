# =============================================================================
# Shared — Webhook Deduplication Helper
# =============================================================================
"""
WebhookDedup provides idempotent processing for all inbound webhook calls.

Usage pattern:
    event = await WebhookDedup.ensure_unique(
        db, gateway="n8n", event_id=event_id,
        event_type="order.delivered", payload=raw_body,
    )
    if event is None:
        return {"received": True, "duplicate": True}

    try:
        await process_event(...)
        await WebhookDedup.mark_processed(db, event)
    except Exception as exc:
        await WebhookDedup.mark_failed(db, event, str(exc))
        raise
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payment.models import WebhookEvent

logger = logging.getLogger(__name__)


class WebhookDedup:
    """Deduplication helper for inbound webhooks via the webhook_events table."""

    GATEWAY_N8N = "n8n"

    @staticmethod
    async def ensure_unique(
        db: AsyncSession,
        *,
        gateway: str,
        event_id: str,
        event_type: str | None = None,
        payload: str = "{}",
        transaction_id: str | None = None,
    ) -> WebhookEvent | None:
        """
        Create a new WebhookEvent record if (gateway, event_id) is unseen.

        Returns:
            WebhookEvent: new record (first time seen)
            None: duplicate — caller should return early without processing
        """
        existing = await db.execute(
            select(WebhookEvent).where(
                WebhookEvent.gateway == gateway,
                WebhookEvent.event_id == event_id,
                WebhookEvent.is_deleted.is_(False),
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            logger.info("webhook.duplicate gateway=%s event_id=%s", gateway, event_id)
            return None

        event = WebhookEvent(
            gateway=gateway,
            event_id=event_id,
            event_type=event_type,
            transaction_id=transaction_id,
            payload=payload,
            status="RECEIVED",
        )
        db.add(event)
        try:
            await db.flush()
        except IntegrityError:
            # Race condition — another request inserted the same event_id
            await db.rollback()
            logger.info("webhook.race_condition gateway=%s event_id=%s", gateway, event_id)
            return None

        return event

    @staticmethod
    async def mark_processed(db: AsyncSession, event: WebhookEvent) -> None:
        """Mark a webhook event as successfully processed."""
        event.status = "PROCESSED"
        event.processed_at = datetime.now(timezone.utc)
        await db.flush()

    @staticmethod
    async def mark_failed(db: AsyncSession, event: WebhookEvent, error: str) -> None:
        """Mark a webhook event as failed with an error message."""
        event.status = "FAILED"
        event.error_message = error[:1000]
        await db.flush()
