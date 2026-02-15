# =============================================================================
# Notification Module - ORM Models
# =============================================================================

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel


class Notification(BaseModel):
    """
    Notification record.
    Stores all notifications sent to users.
    """

    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Optional data payload (JSON)
    data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Status
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class DeviceToken(BaseModel):
    """
    User device tokens for push notifications.
    """

    __tablename__ = "device_tokens"

    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    platform: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # ios, android, web

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )


class NotificationPreference(BaseModel):
    """
    User notification preferences.
    """

    __tablename__ = "notification_preferences"

    user_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
    )

    # Channel preferences
    push_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    email_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    sms_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Type preferences
    order_updates: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    promotions: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
