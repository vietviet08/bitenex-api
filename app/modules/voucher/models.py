from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import String, Integer, Boolean, ForeignKey, DECIMAL, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.base import BaseModel
from app.shared.enums import VoucherType, VoucherStatus


class Voucher(BaseModel):
    __tablename__ = "vouchers"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    type: Mapped[VoucherType] = mapped_column(String(20), nullable=False)
    value: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)

    min_order_value: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), default=0)
    max_discount: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 2), nullable=True)

    total_usage_limit: Mapped[int] = mapped_column(Integer, default=10000)
    per_user_limit: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    status: Mapped[VoucherStatus] = mapped_column(String(20), default=VoucherStatus.ACTIVE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user_vouchers: Mapped[List["UserVoucher"]] = relationship("UserVoucher", back_populates="voucher", lazy="selectin")


class UserVoucher(BaseModel):
    __tablename__ = "user_vouchers"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    voucher_id: Mapped[int] = mapped_column(ForeignKey("vouchers.id"), nullable=False)

    times_used: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User")
    voucher: Mapped["Voucher"] = relationship("Voucher", back_populates="user_vouchers")