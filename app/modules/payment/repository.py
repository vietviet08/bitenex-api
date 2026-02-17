# =============================================================================
# Payment Module - Repository Helpers
# =============================================================================

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payment.models import IdempotencyKey, WebhookEvent


class PaymentRepository:
    """Lightweight persistence helpers for payment module primitives."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_idempotency_record(self, scope: str, key: str) -> IdempotencyKey | None:
        result = await self.db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.scope == scope,
                IdempotencyKey.key == key,
                IdempotencyKey.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def save_idempotency_response(
        self,
        record: IdempotencyKey,
        *,
        status_code: int,
        payload: dict,
    ) -> None:
        record.response_status = status_code
        record.response_payload = json.dumps(payload, sort_keys=True)
        await self.db.flush()

    async def mark_webhook_processed(self, event: WebhookEvent) -> None:
        event.status = "PROCESSED"
        event.processed_at = datetime.now(timezone.utc)
        event.error_message = None
        await self.db.flush()

    async def mark_webhook_error(self, event: WebhookEvent, message: str) -> None:
        event.status = "FAILED"
        event.processed_at = datetime.now(timezone.utc)
        event.error_message = message
        await self.db.flush()
