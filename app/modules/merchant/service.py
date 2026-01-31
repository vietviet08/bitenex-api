# =============================================================================
# Merchant Module - Service Layer
# =============================================================================

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.merchant.schemas import (
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    MerchantCreate,
    MerchantResponse,
    MerchantUpdate,
)


class MerchantService:
    """
    Merchant management service.
    Handles merchant profiles and menu management.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_merchant_by_id(self, merchant_id: str) -> MerchantResponse | None:
        """Get merchant by ID."""
        # TODO: Implement
        raise NotImplementedError()

    async def get_merchant_by_slug(self, slug: str) -> MerchantResponse | None:
        """Get merchant by slug."""
        # TODO: Implement
        raise NotImplementedError()

    async def get_merchant_by_user_id(self, user_id: str) -> MerchantResponse | None:
        """Get merchant by owner user ID."""
        # TODO: Implement
        raise NotImplementedError()

    async def create_merchant(self, data: MerchantCreate) -> MerchantResponse:
        """Create merchant profile."""
        # TODO: Implement
        raise NotImplementedError()

    async def update_merchant(
        self,
        merchant_id: str,
        data: MerchantUpdate,
    ) -> MerchantResponse:
        """Update merchant profile."""
        # TODO: Implement
        raise NotImplementedError()

    async def list_merchants(
        self,
        city: str | None = None,
        category: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[MerchantResponse], int]:
        """List merchants with filters and pagination."""
        # TODO: Implement
        raise NotImplementedError()

    async def search_merchants(
        self,
        query: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> list[MerchantResponse]:
        """Search merchants by name."""
        # TODO: Implement
        raise NotImplementedError()

    async def approve_merchant(self, merchant_id: str) -> MerchantResponse:
        """Approve merchant application."""
        # TODO: Implement
        raise NotImplementedError()

    # Menu management
    async def add_menu_item(
        self,
        merchant_id: str,
        data: MenuItemCreate,
    ) -> MenuItemResponse:
        """Add menu item."""
        # TODO: Implement
        raise NotImplementedError()

    async def update_menu_item(
        self,
        item_id: str,
        data: MenuItemUpdate,
    ) -> MenuItemResponse:
        """Update menu item."""
        # TODO: Implement
        raise NotImplementedError()

    async def delete_menu_item(self, item_id: str) -> None:
        """Delete menu item."""
        # TODO: Implement
        pass

    async def get_menu(self, merchant_id: str) -> list[MenuItemResponse]:
        """Get merchant's menu."""
        # TODO: Implement
        raise NotImplementedError()
