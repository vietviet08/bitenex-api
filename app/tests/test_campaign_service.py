from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.exceptions import ValidationError
from app.modules.marketing.campaign_service import CampaignService
from app.modules.marketing.models import Campaign
from app.modules.marketing.schemas import CampaignCreate, CampaignUpdate


def _campaign_create_payload(
    *,
    start_date: datetime,
    end_date: datetime,
    voucher_code: str | None = None,
) -> CampaignCreate:
    return CampaignCreate(
        name="Summer Sale",
        campaign_type="DISCOUNT",
        discount_type="PERCENTAGE",
        discount_value=10,
        min_order_value=100,
        target_audience="ALL",
        start_date=start_date,
        end_date=end_date,
        voucher_code=voucher_code,
    )


@pytest.mark.asyncio
async def test_create_campaign_accepts_naive_datetimes(db_session):
    service = CampaignService(db_session)
    start_date = datetime(2000, 1, 1, 0, 0, 0)
    end_date = datetime(2099, 1, 1, 0, 0, 0)

    response = await service.create_campaign(
        _campaign_create_payload(
            start_date=start_date,
            end_date=end_date,
            voucher_code="SUMMER2026",
        ),
        created_by="admin-user",
    )

    campaign = (
        await db_session.execute(select(Campaign).where(Campaign.id == response.id))
    ).scalar_one()
    assert response.status == "ACTIVE"
    assert campaign.start_date == response.start_date
    assert campaign.end_date == response.end_date


@pytest.mark.asyncio
async def test_update_campaign_validates_normalized_datetime_order(db_session):
    service = CampaignService(db_session)
    start_date = datetime.now(timezone.utc) + timedelta(days=1)
    end_date = start_date + timedelta(days=5)
    created = await service.create_campaign(
        _campaign_create_payload(start_date=start_date, end_date=end_date),
        created_by="admin-user",
    )

    with pytest.raises(ValidationError, match="End date must be after start date"):
        await service.update_campaign(
            created.id,
            CampaignUpdate(end_date=datetime.now() + timedelta(hours=1)),
        )
