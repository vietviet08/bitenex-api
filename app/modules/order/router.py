# =============================================================================
# Order Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_role
from app.modules.order.schemas import (
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdate,
)
from app.modules.order.service import OrderService
from app.shared.dto import MessageResponse
from app.shared.enums import OrderStatus, Role

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)


async def get_order_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    return OrderService(db)


# =============================================================================
# User Endpoints
# =============================================================================
@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create order",
)
async def create_order(
    data: OrderCreate,
    user: CurrentUser,
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    """Create a new order."""
    return await service.create_order(user.user_id, data)


@router.get(
    "/my",
    response_model=OrderListResponse,
    summary="Get my orders",
)
async def get_my_orders(
    user: CurrentUser,
    status_filter: OrderStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: OrderService = Depends(get_order_service),
) -> OrderListResponse:
    """Get current user's orders."""
    items, total = await service.get_user_orders(
        user.user_id, status_filter, page, per_page
    )
    return OrderListResponse(items=items, total=total)


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order",
)
async def get_order(
    order_id: str,
    user: CurrentUser,
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    """Get order by ID."""
    return await service.get_order_by_id(order_id)


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel order",
)
async def cancel_order(
    order_id: str,
    user: CurrentUser,
    reason: str = "",
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    """Cancel an order."""
    return await service.cancel_order(order_id, reason, user.user_id)


# =============================================================================
# Merchant Endpoints
# =============================================================================
@router.get(
    "/merchant/incoming",
    response_model=OrderListResponse,
    summary="Get merchant orders",
    dependencies=[Depends(require_role(Role.MERCHANT))],
)
async def get_merchant_orders(
    user: CurrentUser,
    status_filter: OrderStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: OrderService = Depends(get_order_service),
) -> OrderListResponse:
    """Get orders for merchant."""
    # TODO: Get merchant_id from user
    items, total = await service.get_merchant_orders(
        "", status_filter, page, per_page
    )
    return OrderListResponse(items=items, total=total)


@router.post(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status",
    dependencies=[Depends(require_role(Role.MERCHANT, Role.DRIVER, Role.ADMIN))],
)
async def update_order_status(
    order_id: str,
    data: OrderStatusUpdate,
    user: CurrentUser,
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    """Update order status."""
    return await service.update_status(order_id, data, user.user_id)


# =============================================================================
# Driver Endpoints
# =============================================================================
@router.get(
    "/driver/assigned",
    response_model=OrderListResponse,
    summary="Get driver orders",
    dependencies=[Depends(require_role(Role.DRIVER))],
)
async def get_driver_orders(
    user: CurrentUser,
    status_filter: OrderStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: OrderService = Depends(get_order_service),
) -> OrderListResponse:
    """Get orders assigned to driver."""
    # TODO: Get driver_id from user
    items, total = await service.get_driver_orders(
        "", status_filter, page, per_page
    )
    return OrderListResponse(items=items, total=total)
