# =============================================================================
# Payment Module - Pydantic Schemas
# =============================================================================

from datetime import datetime

from app.shared.dto import BaseDTO, TimestampMixin
from app.shared.enums import PaymentMethod, PaymentStatus


class PaymentCreate(BaseDTO):
    """Create payment request."""
    order_id: str
    amount: float
    currency: str = "USD"
    method: PaymentMethod
    payment_method_id: str | None = None  # For saved payment methods


class PaymentResponse(BaseDTO, TimestampMixin):
    """Payment response."""
    id: str
    transaction_id: str
    order_id: str
    user_id: str
    amount: float
    currency: str
    method: str
    status: PaymentStatus
    gateway: str | None = None
    error_message: str | None = None


class RefundCreate(BaseDTO):
    """Create refund request."""
    payment_id: str
    amount: float | None = None  # Full refund if None
    reason: str


class RefundResponse(BaseDTO, TimestampMixin):
    """Refund response."""
    id: str
    payment_id: str
    order_id: str
    amount: float
    reason: str
    status: str
    refunded_by: str | None = None


class SavedPaymentMethodResponse(BaseDTO):
    """Saved payment method response."""
    id: str
    type: str
    last_four: str | None = None
    brand: str | None = None
    is_default: bool


class AddPaymentMethodRequest(BaseDTO):
    """Add payment method request."""
    type: PaymentMethod
    token: str  # Token from payment gateway


class PaymentWebhookPayload(BaseDTO):
    """Payment gateway webhook payload."""
    gateway: str
    event_type: str
    transaction_id: str
    status: str
    raw_payload: dict
