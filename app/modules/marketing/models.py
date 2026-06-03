# =============================================================================
# Marketing Module - Campaign Models
# =============================================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel


class Campaign(BaseModel):
    """
    Marketing campaign for promotions and discounts.
    """

    __tablename__ = "campaigns"

    # Basic info
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Campaign type
    campaign_type: Mapped[str] = mapped_column(
        String(50),
        default="DISCOUNT",
        nullable=False,
        index=True,
    )  # DISCOUNT, FREE_DELIVERY, BUNDLE, LOYALTY

    # Discount settings
    discount_type: Mapped[str] = mapped_column(
        String(30),
        default="PERCENTAGE",
        nullable=False,
    )  # PERCENTAGE, FIXED_AMOUNT

    discount_value: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    max_discount: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    min_order_value: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Voucher settings
    voucher_code: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
    )

    auto_generate_vouchers: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    max_vouchers: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    used_vouchers: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Targeting
    target_audience: Mapped[str] = mapped_column(
        String(50),
        default="ALL",
        nullable=False,
    )  # ALL, NEW_USERS, RETURNING_USERS, VIP

    # Scheduling
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="DRAFT",
        nullable=False,
        index=True,
    )  # DRAFT, SCHEDULED, ACTIVE, PAUSED, ENDED, CANCELLED

    # Budget
    budget: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    spent: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Stats
    total_orders: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_revenue: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Metadata
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
