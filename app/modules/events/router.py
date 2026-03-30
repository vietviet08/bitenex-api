# =============================================================================
# Events Module - Router
# =============================================================================

import logging

from fastapi import APIRouter, status
from pydantic import BaseModel

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
    properties: dict | None = None
    timestamp: str | None = None


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
