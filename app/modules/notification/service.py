import json
import logging
from typing import Any

from sqlalchemy import func, select, update
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
from app.realtime.events import RealtimeEventType
from app.realtime.socket_manager import connection_manager
from app.shared.enums import NotificationChannel, NotificationType

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Notification service.
    Handles sending and managing notifications.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _serialize_data(data: dict[str, Any] | None) -> str | None:
        if data is None:
            return None
        return json.dumps(data, sort_keys=True)

    @staticmethod
    def _deserialize_data(raw_data: str | None) -> dict[str, Any] | None:
        if not raw_data:
            return None
        try:
            parsed = json.loads(raw_data)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _to_notification_response(notification: Notification) -> NotificationResponse:
        return NotificationResponse(
            id=notification.id,
            user_id=notification.user_id,
            type=NotificationType(notification.type),
            channel=NotificationChannel(notification.channel),
            title=notification.title,
            body=notification.body,
            data=NotificationService._deserialize_data(notification.data),
            is_read=notification.is_read,
            is_sent=notification.is_sent,
            created_at=notification.created_at,
            updated_at=notification.updated_at,
        )

    @staticmethod
    def _to_preference_response(
        preference: NotificationPreference,
    ) -> NotificationPreferenceResponse:
        return NotificationPreferenceResponse(
            push_enabled=preference.push_enabled,
            email_enabled=preference.email_enabled,
            sms_enabled=preference.sms_enabled,
            order_updates=preference.order_updates,
            promotions=preference.promotions,
        )

    async def _get_or_create_preferences(self, user_id: str) -> NotificationPreference:
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.is_deleted.is_(False),
            )
        )
        preference = result.scalar_one_or_none()
        if preference:
            return preference

        preference = NotificationPreference(user_id=user_id)
        self.db.add(preference)
        await self.db.flush()
        await self.db.refresh(preference)
        return preference

    @staticmethod
    def _is_type_enabled(
        preference: NotificationPreference,
        notification_type: NotificationType,
    ) -> bool:
        if notification_type == NotificationType.PROMOTION:
            return preference.promotions
        if notification_type in {
            NotificationType.ORDER_UPDATE,
            NotificationType.PAYMENT,
            NotificationType.CHAT,
        }:
            return preference.order_updates
        return True

    @staticmethod
    def _is_channel_enabled(
        preference: NotificationPreference,
        channel: NotificationChannel,
    ) -> bool:
        if channel == NotificationChannel.PUSH:
            return preference.push_enabled
        if channel == NotificationChannel.EMAIL:
            return preference.email_enabled
        if channel == NotificationChannel.SMS:
            return preference.sms_enabled
        return True

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
        preference = await self._get_or_create_preferences(data.user_id)

        notification = Notification(
            user_id=data.user_id,
            type=data.type.value,
            channel=data.channel.value,
            title=data.title,
            body=data.body,
            data=self._serialize_data(data.data),
            is_read=False,
            is_sent=False,
        )
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)

        type_enabled = self._is_type_enabled(preference, data.type)
        channel_enabled = self._is_channel_enabled(preference, data.channel)

        if not type_enabled:
            notification.error_message = "Notification type disabled by user preferences"
            await self.db.flush()
            return self._to_notification_response(notification)

        if not channel_enabled:
            notification.error_message = "Notification channel disabled by user preferences"
            await self.db.flush()
            return self._to_notification_response(notification)

        try:
            if data.channel == NotificationChannel.IN_APP:
                notification.is_sent = True
                notification.error_message = None
                await self.db.flush()
                payload = self._to_notification_response(notification).model_dump(mode="json")
                await connection_manager.send_personal(
                    data.user_id,
                    {
                        "event": RealtimeEventType.NOTIFICATION_NEW.value,
                        "data": payload,
                    },
                )
            elif data.channel == NotificationChannel.PUSH:
                await self.send_push(data.user_id, data.title, data.body, data.data)
                notification.is_sent = True
                notification.error_message = None
            elif data.channel == NotificationChannel.EMAIL:
                await self.send_email(data.user_id, data.title, data.body)
                notification.is_sent = True
                notification.error_message = None
            elif data.channel == NotificationChannel.SMS:
                await self.send_sms(data.user_id, data.body)
                notification.is_sent = True
                notification.error_message = None
        except Exception as exc:
            logger.warning(
                "notification.send.failed user_id=%s type=%s channel=%s error=%s",
                data.user_id,
                data.type.value,
                data.channel.value,
                str(exc),
            )
            notification.is_sent = False
            notification.error_message = str(exc)

        await self.db.flush()
        await self.db.refresh(notification)
        return self._to_notification_response(notification)

    async def send_push(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Send push notification to user's devices."""
        logger.info("notification.push.stub user_id=%s title=%s", user_id, title)

    async def send_email(
        self,
        user_id: str,
        subject: str,
        body: str,
        template: str | None = None,
    ) -> None:
        """Send email notification."""
        logger.info("notification.email.stub user_id=%s subject=%s", user_id, subject)

    async def send_sms(
        self,
        user_id: str,
        message: str,
    ) -> None:
        """Send SMS notification."""
        logger.info("notification.sms.stub user_id=%s", user_id)

    async def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[NotificationResponse], int, int]:
        """Get user's notifications."""
        filters = [
            Notification.user_id == user_id,
            Notification.is_deleted.is_(False),
        ]
        if unread_only:
            filters.append(Notification.is_read.is_(False))

        query = (
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        count_query = select(func.count(Notification.id)).where(*filters)
        unread_count_query = select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_deleted.is_(False),
            Notification.is_read.is_(False),
        )

        rows = (await self.db.execute(query)).scalars().all()
        total = int((await self.db.execute(count_query)).scalar_one())
        unread_count = int((await self.db.execute(unread_count_query)).scalar_one())

        items = [self._to_notification_response(item) for item in rows]
        return items, total, unread_count

    async def mark_as_read(
        self,
        notification_id: str,
        user_id: str,
    ) -> None:
        """Mark notification as read."""
        result = await self.db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.is_deleted.is_(False),
            )
        )
        notification = result.scalar_one_or_none()
        if not notification:
            raise NotFoundError(message="Notification not found")

        if not notification.is_read:
            notification.is_read = True
            await self.db.flush()

    async def mark_all_as_read(self, user_id: str) -> None:
        """Mark all notifications as read."""
        await self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_deleted.is_(False),
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await self.db.flush()

    # Device tokens
    async def register_device(
        self,
        user_id: str,
        data: DeviceTokenCreate,
    ) -> DeviceTokenResponse:
        """Register device for push notifications."""
        existing_result = await self.db.execute(
            select(DeviceToken).where(
                DeviceToken.token == data.token,
                DeviceToken.is_deleted.is_(False),
            )
        )
        device = existing_result.scalar_one_or_none()

        if device:
            device.user_id = user_id
            device.platform = data.platform
            device.is_active = True
        else:
            device = DeviceToken(
                user_id=user_id,
                token=data.token,
                platform=data.platform,
                is_active=True,
            )
            self.db.add(device)

        await self.db.flush()
        await self.db.refresh(device)
        return DeviceTokenResponse(
            id=device.id,
            platform=device.platform,
            is_active=device.is_active,
        )

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
        if not device:
            return
        if device.is_active:
            device.is_active = False
            await self.db.flush()

    # Preferences
    async def get_preferences(
        self,
        user_id: str,
    ) -> NotificationPreferenceResponse:
        """Get user's notification preferences."""
        preference = await self._get_or_create_preferences(user_id)
        return self._to_preference_response(preference)

    async def update_preferences(
        self,
        user_id: str,
        data: NotificationPreferenceUpdate,
    ) -> NotificationPreferenceResponse:
        """Update notification preferences."""
        preference = await self._get_or_create_preferences(user_id)

        for field_name in [
            "push_enabled",
            "email_enabled",
            "sms_enabled",
            "order_updates",
            "promotions",
        ]:
            value = getattr(data, field_name)
            if value is not None:
                setattr(preference, field_name, value)

        await self.db.flush()
        await self.db.refresh(preference)
        return self._to_preference_response(preference)

    async def broadcast(
        self,
        title: str,
        body: str,
        notification_type: NotificationType,
        user_ids: list[str] | None = None,
    ) -> int:
        """
        Broadcast notification to multiple users.
        Returns count of notifications queued.
        """
        if user_ids is None:
            rows = await self.db.execute(
                select(User.id).where(
                    User.is_deleted.is_(False),
                    User.is_active.is_(True),
                )
            )
            targets = [row[0] for row in rows.all()]
        else:
            targets = [item.strip() for item in user_ids if item and item.strip()]

        count = 0
        for user_id in targets:
            try:
                await self.send_notification(
                    NotificationCreate(
                        user_id=user_id,
                        type=notification_type,
                        channel=NotificationChannel.IN_APP,
                        title=title,
                        body=body,
                    )
                )
                count += 1
            except Exception as exc:
                logger.warning(
                    "notification.broadcast.user_failed user_id=%s error=%s",
                    user_id,
                    str(exc),
                )

        return count
