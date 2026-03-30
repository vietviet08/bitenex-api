# =============================================================================
# Merchant Module - Internal API Router (n8n endpoints)
# =============================================================================

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import RequireInternalService
from app.modules.merchant.models import Merchant
from app.modules.order.models import Order
from app.shared.enums import MerchantStatus, OrderStatus

internal_router = APIRouter(
    prefix="/internal/merchants",
    tags=["Internal — Merchants"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ActiveMerchantItem(BaseModel):
    merchantId: str
    merchantName: str
    ownerUserId: str
    city: str | None


class ActiveMerchantsResponse(BaseModel):
    items: list[ActiveMerchantItem]
    total: int


class DailyStatsResponse(BaseModel):
    merchantId: str
    date: str
    totalOrders: int
    revenue: float
    cancelledOrders: int
    cancelRate: float
    averageOrderValue: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@internal_router.get(
    "/active-list",
    response_model=ActiveMerchantsResponse,
    summary="List all active merchants",
    dependencies=[RequireInternalService],
)
async def get_active_merchants(
    db: AsyncSession = Depends(get_db),
) -> ActiveMerchantsResponse:
    """
    Returns all merchants with ACTIVE status.
    Used by WF-07 merchant daily analytics digest.
    """
    result = await db.execute(
        select(Merchant).where(
            Merchant.status == MerchantStatus.ACTIVE.value,
            Merchant.is_deleted.is_(False),
        )
    )
    merchants = result.scalars().all()

    return ActiveMerchantsResponse(
        items=[
            ActiveMerchantItem(
                merchantId=m.id,
                merchantName=m.name,
                ownerUserId=m.user_id,
                city=m.city,
            )
            for m in merchants
        ],
        total=len(merchants),
    )


@internal_router.get(
    "/{merchant_id}/daily-stats",
    response_model=DailyStatsResponse,
    summary="Get daily order stats for a merchant",
    dependencies=[RequireInternalService],
)
async def get_merchant_daily_stats(
    merchant_id: str,
    date: str = Query(default=None, description="Date in YYYY-MM-DD format, defaults to yesterday"),
    db: AsyncSession = Depends(get_db),
) -> DailyStatsResponse:
    """
    Returns aggregated order stats for a merchant on the given date.
    Used by WF-07 to build the daily email analytics digest.
    """
    if date is None:
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    else:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()

    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(Order).where(
            Order.merchant_id == merchant_id,
            Order.created_at >= day_start,
            Order.created_at < day_end,
            Order.is_deleted.is_(False),
        )
    )
    orders = result.scalars().all()

    total = len(orders)
    cancelled = sum(1 for o in orders if o.status == OrderStatus.CANCELLED.value)
    revenue = sum(float(o.total_amount) for o in orders if o.status not in [OrderStatus.CANCELLED.value, OrderStatus.REFUNDED.value])
    avg_value = revenue / (total - cancelled) if (total - cancelled) > 0 else 0.0
    cancel_rate = round(cancelled / total * 100, 1) if total > 0 else 0.0

    return DailyStatsResponse(
        merchantId=merchant_id,
        date=str(target_date),
        totalOrders=total,
        revenue=round(revenue, 2),
        cancelledOrders=cancelled,
        cancelRate=cancel_rate,
        averageOrderValue=round(avg_value, 2),
    )
