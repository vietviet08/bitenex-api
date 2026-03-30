# =============================================================================
# Order Module - Internal API Router (n8n endpoints)
# =============================================================================

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import RequireInternalService
from app.modules.dispatch.models import DispatchAssignment
from app.modules.order.models import Order
from app.shared.enums import OrderStatus

internal_router = APIRouter(
    prefix="/internal/orders",
    tags=["Internal — Orders"],
)


class ActiveDeliveryItem(BaseModel):
    orderId: str
    orderNumber: str
    userId: str
    merchantId: str
    driverId: str | None
    assignedAt: datetime | None
    estimatedDeliveryMinutes: int
    status: str


class ActiveDeliveriesResponse(BaseModel):
    items: list[ActiveDeliveryItem]
    total: int


def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db


@internal_router.get(
    "/active-deliveries",
    response_model=ActiveDeliveriesResponse,
    summary="List orders currently in DELIVERING state",
    dependencies=[RequireInternalService],
)
async def get_active_deliveries(
    db: AsyncSession = Depends(get_db),
) -> ActiveDeliveriesResponse:
    """
    Returns all orders currently in DELIVERING status.
    Used by WF-05 SLA monitor cron to track overdue deliveries.
    """
    result = await db.execute(
        select(Order).where(
            Order.status == OrderStatus.DELIVERING.value,
            Order.is_deleted.is_(False),
        )
    )
    orders = result.scalars().all()

    # Try to fetch dispatch records for driver/assignedAt info
    order_ids = [o.id for o in orders]
    dispatch_map: dict[str, DispatchAssignment] = {}
    if order_ids:
        dispatch_result = await db.execute(
            select(DispatchAssignment).where(
                DispatchAssignment.order_id.in_(order_ids),
                DispatchAssignment.is_deleted.is_(False),
            )
        )
        for d in dispatch_result.scalars().all():
            dispatch_map[d.order_id] = d

    items = []
    for order in orders:
        dispatch = dispatch_map.get(order.id)
        items.append(
            ActiveDeliveryItem(
                orderId=order.id,
                orderNumber=order.order_number,
                userId=order.user_id,
                merchantId=order.merchant_id,
                driverId=dispatch.driver_id if dispatch else None,
                assignedAt=dispatch.created_at if dispatch else None,
                estimatedDeliveryMinutes=30,
                status=order.status,
            )
        )

    return ActiveDeliveriesResponse(items=items, total=len(items))
