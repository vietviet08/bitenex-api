# =============================================================================
# Notification Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdminOrInternal
from app.modules.notification.schemas import (
    BroadcastNotification,
    DeviceTokenCreate,
    DeviceTokenResponse,
    NotificationListResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
)
from app.modules.notification.service import NotificationService
from app.shared.dto import MessageResponse

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


def get_notification_service(
    db: AsyncSession = Depends(get_db),
) -> NotificationService:
    return NotificationService(db)


# =============================================================================
# User Notifications
# =============================================================================
@router.get(
    "",
    response_model=NotificationListResponse,
    summary="Get my notifications",
)
async def get_notifications(
    user: CurrentUser,
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    """Get current user's notifications."""
    items, total, unread = await service.get_notifications(
        user.user_id, unread_only, page, per_page
    )
    return NotificationListResponse(items=items, total=total, unread_count=unread)


@router.post(
    "/{notification_id}/read",
    response_model=MessageResponse,
    summary="Mark as read",
)
async def mark_as_read(
    notification_id: str,
    user: CurrentUser,
    service: NotificationService = Depends(get_notification_service),
) -> MessageResponse:
    """Mark a notification as read."""
    await service.mark_as_read(notification_id, user.user_id)
    return MessageResponse(message="Marked as read")


@router.post(
    "/read-all",
    response_model=MessageResponse,
    summary="Mark all as read",
)
async def mark_all_as_read(
    user: CurrentUser,
    service: NotificationService = Depends(get_notification_service),
) -> MessageResponse:
    """Mark all notifications as read."""
    await service.mark_all_as_read(user.user_id)
    return MessageResponse(message="All notifications marked as read")


# =============================================================================
# Device Tokens
# =============================================================================
@router.post(
    "/devices",
    response_model=DeviceTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register device",
)
async def register_device(
    data: DeviceTokenCreate,
    user: CurrentUser,
    service: NotificationService = Depends(get_notification_service),
) -> DeviceTokenResponse:
    """Register device for push notifications."""
    return await service.register_device(user.user_id, data)


@router.delete(
    "/devices/{token}",
    response_model=MessageResponse,
    summary="Unregister device",
)
async def unregister_device(
    token: str,
    user: CurrentUser,
    service: NotificationService = Depends(get_notification_service),
) -> MessageResponse:
    """Unregister a device from push notifications."""
    await service.unregister_device(user.user_id, token)
    return MessageResponse(message="Device unregistered")


# =============================================================================
# Preferences
# =============================================================================
@router.get(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    summary="Get preferences",
)
async def get_preferences(
    user: CurrentUser,
    service: NotificationService = Depends(get_notification_service),
) -> NotificationPreferenceResponse:
    """Get notification preferences."""
    return await service.get_preferences(user.user_id)


@router.patch(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    summary="Update preferences",
)
async def update_preferences(
    data: NotificationPreferenceUpdate,
    user: CurrentUser,
    service: NotificationService = Depends(get_notification_service),
) -> NotificationPreferenceResponse:
    """Update notification preferences."""
    return await service.update_preferences(user.user_id, data)


# =============================================================================
# Admin Endpoints
# =============================================================================
@router.post(
    "/broadcast",
    response_model=MessageResponse,
    summary="Broadcast notification",
    dependencies=[RequireAdminOrInternal],
)
async def broadcast(
    data: BroadcastNotification,
    service: NotificationService = Depends(get_notification_service),
) -> MessageResponse:
    """Broadcast notification to users. Admin only."""
    count = await service.broadcast(
        data.title,
        data.body,
        data.type,
        data.user_ids,
        data.data,
    )
    return MessageResponse(message=f"Notification queued for {count} users")
