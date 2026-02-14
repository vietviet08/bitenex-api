# =============================================================================
# Merchant Module - Pydantic Schemas
# =============================================================================

from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin
from app.shared.enums import MerchantStatus


class MerchantBase(BaseDTO):
    """Base merchant fields."""

    name: str = Field(max_length=100)
    description: str | None = None
    address: str = Field(max_length=255)
    city: str = Field(max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    min_order_amount: float = 0.0
    delivery_fee: float = 0.0
    estimated_prep_time: int = 30


class MerchantCreate(MerchantBase):
    """Create merchant request."""

    user_id: str
    latitude: float | None = None
    longitude: float | None = None


class MerchantUpdate(BaseDTO):
    """Update merchant request."""

    name: str | None = None
    description: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    logo_url: str | None = None
    cover_image_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    min_order_amount: float | None = None
    delivery_fee: float | None = None
    estimated_prep_time: int | None = None


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

    name: str = Field(max_length=100)
    description: str | None = None
    price: float = Field(gt=0)
    category: str | None = Field(default=None, max_length=50)
    is_available: bool = True


class MenuItemCreate(MenuItemBase):
    """Create menu item request."""

    pass


class MenuItemUpdate(BaseDTO):
    """Update menu item request."""

    name: str | None = None
    description: str | None = None
    price: float | None = None
    category: str | None = None
    is_available: bool | None = None


class MenuItemResponse(MenuItemBase, TimestampMixin):
    """Menu item response."""

    id: str
    merchant_id: str
    image_url: str | None = None
    is_featured: bool
