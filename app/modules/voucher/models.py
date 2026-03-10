# =============================================================================
# Voucher Module - ORM Models
# =============================================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel
from app.shared.enums import VoucherDiscountType


class Voucher(BaseModel):
    """
    Discount voucher that can be applied during order creation.
    """

    __tablename__ = "vouchers"

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    merchant_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    discount_type: Mapped[str] = mapped_column(
        String(20),
        default=VoucherDiscountType.PERCENTAGE.value,
        nullable=False,
    )

    discount_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    max_discount_amount: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    min_order_amount: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    usage_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    per_user_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
