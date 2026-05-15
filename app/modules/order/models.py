# =============================================================================
# Order Module - ORM Models
# =============================================================================

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from transformers import Optional

from app.modules.base import BaseModel
from app.shared.enums import OrderStatus


class Order(BaseModel):
    """
    Order entity representing a food delivery order.
    Central entity connecting users, merchants, and drivers.
    """

    __tablename__ = "orders"

    # Order number (human-readable)
    order_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    # Participants
    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    merchant_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    driver_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=OrderStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    status_reason: Optional[str] = Field(
        default=None, 
        max_length=255,
        description="Lý do thay đổi trạng thái"
    )
    
    # Pricing
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tax: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    discount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total: Mapped[float] = mapped_column(Float, nullable=False)

    # Delivery address
    delivery_address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    delivery_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Notes
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    estimated_prep_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_delivery_time: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OrderItem(BaseModel):
    """
    Individual items in an order.
    """

    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    menu_item_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )

    # Snapshot of item at order time
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)

    # Special instructions
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON snapshot of selected options at order time
    selected_options: Mapped[str | None] = mapped_column(Text, nullable=True)


class OrderStatusHistory(BaseModel):
    """
    Track order status changes for audit trail.
    """

    __tablename__ = "order_status_history"

    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)

    changed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
