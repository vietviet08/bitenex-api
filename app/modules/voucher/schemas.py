# =============================================================================
# Voucher Module - Pydantic Schemas
# =============================================================================

from datetime import datetime

from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin
from app.shared.enums import VoucherStatus


class VoucherResponse(BaseDTO, TimestampMixin):
    """Single voucher response."""

    id: str
    user_id: str
    code: str
    max_discount: float
    min_cart_value: float
    status: VoucherStatus
    expires_at: datetime
    consumed_at: datetime | None = None


class VoucherListResponse(BaseDTO):
    """Paginated list of vouchers."""

    items: list[VoucherResponse]
    total: int
    page: int
    per_page: int


class VoucherValidateRequest(BaseDTO):
    """Validate voucher for cart."""

    code: str = Field(min_length=1, max_length=50)
    cart_value: float = Field(ge=0)


class VoucherValidateResponse(BaseDTO):
    """Voucher validation result."""

    is_valid: bool
    code: str | None = None
    discount_amount: float = 0.0
    error_message: str | None = None


class VoucherCreateRequest(BaseDTO):
    """Admin creates manual voucher."""

    code: str = Field(min_length=1, max_length=50)
    user_id: str = Field(min_length=1, max_length=36)
    max_discount: float = Field(ge=0)
    min_cart_value: float = Field(default=0, ge=0)
    expires_in_days: int = Field(default=7, ge=1, le=365)


class VoucherUpdateRequest(BaseDTO):
    """Admin updates voucher."""

    max_discount: float | None = Field(default=None, ge=0)
    expires_at: datetime | None = None
    status: VoucherStatus | None = None


class IssueVoucherRequest(BaseDTO):
    """Internal: n8n issues voucher."""

    userId: str
    voucherCode: str
    discountAmount: float
    freeDeliveryOrders: int | None = None
    expiresInDays: int = 7
    reason: str | None = "n8n_workflow"


class IssueVoucherResponse(BaseDTO):
    """Internal: voucher issuance response."""

    voucherCode: str
    discountAmount: float
    expiresAt: datetime
    isExisting: bool


class AdminVoucherListResponse(BaseDTO):
    """Admin paginated list of all vouchers."""

    items: list[VoucherResponse]
    total: int
    page: int
    per_page: int
