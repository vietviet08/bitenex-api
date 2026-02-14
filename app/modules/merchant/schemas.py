# =============================================================================
# Merchant Module - Pydantic Schemas
# =============================================================================

from typing import Literal

from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin
from app.shared.enums import MerchantStatus


class MerchantBase(BaseDTO):
    """Base merchant fields."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    min_order_amount: float = Field(default=0.0, ge=0)
    delivery_fee: float = Field(default=0.0, ge=0)
    estimated_prep_time: int = Field(default=30, ge=1, le=300)


class MerchantCreate(MerchantBase):
    """Create merchant request."""

    user_id: str
    latitude: float | None = None
    longitude: float | None = None


class MerchantUpdate(BaseDTO):
    """Update merchant request."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    address: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    logo_url: str | None = None
    cover_image_url: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    min_order_amount: float | None = Field(default=None, ge=0)
    delivery_fee: float | None = Field(default=None, ge=0)
    estimated_prep_time: int | None = Field(default=None, ge=1, le=300)


class MerchantResponse(MerchantBase, TimestampMixin):
    """Merchant response."""

    id: str
    user_id: str
    slug: str
    logo_url: str | None = None
    cover_image_url: str | None = None
    status: MerchantStatus
    is_featured: bool
    latitude: float | None = None
    longitude: float | None = None
    average_rating: float
    total_orders: int
    is_profile_complete: bool = False


class MerchantListResponse(BaseDTO):
    """Paginated merchant list."""

    items: list[MerchantResponse]
    total: int


class AdminMerchantResponse(MerchantResponse):
    """Merchant response enriched for admin management."""

    owner_email: str | None = None
    owner_full_name: str | None = None


class AdminMerchantListResponse(BaseDTO):
    """Paginated merchant list for admins."""

    items: list[AdminMerchantResponse]
    total: int


# Menu Item schemas
class MenuItemBase(BaseDTO):
    """Base menu item fields."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    price: float = Field(gt=0)
    category: str | None = Field(default=None, max_length=50)
    is_available: bool = True


class MenuItemCreate(MenuItemBase):
    """Create menu item request."""

    pass


class MenuItemUpdate(BaseDTO):
    """Update menu item request."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, max_length=50)
    is_available: bool | None = None


class MenuItemResponse(MenuItemBase, TimestampMixin):
    """Menu item response."""

    id: str
    merchant_id: str
    image_url: str | None = None
    is_featured: bool


class MenuListResponse(BaseDTO):
    """Paginated menu list response."""

    items: list[MenuItemResponse]
    total: int
    page: int
    per_page: int


class AdminMerchantDetailResponse(BaseDTO):
    """Admin merchant detail response with merchant profile and menu context."""

    merchant: AdminMerchantResponse
    menu: MenuListResponse


# =============================================================================
# Menu Item Option Group & Option schemas
# =============================================================================


class OptionCreate(BaseDTO):
    """Create option request."""

    name: str = Field(min_length=1, max_length=100)
    price_delta: float = Field(default=0.0)
    sort_order: int = Field(default=0, ge=0)
    is_available: bool = True


class OptionUpdate(BaseDTO):
    """Update option request."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    price_delta: float | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_available: bool | None = None


class OptionResponse(BaseDTO, TimestampMixin):
    """Option response."""

    id: str
    option_group_id: str
    name: str
    price_delta: float
    sort_order: int
    is_available: bool


class OptionGroupCreate(BaseDTO):
    """Create option group request."""

    name: str = Field(min_length=1, max_length=100)
    selection_type: Literal["single", "multiple"] = "single"
    sort_order: int = Field(default=0, ge=0)
    is_required: bool = False


class OptionGroupUpdate(BaseDTO):
    """Update option group request."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    selection_type: Literal["single", "multiple"] | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_required: bool | None = None


class OptionGroupResponse(BaseDTO, TimestampMixin):
    """Option group response with nested options."""

    id: str
    menu_item_id: str
    name: str
    selection_type: str
    sort_order: int
    is_required: bool
    options: list[OptionResponse] = []


class MenuItemDetailResponse(MenuItemBase, TimestampMixin):
    """Menu item detail response with nested option groups."""

    id: str
    merchant_id: str
    image_url: str | None = None
    is_featured: bool
    option_groups: list[OptionGroupResponse] = []
