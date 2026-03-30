# =============================================================================
# Notification Module - Internal API Router (n8n endpoints)
# =============================================================================

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import RequireInternalService
from app.modules.notification.models import Notification

logger = logging.getLogger(__name__)

internal_router = APIRouter(
    prefix="/internal/notifications",
    tags=["Internal — Notifications"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PushNotificationRequest(BaseModel):
    userId: str
    title: str
    body: str
    data: dict | None = None
    badge: int | None = None


class InAppNotificationRequest(BaseModel):
    userId: str
    type: str = "ORDER_UPDATE"
    channel: str = "IN_APP"
    title: str
    body: str
    data: dict | None = None


class NotificationAck(BaseModel):
    notificationId: str
    sent: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@internal_router.post(
    "/push",
    response_model=NotificationAck,
    status_code=status.HTTP_200_OK,
    summary="Send push notification to a user",
    dependencies=[RequireInternalService],
)
async def send_push_notification(
    req: PushNotificationRequest,
    db: AsyncSession = Depends(get_db),
) -> NotificationAck:
    """
    Store a push notification record and log for FCM dispatch.
    Used by WF-01 → WF-08 to send push messages.
    In production, integrate with FCM/APNs here.
    """
    notif = Notification(
        user_id=req.userId,
        type="PUSH",
        channel="PUSH_NOTIFICATION",
        title=req.title,
        body=req.body,
        data=str(req.data or {}),
        is_read=False,
    )
    db.add(notif)
    await db.flush()
    await db.refresh(notif)

    logger.info(
        "push.queued user_id=%s title=%s notification_id=%s",
        req.userId, req.title, notif.id,
    )

    return NotificationAck(notificationId=notif.id, sent=True)


@internal_router.post(
    "/in-app",
    response_model=NotificationAck,
    status_code=status.HTTP_200_OK,
    summary="Store an in-app notification record",
    dependencies=[RequireInternalService],
)
async def send_in_app_notification(
    req: InAppNotificationRequest,
    db: AsyncSession = Depends(get_db),
) -> NotificationAck:
    """
    Persist an in-app notification to be rendered in the mobile/web UI.
    Used by WF-03 order lifecycle orchestration.
    """
    notif = Notification(
        user_id=req.userId,
        type=req.type,
        channel=req.channel,
        title=req.title,
        body=req.body,
        data=str(req.data or {}),
        is_read=False,
    )
    db.add(notif)
    await db.flush()
    await db.refresh(notif)

    return NotificationAck(notificationId=notif.id, sent=True)
