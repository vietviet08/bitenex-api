# =============================================================================
# Journey Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, status
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
    JourneyOfferResponse,
)
from app.modules.journey.service import JourneyService

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
