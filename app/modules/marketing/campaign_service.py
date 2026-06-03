# =============================================================================
# Marketing Module - Campaign Service
# =============================================================================

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.marketing.models import Campaign
from app.modules.marketing.schemas import (
    CampaignCreate,
    CampaignListResponse,
    CampaignResponse,
    CampaignStatsResponse,
    CampaignUpdate,
)
from app.shared.utils import ensure_utc


def _as_utc(value: datetime) -> datetime:
    return ensure_utc(value).astimezone(timezone.utc)


class CampaignService:
    """
    Campaign management service.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_campaigns(
        self,
        status: str | None = None,
        campaign_type: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> CampaignListResponse:
        """List campaigns with filters."""
        query = select(Campaign).where(Campaign.is_deleted.is_(False))

        if status:
            query = query.where(Campaign.status == status)
        if campaign_type:
            query = query.where(Campaign.campaign_type == campaign_type)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Paginate
        query = query.order_by(Campaign.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        campaigns = result.scalars().all()

        return CampaignListResponse(
            items=[CampaignResponse.model_validate(c) for c in campaigns],
            total=total,
        )

    async def get_campaign(self, campaign_id: str) -> CampaignResponse:
        """Get campaign by ID."""
        result = await self.db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.is_deleted.is_(False),
            )
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise NotFoundError("Campaign", campaign_id)
        return CampaignResponse.model_validate(campaign)

    async def create_campaign(
        self,
        data: CampaignCreate,
        created_by: str,
    ) -> CampaignResponse:
        """Create a new campaign."""
        start_date = _as_utc(data.start_date)
        end_date = _as_utc(data.end_date)

        # Validate dates
        if end_date <= start_date:
            raise ValidationError(message="End date must be after start date")

        # Check voucher code uniqueness
        if data.voucher_code:
            existing = await self.db.execute(
                select(Campaign.id).where(
                    Campaign.voucher_code == data.voucher_code,
                    Campaign.is_deleted.is_(False),
                )
            )
            if existing.scalar_one_or_none():
                raise ValidationError(message=f"Voucher code '{data.voucher_code}' already exists")

        # Determine status based on start date
        now = datetime.now(timezone.utc)
        status = "SCHEDULED" if start_date > now else "ACTIVE"

        campaign = Campaign(
            name=data.name,
            description=data.description,
            campaign_type=data.campaign_type,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            max_discount=data.max_discount,
            min_order_value=data.min_order_value,
            voucher_code=data.voucher_code,
            auto_generate_vouchers=data.auto_generate_vouchers,
            max_vouchers=data.max_vouchers,
            target_audience=data.target_audience,
            start_date=start_date,
            end_date=end_date,
            budget=data.budget,
            is_featured=data.is_featured,
            status=status,
            created_by=created_by,
        )

        self.db.add(campaign)
        await self.db.flush()
        await self.db.refresh(campaign)
        return CampaignResponse.model_validate(campaign)

    async def update_campaign(
        self,
        campaign_id: str,
        data: CampaignUpdate,
    ) -> CampaignResponse:
        """Update campaign."""
        result = await self.db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.is_deleted.is_(False),
            )
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise NotFoundError("Campaign", campaign_id)

        # Only allow updates to DRAFT or SCHEDULED campaigns
        if campaign.status not in ("DRAFT", "SCHEDULED"):
            raise ValidationError(message="Can only update DRAFT or SCHEDULED campaigns")

        update_data = data.model_dump(exclude_unset=True)
        for date_field in ("start_date", "end_date"):
            if date_field not in update_data:
                continue
            if update_data[date_field] is None:
                raise ValidationError(message=f"{date_field} is required")
            update_data[date_field] = _as_utc(update_data[date_field])

        start_date = update_data.get("start_date", campaign.start_date)
        end_date = update_data.get("end_date", campaign.end_date)
        if _as_utc(end_date) <= _as_utc(start_date):
            raise ValidationError(message="End date must be after start date")

        for field, value in update_data.items():
            setattr(campaign, field, value)

        await self.db.flush()
        await self.db.refresh(campaign)
        return CampaignResponse.model_validate(campaign)

    async def update_campaign_status(
        self,
        campaign_id: str,
        new_status: str,
    ) -> CampaignResponse:
        """Update campaign status."""
        result = await self.db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.is_deleted.is_(False),
            )
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise NotFoundError("Campaign", campaign_id)

        # Validate status transitions
        valid_transitions = {
            "DRAFT": ["SCHEDULED", "ACTIVE", "CANCELLED"],
            "SCHEDULED": ["ACTIVE", "CANCELLED"],
            "ACTIVE": ["PAUSED", "ENDED"],
            "PAUSED": ["ACTIVE", "ENDED"],
        }

        allowed = valid_transitions.get(campaign.status, [])
        if new_status not in allowed:
            raise ValidationError(
                message=f"Cannot transition from {campaign.status} to {new_status}"
            )

        campaign.status = new_status
        await self.db.flush()
        await self.db.refresh(campaign)
        return CampaignResponse.model_validate(campaign)

    async def delete_campaign(self, campaign_id: str) -> None:
        """Soft delete campaign."""
        result = await self.db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.is_deleted.is_(False),
            )
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise NotFoundError("Campaign", campaign_id)

        if campaign.status == "ACTIVE":
            raise ValidationError(message="Cannot delete active campaign. Pause it first.")

        campaign.soft_delete()
        await self.db.flush()

    async def get_campaign_stats(self) -> CampaignStatsResponse:
        """Get campaign statistics."""
        from sqlalchemy import case

        res = await self.db.execute(
            select(
                func.count(),
                func.sum(case((Campaign.status == "ACTIVE", 1), else_=0)),
                func.sum(case((Campaign.status == "SCHEDULED", 1), else_=0)),
                func.sum(case((Campaign.status == "ENDED", 1), else_=0)),
                func.coalesce(func.sum(Campaign.budget), 0.0),
                func.coalesce(func.sum(Campaign.spent), 0.0),
                func.coalesce(func.sum(Campaign.total_revenue), 0.0),
                func.coalesce(func.sum(Campaign.total_orders), 0),
                func.coalesce(func.sum(Campaign.used_vouchers), 0),
            ).where(Campaign.is_deleted.is_(False))
        )
        result = res.one()

        return CampaignStatsResponse(
            total_campaigns=result[0] or 0,
            active_campaigns=result[1] or 0,
            scheduled_campaigns=result[2] or 0,
            ended_campaigns=result[3] or 0,
            total_budget=float(result[4] or 0.0),
            total_spent=float(result[5] or 0.0),
            total_revenue_generated=float(result[6] or 0.0),
            total_orders=result[7] or 0,
            total_vouchers_used=result[8] or 0,
        )
