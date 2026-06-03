# =============================================================================
# Marketing Module - Pydantic Schemas
# =============================================================================

from datetime import datetime

from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin


# =============================================================================
# Campaign Schemas
# =============================================================================

class CampaignBase(BaseDTO):
    """Base campaign fields."""

    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    campaign_type: str = Field(default="DISCOUNT", pattern="^(DISCOUNT|FREE_DELIVERY|BUNDLE|LOYALTY)$")
    discount_type: str = Field(default="PERCENTAGE", pattern="^(PERCENTAGE|FIXED_AMOUNT)$")
    discount_value: float = Field(ge=0)
    max_discount: float | None = None
    min_order_value: float = Field(default=0, ge=0)
    target_audience: str = Field(default="ALL", pattern="^(ALL|NEW_USERS|RETURNING_USERS|VIP)$")
    start_date: datetime
    end_date: datetime
    budget: float | None = None
    is_featured: bool = False


class CampaignCreate(CampaignBase):
    """Create campaign request."""

    voucher_code: str | None = Field(default=None, max_length=50)
    auto_generate_vouchers: bool = False
    max_vouchers: int | None = Field(default=None, ge=1)


class CampaignUpdate(BaseDTO):
    """Update campaign request."""

    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    campaign_type: str | None = None
    discount_type: str | None = None
    discount_value: float | None = None
    max_discount: float | None = None
    min_order_value: float | None = None
    target_audience: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    budget: float | None = None
    is_featured: bool | None = None


class CampaignResponse(CampaignBase, TimestampMixin):
    """Campaign response."""

    id: str
    voucher_code: str | None
    auto_generate_vouchers: bool
    max_vouchers: int | None
    used_vouchers: int
    status: str
    spent: float
    total_orders: int
    total_revenue: float
    created_by: str | None


class CampaignListResponse(BaseDTO):
    """Paginated campaign list."""

    items: list[CampaignResponse]
    total: int


class CampaignStatsResponse(BaseDTO):
    """Campaign statistics."""

    total_campaigns: int
    active_campaigns: int
    scheduled_campaigns: int
    ended_campaigns: int
    total_budget: float
    total_spent: float
    total_revenue_generated: float
    total_orders: int
    total_vouchers_used: int


class CampaignUpdateStatus(BaseDTO):
    """Update campaign status."""

    status: str = Field(pattern="^(DRAFT|SCHEDULED|ACTIVE|PAUSED|ENDED|CANCELLED)$")
