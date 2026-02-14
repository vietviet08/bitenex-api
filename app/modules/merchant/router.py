# =============================================================================
# Merchant Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdmin, RequireMerchant
from app.modules.merchant.schemas import (
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    MerchantListResponse,
    MerchantResponse,
    MerchantUpdate,
)
from app.modules.merchant.service import MerchantService
from app.shared.dto import MessageResponse

router = APIRouter(
    prefix="/merchants",
    tags=["Merchants"],
)


async def get_merchant_service(
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


@router.get(
    "/{merchant_id}/menu",
    response_model=list[MenuItemResponse],
    summary="Get menu",
)
async def get_menu(
    merchant_id: str,
    service: MerchantService = Depends(get_merchant_service),
) -> list[MenuItemResponse]:
    """Get merchant's menu."""
    return await service.get_menu(merchant_id)


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
# Admin Endpoints
# =============================================================================
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
