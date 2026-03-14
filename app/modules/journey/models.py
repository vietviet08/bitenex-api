# =============================================================================
# Journey Module - ORM Models
# =============================================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel


class AbandonedCartJourney(BaseModel):
    """
    Tracks cart activity snapshots so the backend can detect abandoned carts.
    """

    __tablename__ = "abandoned_cart_journeys"

    cart_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    merchant_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    merchant_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    cart_value: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="VND",
        nullable=False,
    )

    item_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    restaurant_open: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    items_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    deep_link: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    payload_snapshot: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        nullable=False,
        index=True,
    )

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    abandoned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    webhook_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_webhook_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    recovery_order_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )


class JourneyOffer(BaseModel):
    """
    Stores journey-generated offers until the main coupon engine exists.
    """

    __tablename__ = "journey_offers"

    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    journey_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    source_cart_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    offer_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    max_discount: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    min_cart_value: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        nullable=False,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
