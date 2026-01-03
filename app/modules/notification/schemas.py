# =============================================================================
# Notification Module - Pydantic Schemas
# =============================================================================

from datetime import datetime
from typing import Any

from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin
from app.shared.enums import NotificationChannel, NotificationType


class NotificationCreate(BaseDTO):
    """Create notification request."""
    user_id: str
    type: NotificationType
    channel: NotificationChannel
    title: str = Field(max_length=255)
    body: str
    data: dict[str, Any] | None = None


class NotificationResponse(BaseDTO, TimestampMixin):
    """Notification response."""
    id: str
    user_id: str
    type: NotificationType
    channel: NotificationChannel
    title: str
    body: str
    data: dict[str, Any] | None = None
    is_read: bool
    is_sent: bool


class NotificationListResponse(BaseDTO):
    """Paginated notification list."""
    items: list[NotificationResponse]
    total: int
    unread_count: int


class DeviceTokenCreate(BaseDTO):
    """Register device token request."""
    token: str
    platform: str = Field(pattern="^(ios|android|web)$")


class DeviceTokenResponse(BaseDTO):
    """Device token response."""
    id: str
    platform: str
    is_active: bool


class NotificationPreferenceUpdate(BaseDTO):
    """Update notification preferences."""
    push_enabled: bool | None = None
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    order_updates: bool | None = None
    promotions: bool | None = None


class NotificationPreferenceResponse(BaseDTO):
    """Notification preferences response."""
    push_enabled: bool
    email_enabled: bool
    sms_enabled: bool
    order_updates: bool
    promotions: bool


class BroadcastNotification(BaseDTO):
    """Broadcast notification to multiple users."""
    user_ids: list[str] | None = None  # None = all users
    type: NotificationType
    title: str
    body: str
    data: dict[str, Any] | None = None
