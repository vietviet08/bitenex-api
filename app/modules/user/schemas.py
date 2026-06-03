# =============================================================================
# User Module - Pydantic Schemas
# =============================================================================


from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin
from app.shared.enums import Role


class UserBase(BaseDTO):
    """Base user fields."""

    email: str = Field(pattern=r"^.+@.+$", max_length=255)
    full_name: str = Field(min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)


class UserCreate(UserBase):
    """Create user request."""

    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.USER


class UserUpdate(BaseDTO):
    """Update user request."""

    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    avatar_url: str | None = None


class AdminUserUpdate(BaseDTO):
    """Admin update user request — can change role and active status."""

    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    role: Role | None = None
    is_active: bool | None = None
    is_verified: bool | None = None


class UserResponse(UserBase, TimestampMixin):
    """User response."""

    id: str
    role: Role
    is_active: bool
    is_verified: bool
    avatar_url: str | None = None


class UserListResponse(BaseDTO):
    """Paginated user list."""

    items: list[UserResponse]
    total: int


class AdminUserListResponse(BaseDTO):
    """Paginated admin user list."""

    items: list[UserResponse]
    total: int


class AddressBase(BaseDTO):
    """Base address fields."""

    label: str = Field(max_length=50)
    address_line1: str = Field(max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    latitude: float | None = None
    longitude: float | None = None
    is_default: bool = False


class AddressCreate(AddressBase):
    """Create address request."""

    pass


class AddressResponse(AddressBase, TimestampMixin):
    """Address response."""

    id: str
    user_id: str


# =============================================================================
# Favorites Schemas
# =============================================================================


class FavoriteMerchantResponse(BaseDTO):
    """Merchant data returned in the user favorites list."""

    id: str
    merchant_id: str
    name: str
    logo_url: str | None = None
    cover_image_url: str | None = None
    average_rating: float
    delivery_fee: float
    estimated_prep_time: int
    address: str
    city: str


class FavoriteListResponse(BaseDTO):
    """Paginated list of favorite merchants."""

    items: list[FavoriteMerchantResponse]
    total: int
