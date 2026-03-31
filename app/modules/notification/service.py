# =============================================================================
# Notification Module - Service Layer
# =============================================================================

import json
import logging
import os
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.integrations.firebase import get_firebase_app
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

logger = logging.getLogger(__name__)
settings = get_settings()


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

    @staticmethod
    def has_firebase_configuration() -> bool:
        """Check whether Firebase Admin can be initialized for FCM sending."""
        return bool(
            settings.firebase_project_id
            or settings.firebase_credentials_json
            or settings.firebase_credentials_path
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        )

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
    ) -> int:
        """Send push notification to user's devices."""
        from firebase_admin import messaging

        result = await self.db.execute(
            select(DeviceToken).where(
                DeviceToken.user_id == user_id,
                DeviceToken.is_active.is_(True),
                DeviceToken.is_deleted.is_(False),
            )
        )
        tokens = result.scalars().all()
        if not tokens:
            return 0

        if not self.has_firebase_configuration():
            logger.warning(
                "push.skipped_missing_firebase_configuration user_id=%s token_count=%s",
                user_id,
                len(tokens),
            )
            return 0

        firebase_app = get_firebase_app()
        payload = self._stringify_push_data(data)
        sent_count = 0

        for device_token in tokens:
            try:
                message = messaging.Message(
                    token=device_token.token,
                    notification=messaging.Notification(title=title, body=body),
                    data=payload,
                    android=messaging.AndroidConfig(
                        priority="high",
                        notification=messaging.AndroidNotification(
                            sound="default",
                        ),
                    ),
                    apns=messaging.APNSConfig(
                        headers={"apns-priority": "10"},
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(
                                sound="default",
                                content_available=True,
                            )
                        ),
                    ),
                )
                messaging.send(message, app=firebase_app)
                sent_count += 1
            except Exception as exc:
                logger.exception(
                    "push.send_failed user_id=%s token_id=%s",
                    user_id,
                    device_token.id,
                )
                if "registration-token-not-registered" in str(exc).lower():
                    device_token.is_active = False

        return sent_count

    async def count_active_devices(self, user_id: str) -> int:
        """Count active device tokens for a user."""
        result = await self.db.execute(
            select(func.count(DeviceToken.id)).where(
                DeviceToken.user_id == user_id,
                DeviceToken.is_active.is_(True),
                DeviceToken.is_deleted.is_(False),
            )
        )
        return int(result.scalar() or 0)

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
        result = await self.db.execute(
            select(DeviceToken).where(
                DeviceToken.token == data.token,
                DeviceToken.is_deleted.is_(False),
            )
        )
        device = result.scalar_one_or_none()

        if device is None:
            device = DeviceToken(
                user_id=user_id,
                token=data.token,
                platform=data.platform,
                is_active=True,
            )
            self.db.add(device)
        else:
            device.user_id = user_id
            device.platform = data.platform
            device.is_active = True

        await self.db.flush()
        await self.db.refresh(device)
        return DeviceTokenResponse.model_validate(device)

    async def unregister_device(
        self,
        user_id: str,
        token: str,
    ) -> None:
        """Unregister a device."""
        result = await self.db.execute(
            select(DeviceToken).where(
                DeviceToken.user_id == user_id,
                DeviceToken.token == token,
                DeviceToken.is_deleted.is_(False),
            )
        )
        device = result.scalar_one_or_none()
        if device is None:
            raise NotFoundError("Device token", token)

        device.is_active = False
        await self.db.flush()

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

    @staticmethod
    def _stringify_push_data(data: dict[str, Any] | None) -> dict[str, str]:
        if not data:
            return {}

        payload: dict[str, str] = {}
        for key, value in data.items():
            if isinstance(value, str):
                payload[key] = value
            else:
                payload[key] = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        return payload
