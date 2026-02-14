# =============================================================================
# Order Module - Pydantic Schemas
# =============================================================================

from datetime import datetime

from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin
from app.shared.enums import OrderStatus


class SelectedOptionInput(BaseDTO):
    """Selected option in an order item."""

    option_group_id: str
    option_id: str


class OrderItemCreate(BaseDTO):
    """Create order item request."""

    menu_item_id: str
    quantity: int = Field(ge=1)
    notes: str | None = None
    selected_options: list[SelectedOptionInput] = []


class OrderItemResponse(BaseDTO):
    """Order item response."""

    id: str
    menu_item_id: str
    name: str
    price: float
    quantity: int
    subtotal: float
    notes: str | None = None
    selected_options: str | None = None


class OrderCreate(BaseDTO):
    """Create order request."""

    merchant_id: str
    items: list[OrderItemCreate] = Field(min_length=1)
    delivery_address: str
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    customer_note: str | None = None


class OrderUpdate(BaseDTO):
    """Update order request (limited fields)."""

    customer_note: str | None = None


class OrderStatusUpdate(BaseDTO):
    """Update order status request."""

    status: OrderStatus
    reason: str | None = None


class OrderResponse(BaseDTO, TimestampMixin):
    """Order response."""

    id: str
    order_number: str
    user_id: str
    merchant_id: str
    driver_id: str | None = None
    status: OrderStatus
    subtotal: float
    delivery_fee: float
    tax: float
    discount: float
    total: float
    delivery_address: str
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    customer_note: str | None = None
    estimated_prep_time: int | None = None
    estimated_delivery_time: int | None = None
    items: list[OrderItemResponse] = []


class OrderListResponse(BaseDTO):
    """Paginated order list."""

    items: list[OrderResponse]
    total: int


class OrderStatusHistoryResponse(BaseDTO):
    """Order status history entry."""

    id: str
    from_status: str | None
    to_status: str
    changed_by: str | None
    reason: str | None
    created_at: datetime
