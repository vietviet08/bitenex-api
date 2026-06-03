# =============================================================================
# Marketing Module - Admin Campaign Router
# =============================================================================

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdmin
from app.modules.marketing.campaign_service import CampaignService
from app.modules.marketing.schemas import (
    CampaignCreate,
    CampaignListResponse,
    CampaignResponse,
    CampaignStatsResponse,
    CampaignUpdate,
    CampaignUpdateStatus,
)
from app.shared.dto import MessageResponse

router = APIRouter(
    prefix="/admin/campaigns",
    tags=["Admin - Campaigns"],
    dependencies=[RequireAdmin],
)


def get_campaign_service(db: AsyncSession = Depends(get_db)) -> CampaignService:
    return CampaignService(db)


@router.get(
    "",
    response_model=CampaignListResponse,
    summary="List campaigns",
)
async def list_campaigns(
    status: str | None = Query(default=None),
    campaign_type: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignListResponse:
    """List campaigns with optional filters."""
    return await service.list_campaigns(
        status=status,
        campaign_type=campaign_type,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/stats",
    response_model=CampaignStatsResponse,
    summary="Get campaign statistics",
)
async def get_campaign_stats(
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignStatsResponse:
    """Get campaign statistics overview."""
    return await service.get_campaign_stats()


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    summary="Get campaign",
)
async def get_campaign(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignResponse:
    """Get campaign by ID."""
    return await service.get_campaign(campaign_id)


@router.post(
    "",
    response_model=CampaignResponse,
    summary="Create campaign",
)
async def create_campaign(
    data: CampaignCreate,
    user: CurrentUser,
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignResponse:
    """Create a new campaign."""
    return await service.create_campaign(data, created_by=user.user_id)


@router.patch(
    "/{campaign_id}",
    response_model=CampaignResponse,
    summary="Update campaign",
)
async def update_campaign(
    campaign_id: str,
    data: CampaignUpdate,
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignResponse:
    """Update campaign details."""
    return await service.update_campaign(campaign_id, data)


@router.patch(
    "/{campaign_id}/status",
    response_model=CampaignResponse,
    summary="Update campaign status",
)
async def update_campaign_status(
    campaign_id: str,
    data: CampaignUpdateStatus,
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignResponse:
    """Update campaign status."""
    return await service.update_campaign_status(campaign_id, data.status)


@router.delete(
    "/{campaign_id}",
    response_model=MessageResponse,
    summary="Delete campaign",
)
async def delete_campaign(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service),
) -> MessageResponse:
    """Delete campaign (soft delete)."""
    await service.delete_campaign(campaign_id)
    return MessageResponse(message="Campaign deleted successfully")
