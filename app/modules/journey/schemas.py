# =============================================================================
# Journey Module - Pydantic Schemas
# =============================================================================

from datetime import datetime
from typing import Any

from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin


class AbandonedCartProperties(BaseDTO):
    cart_value: float = Field(default=0.0, ge=0)
    currency: str = Field(default="VND", max_length=10)
    restaurant_open: bool = True
    items_available: bool = True
    merchant_id: str | None = None
    merchant_name: str | None = Field(default=None, max_length=100)
    deep_link: str | None = None
    item_count: int = Field(default=1, ge=0)
    anonymous_id: str | None = None


class AbandonedCartActivityUpsert(BaseDTO):
    cart_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=36)
    merchant_id: str | None = None
    merchant_name: str | None = Field(default=None, max_length=100)
    cart_value: float = Field(default=0.0, ge=0)
    currency: str = Field(default="VND", max_length=10)
    item_count: int = Field(default=1, ge=0)
    restaurant_open: bool = True
    items_available: bool = True
    deep_link: str | None = None
    payload_snapshot: dict[str, Any] | None = None
    last_activity_at: datetime | None = None
    is_active: bool = True


class AuthenticatedAbandonedCartActivityUpsert(BaseDTO):
    cart_id: str = Field(min_length=1, max_length=64)
    merchant_id: str | None = None
    merchant_name: str | None = Field(default=None, max_length=100)
    cart_value: float = Field(default=0.0, ge=0)
    currency: str = Field(default="VND", max_length=10)
    item_count: int = Field(default=1, ge=0)
    restaurant_open: bool = True
    items_available: bool = True
    deep_link: str | None = None
    payload_snapshot: dict[str, Any] | None = None
    last_activity_at: datetime | None = None
    is_active: bool = True


class AbandonedCartActivityResponse(BaseDTO, TimestampMixin):
    id: str
    cart_id: str
    user_id: str
    merchant_id: str | None = None
    merchant_name: str | None = None
    cart_value: float
    currency: str
    item_count: int
    restaurant_open: bool
    items_available: bool
    status: str
    last_activity_at: datetime
    abandoned_at: datetime | None = None
    webhook_triggered_at: datetime | None = None
    recovered_at: datetime | None = None
    recovery_order_id: str | None = None


class AbandonedCartStatusRequest(BaseDTO):
    journey: str = "abandoned_cart_recovery"
    trigger_event: str = "cart_abandoned"
    event_time: datetime | None = None
    user_id: str = Field(min_length=1, max_length=36)
    cart_id: str = Field(min_length=1, max_length=64)
    dedupe_key: str | None = None
    check_phase: str = Field(default="initial", max_length=20)
    properties: AbandonedCartProperties | None = None


class AbandonedCartStatusResponse(BaseDTO):
    cart_id: str
    user_id: str
    journey: str
    cart_status: str
    has_converted: bool
    recovery_order_id: str | None = None
    abandoned_at: datetime | None = None
    webhook_triggered_at: datetime | None = None
    cart_value: float = 0.0
    offer_eligible: bool = False


class CreateFreeshipOfferRequest(BaseDTO):
    journey: str = "abandoned_cart_recovery"
    user_id: str = Field(min_length=1, max_length=36)
    cart_id: str = Field(min_length=1, max_length=64)
    cart_value: float = Field(ge=0)
    coupon_type: str = Field(default="freeship", max_length=30)
    max_discount: float = Field(default=30000, ge=0)
    min_cart_value: float = Field(default=150000, ge=0)
    expires_in_hours: int = Field(default=24, ge=1, le=168)
    reason: str = Field(default="abandoned_cart_recovery", max_length=100)


class JourneyOfferResponse(BaseDTO, TimestampMixin):
    id: str
    user_id: str
    journey_type: str
    source_cart_id: str
    offer_type: str
    code: str
    max_discount: float
    min_cart_value: float
    status: str
    expires_at: datetime
    consumed_at: datetime | None = None
    is_existing: bool = False
