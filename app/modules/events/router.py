# =============================================================================
# Events Module - Router
# =============================================================================

import json
import logging
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal/events",
    tags=["Internal — Events"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TrackEventRequest(BaseModel):
    event: str
    userId: str | None = None
    properties: dict[str, Any] | None = None
    timestamp: str | None = None

    @field_validator("properties", mode="before")
    @classmethod
    def parse_stringified_properties(cls, value: Any) -> dict[str, Any] | None:
        """
        Accept both native JSON objects and stringified JSON.

        n8n HTTP Request nodes in this repo currently send `properties`
        as `JSON.stringify(...)`, so we normalize that here.
        """
        if value in (None, ""):
            return None

        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("properties must be a JSON object")
            return parsed

        return value


class TrackEventResponse(BaseModel):
    tracked: bool
    event: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/track",
    response_model=TrackEventResponse,
    status_code=status.HTTP_200_OK,
    summary="Track an analytics event from n8n workflow",
)
async def track_event(req: TrackEventRequest) -> TrackEventResponse:
    """
    Structured event logging endpoint called by all 8 n8n workflows.

    In production, pipe this to Mixpanel / GA4 / warehouse.
    For MVP, events are logged with structured fields.

    Events tracked:
      WF-01: user_registered, first_order_converted, unactivated_24h
      WF-02: checkout_abandoned, checkout_recovered
      WF-03: order_status_updated, order_delivered
      WF-04: review_submitted, reorder_success
      WF-05: sla_warning_driver, sla_breach
      WF-06: payment_failed, payment_recovered
      WF-07: daily_digest_sent
      WF-08: winback_success, user_churned
    """
    logger.info(
        "analytics.event event=%s user_id=%s properties=%s",
        req.event,
        req.userId,
        req.properties,
    )
    return TrackEventResponse(tracked=True, event=req.event)
