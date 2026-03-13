# =============================================================================
# Voucher Module - Pydantic Schemas
# =============================================================================

from datetime import datetime

from pydantic import Field, model_validator

from app.shared.dto import BaseDTO, TimestampMixin
from app.shared.enums import VoucherDiscountType


class VoucherBase(BaseDTO):
    """Shared voucher fields."""

    description: str | None = None
    merchant_id: str | None = None
    discount_type: VoucherDiscountType
    discount_value: float = Field(gt=0)
    max_discount_amount: float | None = Field(default=None, gt=0)
    min_order_amount: float = Field(default=0.0, ge=0)
    usage_limit: int | None = Field(default=None, ge=1)
    per_user_limit: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_window(self) -> "VoucherBase":
        if self.expires_at and self.starts_at and self.expires_at <= self.starts_at:
            raise ValueError("expires_at must be after starts_at")
        return self


class VoucherCreate(VoucherBase):
    """Create voucher request."""

    code: str = Field(min_length=3, max_length=50)


class VoucherUpdate(BaseDTO):
    """Update voucher request."""

    description: str | None = None
    merchant_id: str | None = None
    discount_type: VoucherDiscountType | None = None
    discount_value: float | None = Field(default=None, gt=0)
    max_discount_amount: float | None = Field(default=None, gt=0)
    min_order_amount: float | None = Field(default=None, ge=0)
    usage_limit: int | None = Field(default=None, ge=1)
    per_user_limit: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_window(self) -> "VoucherUpdate":
        if self.expires_at and self.starts_at and self.expires_at <= self.starts_at:
            raise ValueError("expires_at must be after starts_at")
        return self


class VoucherResponse(BaseDTO, TimestampMixin):
    """Voucher response."""

    id: str
    code: str
    description: str | None = None
    merchant_id: str | None = None
    discount_type: VoucherDiscountType
    discount_value: float
    max_discount_amount: float | None = None
    min_order_amount: float
    usage_limit: int | None = None
    usage_count: int
    per_user_limit: int | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool


class VoucherListResponse(BaseDTO):
    """Paginated voucher list."""

    items: list[VoucherResponse]
    total: int


class VoucherValidationRequest(BaseDTO):
    """Validate a voucher against an order subtotal."""

    code: str = Field(min_length=3, max_length=50)
    merchant_id: str
    subtotal: float = Field(ge=0)


class VoucherValidationResponse(BaseDTO):
    """Voucher validation result."""

    code: str
    discount_amount: float
    subtotal: float
    total_after_discount: float
    is_valid: bool
    message: str
