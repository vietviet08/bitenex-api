# =============================================================================
# Payment Module - ORM Models
# =============================================================================

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel
from app.shared.enums import PaymentStatus


class Payment(BaseModel):
    """
    Payment transaction record.
    Stores all payment attempts and their status.
    """

    __tablename__ = "payments"

    # Transaction ID (external reference)
    transaction_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    # Links
    order_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    # Amount
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )

    # Payment details
    method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=PaymentStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    # Gateway response
    gateway: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gateway_transaction_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    gateway_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Error tracking
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Refund(BaseModel):
    """
    Refund transaction record.
    """

    __tablename__ = "refunds"

    payment_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    order_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)

    reason: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False,
    )  # PENDING, PROCESSING, COMPLETED, FAILED

    refunded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class PaymentMethod(BaseModel):
    """
    Saved payment methods for users.
    """

    __tablename__ = "payment_methods"

    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Masked/tokenized data
    last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Gateway token
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    gateway: Mapped[str] = mapped_column(String(50), nullable=False)

    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
