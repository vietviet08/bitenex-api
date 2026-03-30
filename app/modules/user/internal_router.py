# =============================================================================
# User Module - Internal API Router (n8n endpoints)
# =============================================================================

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import RequireInternalService
from app.modules.order.models import Order
from app.modules.user.models import User

internal_router = APIRouter(
    prefix="/internal/users",
    tags=["Internal — Users"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LapsedUserItem(BaseModel):
    userId: str
    email: str
    firstName: str | None
    lapsedDays: int


class LapsedUsersResponse(BaseModel):
    items: list[LapsedUserItem]
    total: int


class LastOrderResponse(BaseModel):
    orderId: str | None
    merchantName: str | None
    total: float | None
    createdAt: datetime | None


class UserPreferencesResponse(BaseModel):
    userId: str
    firstName: str | None
    email: str


class UserActivityResponse(BaseModel):
    userId: str
    hasOrdered: bool
    lastOrderedAt: datetime | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@internal_router.get(
    "/lapsed",
    response_model=LapsedUsersResponse,
    summary="Get users who have not ordered in N days",
    dependencies=[RequireInternalService],
)
async def get_lapsed_users(
    segments: str = Query(default="7d,14d,30d", description="Comma-separated day segments"),
    limit: int = Query(default=500, le=1000),
    db: AsyncSession = Depends(get_db),
) -> LapsedUsersResponse:
    """
    Returns users who have not placed an order within the given day window.
    Used by WF-08 win-back lapsed users cron.
    """
    # Parse the maximum segment to determine the lookback window
    day_values = []
    for seg in segments.split(","):
        seg = seg.strip().rstrip("d")
        try:
            day_values.append(int(seg))
        except ValueError:
            pass

    max_days = max(day_values) if day_values else 30
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)

    # Find all users
    users_result = await db.execute(
        select(User).where(User.is_deleted.is_(False)).limit(limit)
    )
    users = users_result.scalars().all()

    # Find which users have ordered recently
    active_user_ids: set[str] = set()
    recent_orders = await db.execute(
        select(Order.user_id).where(
            Order.created_at >= cutoff,
            Order.is_deleted.is_(False),
        ).distinct()
    )
    for row in recent_orders.all():
        active_user_ids.add(row[0])

    # Determine lapsed days per user
    items = []
    now = datetime.now(timezone.utc)
    for user in users:
        if user.id in active_user_ids:
            continue
        # Get their last order
        last_order_result = await db.execute(
            select(Order).where(
                Order.user_id == user.id,
                Order.is_deleted.is_(False),
            ).order_by(Order.created_at.desc()).limit(1)
        )
        last_order = last_order_result.scalar_one_or_none()
        if last_order and last_order.created_at:
            lapsed_days = (now - last_order.created_at).days
        else:
            lapsed_days = max_days  # Never ordered or very old

        # Only include if within the requested max window
        if lapsed_days <= max_days:
            items.append(LapsedUserItem(
                userId=user.id,
                email=user.email,
                firstName=user.first_name,
                lapsedDays=lapsed_days,
            ))

    return LapsedUsersResponse(items=items[:limit], total=len(items))


@internal_router.get(
    "/{user_id}/last-order",
    response_model=LastOrderResponse,
    summary="Get the most recent order for a user",
    dependencies=[RequireInternalService],
)
async def get_user_last_order(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> LastOrderResponse:
    """Used by WF-08 to personalize win-back messages for 7-day segment."""
    result = await db.execute(
        select(Order).where(
            Order.user_id == user_id,
            Order.is_deleted.is_(False),
        ).order_by(Order.created_at.desc()).limit(1)
    )
    order = result.scalar_one_or_none()
    if not order:
        return LastOrderResponse(orderId=None, merchantName=None, total=None, createdAt=None)

    return LastOrderResponse(
        orderId=order.id,
        merchantName=order.merchant_id,  # merchant_name resolved on frontend
        total=float(order.total_amount),
        createdAt=order.created_at,
    )


@internal_router.get(
    "/{user_id}/preferences",
    response_model=UserPreferencesResponse,
    summary="Get basic user preferences/profile",
    dependencies=[RequireInternalService],
)
async def get_user_preferences(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesResponse:
    """Returns basic user data for personalization in win-back flows."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted.is_(False))
    )
    user = result.scalar_one_or_none()
    if not user:
        return UserPreferencesResponse(userId=user_id, firstName=None, email="")

    return UserPreferencesResponse(
        userId=user.id,
        firstName=user.first_name,
        email=user.email,
    )


@internal_router.get(
    "/{user_id}/activity",
    response_model=UserActivityResponse,
    summary="Check recent user ordering activity",
    dependencies=[RequireInternalService],
)
async def get_user_activity(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> UserActivityResponse:
    """
    Returns whether a user has placed an order in the last 72 hours.
    Used by WF-08 after wait node to check if win-back succeeded.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    result = await db.execute(
        select(Order).where(
            Order.user_id == user_id,
            Order.created_at >= cutoff,
            Order.is_deleted.is_(False),
        ).order_by(Order.created_at.desc()).limit(1)
    )
    order = result.scalar_one_or_none()

    return UserActivityResponse(
        userId=user_id,
        hasOrdered=order is not None,
        lastOrderedAt=order.created_at if order else None,
    )
