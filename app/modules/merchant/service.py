# =============================================================================
# Merchant Module - Service Layer
# =============================================================================

import re

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import MerchantApprovedEvent, emit_event
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.modules.merchant.models import (
    MenuItem,
    MenuItemOption,
    MenuItemOptionGroup,
    Merchant,
)
from app.modules.merchant.schemas import (
    AdminMerchantDetailResponse,
    AdminMerchantResponse,
    MenuItemCreate,
    MenuItemDetailResponse,
    MenuListResponse,
    MenuItemResponse,
    MenuItemUpdate,
    MerchantCreate,
    MerchantResponse,
    MerchantUpdate,
    OptionCreate,
    OptionGroupCreate,
    OptionGroupResponse,
    OptionGroupUpdate,
    OptionResponse,
    OptionUpdate,
)
from app.modules.user.models import User
from app.shared.enums import MerchantStatus


class MerchantService:
    """
    Merchant management service.
    Handles merchant profiles and menu management.
    """

    _MERCHANT_NOT_FOUND = "Merchant not found"
    _OPTION_NOT_FOUND = "Option not found"
    _OPTION_GROUP_NOT_FOUND = "Option group not found"

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def is_profile_complete(merchant: Merchant) -> bool:
        """Evaluate merchant profile completeness for onboarding gates."""
        required_text = [
            merchant.name,
            merchant.description,
            merchant.address,
            merchant.city,
            merchant.phone,
        ]
        has_required_text = all(
            value is not None and str(value).strip() for value in required_text
        )
        has_coordinates = (
            merchant.latitude is not None and merchant.longitude is not None
        )
        has_business_settings = (
            merchant.min_order_amount is not None
            and merchant.delivery_fee is not None
            and merchant.estimated_prep_time is not None
        )
        return has_required_text and has_coordinates and has_business_settings

    @classmethod
    def _to_merchant_response(cls, merchant: Merchant) -> MerchantResponse:
        response = MerchantResponse.model_validate(merchant)
        response.is_profile_complete = cls.is_profile_complete(merchant)
        return response

    @classmethod
    def _to_admin_merchant_response(
        cls,
        merchant: Merchant,
        owner_email: str | None = None,
        owner_full_name: str | None = None,
    ) -> AdminMerchantResponse:
        base = cls._to_merchant_response(merchant)
        return AdminMerchantResponse(
            **base.model_dump(),
            owner_email=owner_email,
            owner_full_name=owner_full_name,
        )

    @staticmethod
    def _to_menu_item_response(item: MenuItem) -> MenuItemResponse:
        return MenuItemResponse.model_validate(item)

    @staticmethod
    def _raise_field_validation_error(details: dict[str, str]) -> None:
        normalized = {
            field: [{"type": "value_error", "message": message}]
            for field, message in details.items()
            if message
        }
        if normalized:
            raise ValidationError(message="Validation failed", details=normalized)

    async def _get_merchant_model_by_id(
        self,
        merchant_id: str,
        *,
        active_only: bool = False,
    ) -> Merchant:
        filters = [
            Merchant.id == merchant_id,
            Merchant.is_deleted.is_(False),
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
            Merchant.is_deleted.is_(False),
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
                Merchant.is_deleted.is_(False),
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
            filters.append(MenuItem.is_deleted.is_(False))

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
                    Merchant.is_deleted.is_(False),
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
                Merchant.is_deleted.is_(False),
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
        self._raise_field_validation_error(
            {
                "latitude": (
                    "Latitude must be between -90 and 90"
                    if data.latitude is not None and not -90 <= data.latitude <= 90
                    else ""
                ),
                "longitude": (
                    "Longitude must be between -180 and 180"
                    if data.longitude is not None and not -180 <= data.longitude <= 180
                    else ""
                ),
                "min_order_amount": (
                    "Minimum order amount must be >= 0"
                    if data.min_order_amount is not None and data.min_order_amount < 0
                    else ""
                ),
                "delivery_fee": (
                    "Delivery fee must be >= 0"
                    if data.delivery_fee is not None and data.delivery_fee < 0
                    else ""
                ),
                "estimated_prep_time": (
                    "Estimated prep time must be between 1 and 300 minutes"
                    if data.estimated_prep_time is not None
                    and not 1 <= data.estimated_prep_time <= 300
                    else ""
                ),
            }
        )
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
            Merchant.is_deleted.is_(False),
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
                MenuItem.is_deleted.is_(False),
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
                Merchant.is_deleted.is_(False),
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

    async def list_admin_merchants(
        self,
        *,
        status: MerchantStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[AdminMerchantResponse], int]:
        """
        List merchants for admin management, including owner metadata.
        """
        query = (
            select(Merchant, User.email, User.full_name)
            .select_from(Merchant)
            .join(
                User,
                and_(User.id == Merchant.user_id, User.is_deleted.is_(False)),
                isouter=True,
            )
            .where(Merchant.is_deleted.is_(False))
        )
        count_query = select(func.count(Merchant.id)).where(
            Merchant.is_deleted.is_(False)
        )

        if status:
            status_filter = Merchant.status == status.value
            query = query.where(status_filter)
            count_query = count_query.where(status_filter)

        query = (
            query.order_by(Merchant.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = (await self.db.execute(query)).all()

        total = (await self.db.execute(count_query)).scalar_one()

        items = [
            self._to_admin_merchant_response(
                merchant=row[0],
                owner_email=row[1],
                owner_full_name=row[2],
            )
            for row in rows
        ]
        return items, total

    async def list_menu_items(
        self,
        merchant_id: str,
        *,
        active_only_merchant: bool,
        category: str | None = None,
        is_available: bool | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[MenuItemResponse], int]:
        await self._get_merchant_model_by_id(
            merchant_id, active_only=active_only_merchant
        )

        filters = [
            MenuItem.merchant_id == merchant_id,
            MenuItem.is_deleted.is_(False),
        ]
        if category:
            filters.append(MenuItem.category.ilike(f"%{category.strip()}%"))
        if is_available is not None:
            filters.append(MenuItem.is_available == is_available)

        query = (
            select(MenuItem)
            .where(*filters)
            .order_by(MenuItem.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        count_query = select(func.count(MenuItem.id)).where(*filters)

        items = (await self.db.execute(query)).scalars().all()
        total = (await self.db.execute(count_query)).scalar_one()
        return [self._to_menu_item_response(item) for item in items], total

    async def get_owner_menu(
        self,
        owner_user_id: str,
        *,
        category: str | None = None,
        is_available: bool | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> MenuListResponse:
        merchant = await self._get_merchant_model_by_user_id(owner_user_id)
        items, total = await self.list_menu_items(
            merchant.id,
            active_only_merchant=False,
            category=category,
            is_available=is_available,
            page=page,
            per_page=per_page,
        )
        return MenuListResponse(items=items, total=total, page=page, per_page=per_page)

    async def get_admin_merchant_detail(
        self,
        merchant_id: str,
        *,
        category: str | None = None,
        is_available: bool | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> AdminMerchantDetailResponse:
        merchant = await self._get_merchant_model_by_id(merchant_id, active_only=False)
        owner_row = (
            await self.db.execute(
                select(User.email, User.full_name).where(
                    User.id == merchant.user_id,
                    User.is_deleted.is_(False),
                )
            )
        ).one_or_none()

        menu_items, total = await self.list_menu_items(
            merchant.id,
            active_only_merchant=False,
            category=category,
            is_available=is_available,
            page=page,
            per_page=per_page,
        )

        return AdminMerchantDetailResponse(
            merchant=self._to_admin_merchant_response(
                merchant=merchant,
                owner_email=owner_row[0] if owner_row else None,
                owner_full_name=owner_row[1] if owner_row else None,
            ),
            menu=MenuListResponse(
                items=menu_items,
                total=total,
                page=page,
                per_page=per_page,
            ),
        )

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

    async def get_menu(
        self,
        merchant_id: str,
        *,
        category: str | None = None,
        is_available: bool | None = None,
    ) -> list[MenuItemResponse]:
        """Get merchant's menu."""
        items, _ = await self.list_menu_items(
            merchant_id,
            active_only_merchant=True,
            category=category,
            is_available=is_available,
            page=1,
            per_page=500,
        )
        return items

    # =========================================================================
    # Menu Item Detail (public)
    # =========================================================================

    async def get_menu_item_detail(
        self,
        merchant_id: str,
        item_id: str,
    ) -> MenuItemDetailResponse:
        """Get a single menu item with its option groups and options."""
        await self._get_merchant_model_by_id(merchant_id, active_only=True)
        item = await self._get_menu_item_model(item_id)
        if item.merchant_id != merchant_id:
            raise NotFoundError(message="Menu item not found")

        option_groups = await self._get_option_groups_with_options(item_id)

        response = MenuItemDetailResponse.model_validate(item)
        response.option_groups = option_groups
        return response

    async def _get_option_groups_with_options(
        self,
        menu_item_id: str,
    ) -> list[OptionGroupResponse]:
        """Fetch option groups with nested options for a menu item."""
        groups_result = await self.db.execute(
            select(MenuItemOptionGroup)
            .where(
                MenuItemOptionGroup.menu_item_id == menu_item_id,
                MenuItemOptionGroup.is_deleted.is_(False),
            )
            .order_by(MenuItemOptionGroup.sort_order)
        )
        groups = groups_result.scalars().all()

        result: list[OptionGroupResponse] = []
        for group in groups:
            options_result = await self.db.execute(
                select(MenuItemOption)
                .where(
                    MenuItemOption.option_group_id == group.id,
                    MenuItemOption.is_deleted.is_(False),
                )
                .order_by(MenuItemOption.sort_order)
            )
            options = options_result.scalars().all()

            group_response = OptionGroupResponse.model_validate(group)
            group_response.options = [
                OptionResponse.model_validate(opt) for opt in options
            ]
            result.append(group_response)

        return result

    # =========================================================================
    # Option Group CRUD (merchant owner)
    # =========================================================================

    async def _verify_menu_item_ownership(
        self,
        item_id: str,
        actor_merchant_id: str,
    ) -> MenuItem:
        """Verify the menu item exists and belongs to the merchant."""
        item = await self._get_menu_item_model(item_id)
        if item.merchant_id != actor_merchant_id:
            raise AuthorizationError(
                message="You can only manage options for your own menu items"
            )
        return item

    async def _get_option_group_model(
        self,
        group_id: str,
    ) -> MenuItemOptionGroup:
        """Get option group by ID."""
        result = await self.db.execute(
            select(MenuItemOptionGroup).where(
                MenuItemOptionGroup.id == group_id,
                MenuItemOptionGroup.is_deleted.is_(False),
            )
        )
        group = result.scalar_one_or_none()
        if not group:
            raise NotFoundError(message=self._OPTION_GROUP_NOT_FOUND)
        return group

    async def _get_option_model(
        self,
        option_id: str,
    ) -> MenuItemOption:
        """Get option by ID."""
        result = await self.db.execute(
            select(MenuItemOption).where(
                MenuItemOption.id == option_id,
                MenuItemOption.is_deleted.is_(False),
            )
        )
        option = result.scalar_one_or_none()
        if not option:
            raise NotFoundError(message=self._OPTION_NOT_FOUND)
        return option

    async def create_option_group(
        self,
        item_id: str,
        data: OptionGroupCreate,
        actor_merchant_id: str,
    ) -> OptionGroupResponse:
        """Create an option group for a menu item."""
        await self._verify_menu_item_ownership(item_id, actor_merchant_id)

        group = MenuItemOptionGroup(
            menu_item_id=item_id,
            name=data.name,
            selection_type=data.selection_type,
            sort_order=data.sort_order,
            is_required=data.is_required,
        )
        self.db.add(group)
        await self.db.flush()
        await self.db.refresh(group)

        response = OptionGroupResponse.model_validate(group)
        response.options = []
        return response

    async def list_option_groups(
        self,
        item_id: str,
        actor_merchant_id: str,
    ) -> list[OptionGroupResponse]:
        """List option groups with options for a menu item (owner)."""
        await self._verify_menu_item_ownership(item_id, actor_merchant_id)
        return await self._get_option_groups_with_options(item_id)

    async def update_option_group(
        self,
        item_id: str,
        group_id: str,
        data: OptionGroupUpdate,
        actor_merchant_id: str,
    ) -> OptionGroupResponse:
        """Update an option group."""
        await self._verify_menu_item_ownership(item_id, actor_merchant_id)
        group = await self._get_option_group_model(group_id)

        if group.menu_item_id != item_id:
            raise NotFoundError(message=self._OPTION_GROUP_NOT_FOUND)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(group, field, value)

        await self.db.flush()
        await self.db.refresh(group)

        # Re-fetch with options
        options_result = await self.db.execute(
            select(MenuItemOption)
            .where(
                MenuItemOption.option_group_id == group.id,
                MenuItemOption.is_deleted.is_(False),
            )
            .order_by(MenuItemOption.sort_order)
        )
        options = options_result.scalars().all()

        response = OptionGroupResponse.model_validate(group)
        response.options = [OptionResponse.model_validate(opt) for opt in options]
        return response

    async def delete_option_group(
        self,
        item_id: str,
        group_id: str,
        actor_merchant_id: str,
    ) -> None:
        """Delete an option group and cascade to its options."""
        await self._verify_menu_item_ownership(item_id, actor_merchant_id)
        group = await self._get_option_group_model(group_id)

        if group.menu_item_id != item_id:
            raise NotFoundError(message=self._OPTION_GROUP_NOT_FOUND)

        # Soft-delete all options in the group
        options_result = await self.db.execute(
            select(MenuItemOption).where(
                MenuItemOption.option_group_id == group_id,
                MenuItemOption.is_deleted.is_(False),
            )
        )
        for option in options_result.scalars().all():
            option.soft_delete()

        group.soft_delete()
        await self.db.flush()

    # =========================================================================
    # Option CRUD (within a group)
    # =========================================================================

    async def create_option(
        self,
        item_id: str,
        group_id: str,
        data: OptionCreate,
        actor_merchant_id: str,
    ) -> OptionResponse:
        """Create an option within an option group."""
        await self._verify_menu_item_ownership(item_id, actor_merchant_id)
        group = await self._get_option_group_model(group_id)
        if group.menu_item_id != item_id:
            raise NotFoundError(message=self._OPTION_GROUP_NOT_FOUND)

        option = MenuItemOption(
            option_group_id=group_id,
            name=data.name,
            price_delta=data.price_delta,
            sort_order=data.sort_order,
            is_available=data.is_available,
        )
        self.db.add(option)
        await self.db.flush()
        await self.db.refresh(option)

        return OptionResponse.model_validate(option)

    async def update_option(
        self,
        item_id: str,
        group_id: str,
        option_id: str,
        data: OptionUpdate,
        actor_merchant_id: str,
    ) -> OptionResponse:
        """Update an option."""
        await self._verify_menu_item_ownership(item_id, actor_merchant_id)
        group = await self._get_option_group_model(group_id)
        if group.menu_item_id != item_id:
            raise NotFoundError(message=self._OPTION_GROUP_NOT_FOUND)

        option = await self._get_option_model(option_id)
        if option.option_group_id != group_id:
            raise NotFoundError(message=self._OPTION_NOT_FOUND)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(option, field, value)

        await self.db.flush()
        await self.db.refresh(option)

        return OptionResponse.model_validate(option)

    async def delete_option(
        self,
        item_id: str,
        group_id: str,
        option_id: str,
        actor_merchant_id: str,
    ) -> None:
        """Delete an option."""
        await self._verify_menu_item_ownership(item_id, actor_merchant_id)
        group = await self._get_option_group_model(group_id)
        if group.menu_item_id != item_id:
            raise NotFoundError(message=self._OPTION_GROUP_NOT_FOUND)

        option = await self._get_option_model(option_id)
        if option.option_group_id != group_id:
            raise NotFoundError(message=self._OPTION_NOT_FOUND)

        option.soft_delete()
        await self.db.flush()

