# =============================================================================
# Notification Module - Service Layer
# =============================================================================

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.notification.models import DeviceToken, Notification, NotificationPreference
from app.modules.notification.schemas import (
    DeviceTokenCreate,
    DeviceTokenResponse,
    NotificationCreate,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
)
from app.modules.user.models import User
from app.shared.enums import NotificationChannel
from app.shared.enums import NotificationType


class NotificationService:
    """
    Notification service.
    Handles sending and managing notifications.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _normalize_notification_type(notification_type: NotificationType | str) -> str:
        """Support both enum instances and Pydantic-coerced enum values."""
        if isinstance(notification_type, NotificationType):
            return notification_type.value
        return str(notification_type)

    async def send_notification(
        self,
        data: NotificationCreate,
    ) -> NotificationResponse:
        """
        Send a notification to a user.

        Steps:
        1. Check user preferences
        2. Create notification record
        3. Send via appropriate channel
        4. Update sent status
        """
        # TODO: Implement
        raise NotImplementedError()

    async def send_push(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Send push notification to user's devices."""
        # TODO: Implement
        pass

    async def send_email(
        self,
        user_id: str,
        subject: str,
        body: str,
        template: str | None = None,
    ) -> None:
        """Send email notification."""
        # TODO: Implement
        pass

    async def send_sms(
        self,
        user_id: str,
        message: str,
    ) -> None:
        """Send SMS notification."""
        # TODO: Implement
        pass

    async def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[NotificationResponse], int, int]:
        """Get user's notifications."""
        # TODO: Implement
        # Returns (notifications, total, unread_count)
        raise NotImplementedError()

    async def mark_as_read(
        self,
        notification_id: str,
        user_id: str,
    ) -> None:
        """Mark notification as read."""
        # TODO: Implement
        pass

    async def mark_all_as_read(self, user_id: str) -> None:
        """Mark all notifications as read."""
        # TODO: Implement
        pass

    # Device tokens
    async def register_device(
        self,
        user_id: str,
        data: DeviceTokenCreate,
    ) -> DeviceTokenResponse:
        """Register device for push notifications."""
        # TODO: Implement
        raise NotImplementedError()

    async def unregister_device(
        self,
        user_id: str,
        token: str,
    ) -> None:
        """Unregister a device."""
        # TODO: Implement
        pass

    # Preferences
    async def get_preferences(
        self,
        user_id: str,
    ) -> NotificationPreferenceResponse:
        """Get user's notification preferences."""
        # TODO: Implement
        raise NotImplementedError()

    async def update_preferences(
        self,
        user_id: str,
        data: NotificationPreferenceUpdate,
    ) -> NotificationPreferenceResponse:
        """Update notification preferences."""
        # TODO: Implement
        raise NotImplementedError()

    async def broadcast(
        self,
        title: str,
        body: str,
        notification_type: NotificationType | str,
        user_ids: list[str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> int:
        """
        Broadcast notification to multiple users.
        Returns count of notifications queued.
        """
        if user_ids:
            resolved_user_ids = user_ids
        else:
            result = await self.db.execute(
                select(User.id).where(
                    User.is_deleted.is_(False),
                    User.is_active.is_(True),
                )
            )
            resolved_user_ids = list(result.scalars().all())

        if not resolved_user_ids:
            return 0

        payload = json.dumps(data, sort_keys=True) if data else None
        notification_type_value = self._normalize_notification_type(notification_type)
        notifications = [
            Notification(
                user_id=user_id,
                type=notification_type_value,
                channel=NotificationChannel.PUSH.value,
                title=title,
                body=body,
                data=payload,
                is_read=False,
                is_sent=True,
                error_message=None,
            )
            for user_id in resolved_user_ids
        ]
        self.db.add_all(notifications)
        await self.db.flush()
        return len(notifications)
