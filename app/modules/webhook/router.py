# =============================================================================
# Webhook Module - n8n Incoming Webhook Router
# =============================================================================
"""
These endpoints receive events fired FROM n8n back into bitenex-api.
All endpoints:
  1. Verify HMAC-SHA256 signature via RequireN8nSignature
  2. Check WebhookDedup to prevent duplicate processing
  3. Dispatch to internal business logic
  4. Mark event PROCESSED or FAILED
"""

import json
import logging

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import RequireN8nSignature
from app.shared.webhook_dedup import WebhookDedup

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhook/bitenex",
    tags=["Webhooks — n8n Inbound"],
)


# ---------------------------------------------------------------------------
# Shared response schema
# ---------------------------------------------------------------------------

class WebhookAck(BaseModel):
    received: bool
    duplicate: bool = False
    eventId: str | None = None


def _build_event_id(event_type: str, payload: dict) -> str:
    """Derive a stable dedup key from payload fields."""
    if "orderId" in payload:
        return f"{event_type}:{payload['orderId']}"
    if "userId" in payload:
        ts = payload.get("registeredAt") or payload.get("changedAt") or "0"
        return f"{event_type}:{payload['userId']}:{ts}"
    if "checkoutSessionId" in payload:
        return f"{event_type}:{payload['checkoutSessionId']}"
    if "paymentId" in payload:
        return f"{event_type}:{payload['paymentId']}"
    return f"{event_type}:{hash(json.dumps(payload, sort_keys=True))}"


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/user-registered",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Receive user.registered event from n8n",
    dependencies=[RequireN8nSignature],
)
async def user_registered(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebhookAck:
    """Triggered when a new user completes registration. Entrypoint for WF-01."""
    body = await request.body()
    payload = json.loads(body)
    event_id = _build_event_id("user.registered", payload)

    event = await WebhookDedup.ensure_unique(
        db, gateway=WebhookDedup.GATEWAY_N8N,
        event_id=event_id, event_type="user.registered", payload=body.decode(),
    )
    if event is None:
        return WebhookAck(received=True, duplicate=True, eventId=event_id)

    try:
        logger.info("webhook.user_registered user_id=%s", payload.get("userId"))
        await WebhookDedup.mark_processed(db, event)
    except Exception as exc:
        await WebhookDedup.mark_failed(db, event, str(exc))
        raise

    return WebhookAck(received=True, duplicate=False, eventId=event_id)


@router.post(
    "/order-status-changed",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Receive order.status_changed event from n8n",
    dependencies=[RequireN8nSignature],
)
async def order_status_changed(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebhookAck:
    """
    Triggered when order status changes. Entrypoint for WF-03.
    Uses orderId + toStatus as dedup key to allow multiple transitions.
    """
    body = await request.body()
    payload = json.loads(body)
    order_id = payload.get("orderId", "")
    to_status = payload.get("toStatus", "")
    event_id = f"order.status_changed:{order_id}:{to_status}"

    event = await WebhookDedup.ensure_unique(
        db, gateway=WebhookDedup.GATEWAY_N8N,
        event_id=event_id, event_type="order.status_changed", payload=body.decode(),
    )
    if event is None:
        return WebhookAck(received=True, duplicate=True, eventId=event_id)

    try:
        logger.info(
            "webhook.order_status_changed order_id=%s %s→%s",
            order_id, payload.get("fromStatus"), to_status,
        )
        await WebhookDedup.mark_processed(db, event)
    except Exception as exc:
        await WebhookDedup.mark_failed(db, event, str(exc))
        raise

    return WebhookAck(received=True, duplicate=False, eventId=event_id)


@router.post(
    "/order-delivered",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Receive order.delivered event (triggers WF-04)",
    dependencies=[RequireN8nSignature],
)
async def order_delivered(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebhookAck:
    """Triggered when an order is delivered. Entrypoint for WF-04 review flow."""
    body = await request.body()
    payload = json.loads(body)
    event_id = _build_event_id("order.delivered", payload)

    event = await WebhookDedup.ensure_unique(
        db, gateway=WebhookDedup.GATEWAY_N8N,
        event_id=event_id, event_type="order.delivered", payload=body.decode(),
    )
    if event is None:
        return WebhookAck(received=True, duplicate=True, eventId=event_id)

    try:
        logger.info("webhook.order_delivered order_id=%s", payload.get("orderId"))
        await WebhookDedup.mark_processed(db, event)
    except Exception as exc:
        await WebhookDedup.mark_failed(db, event, str(exc))
        raise

    return WebhookAck(received=True, duplicate=False, eventId=event_id)


@router.post(
    "/checkout-abandoned",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Receive checkout.abandoned event",
    dependencies=[RequireN8nSignature],
)
async def checkout_abandoned(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebhookAck:
    """Triggered by checkout abandonment. Entrypoint for WF-02."""
    body = await request.body()
    payload = json.loads(body)
    event_id = _build_event_id("checkout.abandoned", payload)

    event = await WebhookDedup.ensure_unique(
        db, gateway=WebhookDedup.GATEWAY_N8N,
        event_id=event_id, event_type="checkout.abandoned", payload=body.decode(),
    )
    if event is None:
        return WebhookAck(received=True, duplicate=True, eventId=event_id)

    try:
        logger.info("webhook.checkout_abandoned session_id=%s", payload.get("checkoutSessionId"))
        await WebhookDedup.mark_processed(db, event)
    except Exception as exc:
        await WebhookDedup.mark_failed(db, event, str(exc))
        raise

    return WebhookAck(received=True, duplicate=False, eventId=event_id)


@router.post(
    "/payment-failed",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Receive payment.failed event",
    dependencies=[RequireN8nSignature],
)
async def payment_failed(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebhookAck:
    """Triggered when a payment attempt fails. Entrypoint for WF-06."""
    body = await request.body()
    payload = json.loads(body)
    event_id = _build_event_id("payment.failed", payload)

    event = await WebhookDedup.ensure_unique(
        db, gateway=WebhookDedup.GATEWAY_N8N,
        event_id=event_id, event_type="payment.failed", payload=body.decode(),
    )
    if event is None:
        return WebhookAck(received=True, duplicate=True, eventId=event_id)

    try:
        logger.info(
            "webhook.payment_failed payment_id=%s error=%s",
            payload.get("paymentId"), payload.get("errorCode"),
        )
        await WebhookDedup.mark_processed(db, event)
    except Exception as exc:
        await WebhookDedup.mark_failed(db, event, str(exc))
        raise

    return WebhookAck(received=True, duplicate=False, eventId=event_id)
