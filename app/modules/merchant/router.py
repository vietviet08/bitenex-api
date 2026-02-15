# =============================================================================
# Merchant Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdmin, RequireMerchant
from app.modules.merchant.schemas import (
    AdminMerchantDetailResponse,
    AdminMerchantListResponse,
    MenuItemCreate,
    MenuItemDetailResponse,
    MenuListResponse,
    MenuItemResponse,
    MenuItemUpdate,
    MerchantListResponse,
    MerchantResponse,
    MerchantUpdate,
    OptionCreate,
    OptionGroupCreate,
    OptionGroupResponse,
    OptionGroupUpdate,
    OptionResponse,
    OptionUpdate,
)
from app.modules.merchant.service import MerchantService
from app.shared.dto import MessageResponse
from app.shared.enums import MerchantStatus

router = APIRouter(
    prefix="/merchants",
    tags=["Merchants"],
)


def get_merchant_service(
    db: AsyncSession = Depends(get_db),
) -> MerchantService:
    return MerchantService(db)


# =============================================================================
# Public Endpoints
# =============================================================================
@router.get(
    "",
    response_model=MerchantListResponse,
    summary="List merchants",
)
async def list_merchants(
    city: str | None = None,
    category: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantListResponse:
    """List merchants with optional filters."""
    items, total = await service.list_merchants(city, category, page, per_page)
    return MerchantListResponse(items=items, total=total)


@router.get(
    "/search",
    response_model=list[MerchantResponse],
    summary="Search merchants",
)
async def search_merchants(
    q: str = Query(..., min_length=2),
    latitude: float | None = None,
    longitude: float | None = None,
    service: MerchantService = Depends(get_merchant_service),
) -> list[MerchantResponse]:
    """Search merchants by name."""
    return await service.search_merchants(q, latitude, longitude)


@router.get(
    "/slug/{slug}",
    response_model=MerchantResponse,
    summary="Get merchant by slug",
)
async def get_merchant_by_slug(
    slug: str,
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantResponse:
    """Get merchant by slug."""
    return await service.get_merchant_by_slug(slug)


# =============================================================================
# Merchant Owner Endpoints
# =============================================================================
@router.get(
    "/owner/profile",
    response_model=MerchantResponse,
    summary="Get my merchant profile",
    dependencies=[RequireMerchant],
)
async def get_my_merchant(
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantResponse:
    """Get current merchant's profile."""
    return await service.get_merchant_by_user_id(user.user_id)


@router.patch(
    "/owner/profile",
    response_model=MerchantResponse,
    summary="Update my merchant profile",
    dependencies=[RequireMerchant],
)
async def update_my_merchant(
    data: MerchantUpdate,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantResponse:
    """Update current merchant's profile."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    return await service.update_merchant(merchant.id, data)


@router.get(
    "/owner/menu/list",
    response_model=MenuListResponse,
    summary="List my menu items",
    dependencies=[RequireMerchant],
)
async def list_owner_menu(
    user: CurrentUser,
    category: str | None = Query(default=None),
    available_only: bool | None = Query(default=None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: MerchantService = Depends(get_merchant_service),
) -> MenuListResponse:
    """List current merchant's menu with pagination and filters."""
    return await service.get_owner_menu(
        user.user_id,
        category=category,
        is_available=available_only,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/owner/menu",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add menu item",
    dependencies=[RequireMerchant],
)
async def add_menu_item(
    data: MenuItemCreate,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> MenuItemResponse:
    """Add item to menu."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    return await service.add_menu_item(merchant.id, data)


@router.patch(
    "/owner/menu/{item_id}",
    response_model=MenuItemResponse,
    summary="Update menu item",
    dependencies=[RequireMerchant],
)
async def update_menu_item(
    item_id: str,
    data: MenuItemUpdate,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> MenuItemResponse:
    """Update menu item."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    return await service.update_menu_item(
        item_id,
        data,
        actor_merchant_id=merchant.id,
    )


@router.delete(
    "/owner/menu/{item_id}",
    response_model=MessageResponse,
    summary="Delete menu item",
    dependencies=[RequireMerchant],
)
async def delete_menu_item(
    item_id: str,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> MessageResponse:
    """Delete menu item."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    await service.delete_menu_item(
        item_id,
        actor_merchant_id=merchant.id,
    )
    return MessageResponse(message="Menu item deleted")


# =============================================================================
# Merchant Owner - Option Group Endpoints
# =============================================================================
@router.post(
    "/owner/menu/{item_id}/option-groups",
    response_model=OptionGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create option group",
    dependencies=[RequireMerchant],
)
async def create_option_group(
    item_id: str,
    data: OptionGroupCreate,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> OptionGroupResponse:
    """Create an option group for a menu item."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    return await service.create_option_group(
        item_id, data, actor_merchant_id=merchant.id
    )


@router.get(
    "/owner/menu/{item_id}/option-groups",
    response_model=list[OptionGroupResponse],
    summary="List option groups",
    dependencies=[RequireMerchant],
)
async def list_option_groups(
    item_id: str,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> list[OptionGroupResponse]:
    """List option groups with nested options for a menu item."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    return await service.list_option_groups(item_id, actor_merchant_id=merchant.id)


@router.patch(
    "/owner/menu/{item_id}/option-groups/{group_id}",
    response_model=OptionGroupResponse,
    summary="Update option group",
    dependencies=[RequireMerchant],
)
async def update_option_group(
    item_id: str,
    group_id: str,
    data: OptionGroupUpdate,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> OptionGroupResponse:
    """Update an option group."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    return await service.update_option_group(
        item_id, group_id, data, actor_merchant_id=merchant.id
    )


@router.delete(
    "/owner/menu/{item_id}/option-groups/{group_id}",
    response_model=MessageResponse,
    summary="Delete option group",
    dependencies=[RequireMerchant],
)
async def delete_option_group(
    item_id: str,
    group_id: str,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> MessageResponse:
    """Delete an option group and its options."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    await service.delete_option_group(item_id, group_id, actor_merchant_id=merchant.id)
    return MessageResponse(message="Option group deleted")


# =============================================================================
# Merchant Owner - Option Endpoints (within a group)
# =============================================================================
@router.post(
    "/owner/menu/{item_id}/option-groups/{group_id}/options",
    response_model=OptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create option",
    dependencies=[RequireMerchant],
)
async def create_option(
    item_id: str,
    group_id: str,
    data: OptionCreate,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> OptionResponse:
    """Create an option within an option group."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    return await service.create_option(
        item_id, group_id, data, actor_merchant_id=merchant.id
    )


@router.patch(
    "/owner/menu/{item_id}/option-groups/{group_id}/options/{option_id}",
    response_model=OptionResponse,
    summary="Update option",
    dependencies=[RequireMerchant],
)
async def update_option(
    item_id: str,
    group_id: str,
    option_id: str,
    data: OptionUpdate,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> OptionResponse:
    """Update an option."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    return await service.update_option(
        item_id, group_id, option_id, data, actor_merchant_id=merchant.id
    )


@router.delete(
    "/owner/menu/{item_id}/option-groups/{group_id}/options/{option_id}",
    response_model=MessageResponse,
    summary="Delete option",
    dependencies=[RequireMerchant],
)
async def delete_option(
    item_id: str,
    group_id: str,
    option_id: str,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> MessageResponse:
    """Delete an option."""
    merchant = await service.get_merchant_by_user_id(user.user_id)
    await service.delete_option(
        item_id, group_id, option_id, actor_merchant_id=merchant.id
    )
    return MessageResponse(message="Option deleted")


# =============================================================================
# Admin Endpoints
# =============================================================================
@router.get(
    "/admin/list",
    response_model=AdminMerchantListResponse,
    summary="Admin list merchants",
    dependencies=[RequireAdmin],
)
async def admin_list_merchants(
    status_filter: MerchantStatus | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: MerchantService = Depends(get_merchant_service),
) -> AdminMerchantListResponse:
    """List merchants for admin management, including pending merchants."""
    items, total = await service.list_admin_merchants(
        status=status_filter,
        page=page,
        per_page=per_page,
    )
    return AdminMerchantListResponse(items=items, total=total)


@router.get(
    "/admin/{merchant_id}",
    response_model=AdminMerchantDetailResponse,
    summary="Admin merchant detail",
    dependencies=[RequireAdmin],
)
async def admin_get_merchant_detail(
    merchant_id: str,
    category: str | None = Query(default=None),
    available_only: bool | None = Query(default=None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: MerchantService = Depends(get_merchant_service),
) -> AdminMerchantDetailResponse:
    """Get merchant detail with menu context for admin dashboards."""
    return await service.get_admin_merchant_detail(
        merchant_id,
        category=category,
        is_available=available_only,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/{merchant_id}/approve",
    response_model=MerchantResponse,
    summary="Approve merchant",
    dependencies=[RequireAdmin],
)
async def approve_merchant(
    merchant_id: str,
    user: CurrentUser,
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantResponse:
    """Approve a merchant application. Admin only."""
    return await service.approve_merchant(merchant_id, approved_by=user.user_id)


# =============================================================================
# Public Parameterized Endpoints (MUST be last – catch-all path params)
# =============================================================================
@router.get(
    "/{merchant_id}",
    response_model=MerchantResponse,
    summary="Get merchant",
)
async def get_merchant(
    merchant_id: str,
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantResponse:
    """Get merchant by ID."""
    return await service.get_merchant_by_id(merchant_id)


@router.get(
    "/{merchant_id}/menu",
    response_model=list[MenuItemResponse],
    summary="Get menu",
)
async def get_menu(
    merchant_id: str,
    category: str | None = Query(default=None),
    available_only: bool | None = Query(default=None),
    service: MerchantService = Depends(get_merchant_service),
) -> list[MenuItemResponse]:
    """Get merchant's menu."""
    return await service.get_menu(
        merchant_id,
        category=category,
        is_available=available_only,
    )


@router.get(
    "/{merchant_id}/menu/{item_id}",
    response_model=MenuItemDetailResponse,
    summary="Get menu item detail",
)
async def get_menu_item_detail(
    merchant_id: str,
    item_id: str,
    service: MerchantService = Depends(get_merchant_service),
) -> MenuItemDetailResponse:
    """Get a single menu item with option groups and options."""
    return await service.get_menu_item_detail(merchant_id, item_id)
