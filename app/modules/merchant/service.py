# =============================================================================
# Merchant Module - Service Layer
# =============================================================================

import re

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import MerchantApprovedEvent, emit_event
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.modules.merchant.models import MenuItem, Merchant
from app.modules.merchant.schemas import (
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    MerchantCreate,
    MerchantResponse,
    MerchantUpdate,
)
from app.shared.enums import MerchantStatus


class MerchantService:
    """
    Merchant management service.
    Handles merchant profiles and menu management.
    """

    _MERCHANT_NOT_FOUND = "Merchant not found"

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _to_merchant_response(merchant: Merchant) -> MerchantResponse:
        return MerchantResponse.model_validate(merchant)

    @staticmethod
    def _to_menu_item_response(item: MenuItem) -> MenuItemResponse:
        return MenuItemResponse.model_validate(item)

    async def _get_merchant_model_by_id(
        self,
        merchant_id: str,
        *,
        active_only: bool = False,
    ) -> Merchant:
        filters = [
            Merchant.id == merchant_id,
            Merchant.is_deleted == False,
        ]
        if active_only:
            filters.append(Merchant.status == MerchantStatus.ACTIVE.value)

        result = await self.db.execute(select(Merchant).where(*filters))
        merchant = result.scalar_one_or_none()
        if not merchant:
            raise NotFoundError(message=self._MERCHANT_NOT_FOUND)
        return merchant

    async def _get_merchant_model_by_slug(
        self,
        slug: str,
        *,
        active_only: bool = False,
    ) -> Merchant:
        filters = [
            Merchant.slug == slug,
            Merchant.is_deleted == False,
        ]
        if active_only:
            filters.append(Merchant.status == MerchantStatus.ACTIVE.value)

        result = await self.db.execute(select(Merchant).where(*filters))
        merchant = result.scalar_one_or_none()
        if not merchant:
            raise NotFoundError(message=self._MERCHANT_NOT_FOUND)
        return merchant

    async def _get_merchant_model_by_user_id(self, user_id: str) -> Merchant:
        result = await self.db.execute(
            select(Merchant).where(
                Merchant.user_id == user_id,
                Merchant.is_deleted == False,
            )
        )
        merchant = result.scalar_one_or_none()
        if not merchant:
            raise NotFoundError(message=self._MERCHANT_NOT_FOUND)
        return merchant

    async def _get_menu_item_model(
        self,
        item_id: str,
        *,
        include_deleted: bool = False,
    ) -> MenuItem:
        filters = [MenuItem.id == item_id]
        if not include_deleted:
            filters.append(MenuItem.is_deleted == False)

        result = await self.db.execute(select(MenuItem).where(*filters))
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError(message="Menu item not found")
        return item

    async def _generate_unique_slug(self, name: str) -> str:
        base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not base_slug:
            base_slug = "merchant"

        candidate = base_slug
        suffix = 1
        while True:
            result = await self.db.execute(
                select(Merchant.id).where(
                    Merchant.slug == candidate,
                    Merchant.is_deleted == False,
                )
            )
            exists = result.scalar_one_or_none()
            if not exists:
                return candidate
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

    async def get_merchant_by_id(self, merchant_id: str) -> MerchantResponse:
        """Get merchant by ID."""
        merchant = await self._get_merchant_model_by_id(merchant_id, active_only=True)
        return self._to_merchant_response(merchant)

    async def get_merchant_by_slug(self, slug: str) -> MerchantResponse:
        """Get merchant by slug."""
        merchant = await self._get_merchant_model_by_slug(slug, active_only=True)
        return self._to_merchant_response(merchant)

    async def get_merchant_by_user_id(self, user_id: str) -> MerchantResponse:
        """Get merchant by owner user ID."""
        merchant = await self._get_merchant_model_by_user_id(user_id)
        return self._to_merchant_response(merchant)

    async def create_merchant(self, data: MerchantCreate) -> MerchantResponse:
        """Create merchant profile."""
        result = await self.db.execute(
            select(Merchant).where(
                Merchant.user_id == data.user_id,
                Merchant.is_deleted == False,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ConflictError(message="Merchant profile already exists for this user")

        merchant = Merchant(
            user_id=data.user_id,
            name=data.name,
            slug=await self._generate_unique_slug(data.name),
            description=data.description,
            address=data.address,
            city=data.city,
            phone=data.phone,
            min_order_amount=data.min_order_amount,
            delivery_fee=data.delivery_fee,
            estimated_prep_time=data.estimated_prep_time,
            latitude=data.latitude,
            longitude=data.longitude,
            status=MerchantStatus.PENDING.value,
        )

        self.db.add(merchant)
        await self.db.flush()
        await self.db.refresh(merchant)

        return self._to_merchant_response(merchant)

    async def update_merchant(
        self,
        merchant_id: str,
        data: MerchantUpdate,
    ) -> MerchantResponse:
        """Update merchant profile."""
        merchant = await self._get_merchant_model_by_id(merchant_id, active_only=False)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(merchant, field, value)

        await self.db.flush()
        await self.db.refresh(merchant)
        return self._to_merchant_response(merchant)

    async def list_merchants(
        self,
        city: str | None = None,
        category: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[MerchantResponse], int]:
        """List merchants with filters and pagination."""
        filters = [
            Merchant.is_deleted == False,
            Merchant.status == MerchantStatus.ACTIVE.value,
        ]

        if city:
            filters.append(Merchant.city.ilike(f"%{city.strip()}%"))

        merchant_query = select(Merchant).where(*filters)
        count_query = select(func.count(Merchant.id)).where(*filters)

        if category:
            category_filter = MenuItem.category.ilike(f"%{category.strip()}%")
            join_condition = and_(
                MenuItem.merchant_id == Merchant.id,
                MenuItem.is_deleted == False,
            )
            merchant_query = (
                merchant_query.join(MenuItem, join_condition)
                .where(category_filter)
                .distinct()
            )
            count_query = (
                select(func.count(func.distinct(Merchant.id)))
                .select_from(Merchant)
                .join(MenuItem, join_condition)
                .where(*filters, category_filter)
            )

        merchant_query = (
            merchant_query.order_by(Merchant.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        merchants_result = await self.db.execute(merchant_query)
        merchants = merchants_result.scalars().all()

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        return [self._to_merchant_response(m) for m in merchants], total

    async def search_merchants(
        self,
        query: str,
        _latitude: float | None = None,
        _longitude: float | None = None,
    ) -> list[MerchantResponse]:
        """Search merchants by name."""
        term = query.strip()
        if not term:
            return []

        result = await self.db.execute(
            select(Merchant)
            .where(
                Merchant.is_deleted == False,
                Merchant.status == MerchantStatus.ACTIVE.value,
                Merchant.name.ilike(f"%{term}%"),
            )
            .order_by(
                Merchant.is_featured.desc(),
                Merchant.average_rating.desc(),
                Merchant.total_orders.desc(),
                Merchant.created_at.desc(),
            )
        )
        merchants = result.scalars().all()
        return [self._to_merchant_response(m) for m in merchants]

    async def approve_merchant(
        self,
        merchant_id: str,
        approved_by: str | None = None,
    ) -> MerchantResponse:
        """Approve merchant application."""
        merchant = await self._get_merchant_model_by_id(merchant_id, active_only=False)
        was_active = merchant.status == MerchantStatus.ACTIVE.value

        merchant.status = MerchantStatus.ACTIVE.value
        await self.db.flush()
        await self.db.refresh(merchant)

        if not was_active:
            # emit_event() is intentionally safe no-op when no handlers are registered.
            await emit_event(
                MerchantApprovedEvent(
                    merchant_id=merchant.id,
                    owner_user_id=merchant.user_id,
                    approved_by=approved_by or "",
                )
            )

        return self._to_merchant_response(merchant)

    # Menu management
    async def add_menu_item(
        self,
        merchant_id: str,
        data: MenuItemCreate,
    ) -> MenuItemResponse:
        """Add menu item."""
        await self._get_merchant_model_by_id(merchant_id, active_only=False)

        item = MenuItem(
            merchant_id=merchant_id,
            name=data.name,
            description=data.description,
            price=data.price,
            category=data.category,
            is_available=data.is_available,
        )

        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return self._to_menu_item_response(item)

    async def update_menu_item(
        self,
        item_id: str,
        data: MenuItemUpdate,
        actor_merchant_id: str | None = None,
    ) -> MenuItemResponse:
        """Update menu item."""
        item = await self._get_menu_item_model(item_id)

        if actor_merchant_id and item.merchant_id != actor_merchant_id:
            raise AuthorizationError(message="You can only update your own menu items")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        await self.db.flush()
        await self.db.refresh(item)
        return self._to_menu_item_response(item)

    async def delete_menu_item(
        self,
        item_id: str,
        actor_merchant_id: str | None = None,
    ) -> None:
        """Delete menu item."""
        item = await self._get_menu_item_model(item_id, include_deleted=True)

        if actor_merchant_id and item.merchant_id != actor_merchant_id:
            raise AuthorizationError(message="You can only delete your own menu items")

        if item.is_deleted:
            return

        item.soft_delete()
        await self.db.flush()

    async def get_menu(self, merchant_id: str) -> list[MenuItemResponse]:
        """Get merchant's menu."""
        await self._get_merchant_model_by_id(merchant_id, active_only=True)

        result = await self.db.execute(
            select(MenuItem)
            .where(
                MenuItem.merchant_id == merchant_id,
                MenuItem.is_deleted == False,
            )
            .order_by(MenuItem.created_at.desc())
        )
        items = result.scalars().all()
        return [self._to_menu_item_response(i) for i in items]
