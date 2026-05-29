# =============================================================================
# Order Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_role
from app.modules.order.schemas import (
    AdminOrderListResponse,
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdate,
    OrderTrackingResponse,
)
from app.modules.order.service import OrderService
from app.shared.enums import OrderStatus, Role

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)


def get_order_service(db: AsyncSession = Depends(get_db)) -> OrderService:
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
    items, total = await service.get_user_orders(user.user_id, status_filter, page, per_page)
    return OrderListResponse(items=items, total=total)


@router.get(
    "/admin/list",
    response_model=AdminOrderListResponse,
    summary="Admin list orders",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def admin_list_orders(
    search: str | None = Query(default=None, description="Search by order/user/merchant/address"),
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    user_id: str | None = Query(default=None),
    merchant_id: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: OrderService = Depends(get_order_service),
) -> AdminOrderListResponse:
    """List orders for admin operations."""
    items, total = await service.get_admin_orders(
        search=search,
        status=status_filter,
        user_id=user_id,
        merchant_id=merchant_id,
        page=page,
        per_page=per_page,
    )
    return AdminOrderListResponse(items=items, total=total)


@router.get(
    "/{order_id}/tracking",
    response_model=OrderTrackingResponse,
    summary="Get order live tracking data",
)
async def get_order_tracking(
    order_id: str,
    user: CurrentUser,
    service: OrderService = Depends(get_order_service),
) -> OrderTrackingResponse:
    """Get pickup, delivery, and latest driver coordinates for an order."""
    return await service.get_order_tracking(
        order_id,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )


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
    return await service.get_order_by_id(
        order_id,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )


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
    return await service.cancel_order(
        order_id,
        reason,
        user.user_id,
        actor_role=user.role,
    )


@router.post(
    "/{order_id}/driver/cancel-pickup",
    response_model=OrderResponse,
    summary="Driver cancels accepted pickup",
    dependencies=[Depends(require_role(Role.DRIVER))],
)
async def driver_cancel_pickup(
    order_id: str,
    user: CurrentUser,
    reason: str = "",
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    """Let an assigned driver release an order before pickup."""
    return await service.driver_cancel_pickup(
        order_id,
        driver_user_id=user.user_id,
        reason=reason,
    )


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
    merchant_id = await service.resolve_merchant_id_by_user_id(user.user_id)
    items, total = await service.get_merchant_orders(merchant_id, status_filter, page, per_page)
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
    return await service.update_status(
        order_id,
        data,
        changed_by=user.user_id,
        actor_role=user.role,
    )


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
    driver_id = await service.resolve_driver_id_by_user_id(user.user_id)
    items, total = await service.get_driver_orders(driver_id, status_filter, page, per_page)
    return OrderListResponse(items=items, total=total)
