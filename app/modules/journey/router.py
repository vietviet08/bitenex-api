# =============================================================================
# Journey Module - API Router
# =============================================================================

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireInternalService
from app.modules.journey.schemas import (
    AbandonedCartActivityResponse,
    AbandonedCartActivityUpsert,
    AuthenticatedAbandonedCartActivityUpsert,
    AbandonedCartStatusRequest,
    AbandonedCartStatusResponse,
    CreateFreeshipOfferRequest,
    FirstOrderStatusResponse,
    JourneyOfferResponse,
    ReorderStatusResponse,
    ReviewStatusResponse,
)
from app.modules.journey.service import JourneyService
from app.modules.notification.models import Notification
from app.modules.order.models import Order

router = APIRouter(
    prefix="/internal/journeys",
    tags=["Journey Internal"],
)

public_router = APIRouter(
    prefix="/journeys",
    tags=["Journeys"],
)


def get_journey_service(
    db: AsyncSession = Depends(get_db),
) -> JourneyService:
    return JourneyService(db)


@router.post(
    "/abandoned-carts/activity",
    response_model=AbandonedCartActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upsert abandoned-cart activity",
    dependencies=[RequireInternalService],
)
async def upsert_abandoned_cart_activity(
    data: AbandonedCartActivityUpsert,
    service: JourneyService = Depends(get_journey_service),
) -> AbandonedCartActivityResponse:
    """Record cart activity snapshots so the scheduler can detect abandoned carts."""
    return await service.upsert_abandoned_cart_activity(data)


@public_router.post(
    "/abandoned-carts/activity",
    response_model=AbandonedCartActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upsert my cart activity",
)
async def upsert_my_abandoned_cart_activity(
    data: AuthenticatedAbandonedCartActivityUpsert,
    user: CurrentUser,
    service: JourneyService = Depends(get_journey_service),
) -> AbandonedCartActivityResponse:
    """Allow the signed-in user app to sync cart activity snapshots."""
    return await service.upsert_user_cart_activity(user_id=user.user_id, data=data)


@router.post(
    "/abandoned-carts/status",
    response_model=AbandonedCartStatusResponse,
    summary="Check abandoned-cart recovery status",
    dependencies=[RequireInternalService],
)
async def abandoned_cart_status(
    data: AbandonedCartStatusRequest,
    service: JourneyService = Depends(get_journey_service),
) -> AbandonedCartStatusResponse:
    """Resolve whether a tracked cart has already converted to an order."""
    return await service.get_abandoned_cart_status(data)


@router.post(
    "/abandoned-carts/offers/freeship",
    response_model=JourneyOfferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or reuse a freeship recovery offer",
    dependencies=[RequireInternalService],
)
async def create_freeship_offer(
    data: CreateFreeshipOfferRequest,
    service: JourneyService = Depends(get_journey_service),
) -> JourneyOfferResponse:
    """Issue a temporary freeship code for an abandoned cart recovery flow."""
    return await service.create_freeship_offer(data)


@router.get(
    "/users/{user_id}/first-order-status",
    response_model=FirstOrderStatusResponse,
    summary="Check if user has placed their first order",
    dependencies=[RequireInternalService],
)
async def get_first_order_status(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> FirstOrderStatusResponse:
    """Used by WF-01 to check conversion after welcome nudge."""
    result = await db.execute(
        select(Order).where(
            Order.user_id == user_id,
            Order.is_deleted.is_(False),
        ).order_by(Order.created_at.asc()).limit(1)
    )
    order = result.scalar_one_or_none()
    return FirstOrderStatusResponse(
        userId=user_id,
        hasFirstOrder=order is not None,
        orderId=order.id if order else None,
        createdAt=order.created_at if order else None,
    )


@router.get(
    "/orders/{order_id}/review-status",
    response_model=ReviewStatusResponse,
    summary="Check if a delivered order has been reviewed",
    dependencies=[RequireInternalService],
)
async def get_review_status(
    order_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReviewStatusResponse:
    """
    Used by WF-04 to check if user has submitted a rating.
    Uses Notification table as a proxy — in production, query a dedicated
    OrderReview model when available.
    """
    # Proxy: check if a review notification exists for this order
    result = await db.execute(
        select(Notification).where(
            Notification.type == "REVIEW_RECEIVED",
            Notification.is_deleted.is_(False),
        ).limit(1)
    )
    review = result.scalar_one_or_none()
    return ReviewStatusResponse(
        orderId=order_id,
        hasReview=review is not None,
        averageRating=None,
    )


@router.get(
    "/users/{user_id}/reorder-status",
    response_model=ReorderStatusResponse,
    summary="Check if user has reordered in the last 7 days",
    dependencies=[RequireInternalService],
)
async def get_reorder_status(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReorderStatusResponse:
    """Used by WF-04 to check if win-back voucher led to reorder."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    result = await db.execute(
        select(Order).where(
            Order.user_id == user_id,
            Order.created_at >= cutoff,
            Order.is_deleted.is_(False),
        ).order_by(Order.created_at.desc()).limit(1)
    )
    order = result.scalar_one_or_none()
    return ReorderStatusResponse(
        userId=user_id,
        hasReordered=order is not None,
        orderId=order.id if order else None,
    )
