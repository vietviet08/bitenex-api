# =============================================================================
# Marketing Module - Router
# =============================================================================

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import RequireInternalService
from app.modules.journey.models import JourneyOffer
from app.modules.journey.service import JourneyService

router = APIRouter(
    prefix="/internal/marketing",
    tags=["Internal — Marketing"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class IssueVoucherRequest(BaseModel):
    userId: str
    voucherCode: str
    discountAmount: float
    freeDeliveryOrders: int | None = None
    expiresInDays: int = 7
    reason: str | None = "n8n_workflow"


class IssueVoucherResponse(BaseModel):
    voucherCode: str
    discountAmount: float
    expiresAt: datetime
    isExisting: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/issue-voucher",
    response_model=IssueVoucherResponse,
    status_code=status.HTTP_200_OK,
    summary="Issue or reuse a discount voucher for a user",
    dependencies=[RequireInternalService],
)
async def issue_voucher(
    req: IssueVoucherRequest,
    db: AsyncSession = Depends(get_db),
) -> IssueVoucherResponse:
    """
    Create a voucher record (JourneyOffer) for the user.
    Returns existing active voucher if one already exists for this code+user.

    Used by:
    - WF-01: WELCOME50K
    - WF-04: REORDER30K
    - WF-05: Delay compensation vouchers
    - WF-08: MISSED20K, COMEBACK35K, BACK50K
    """
    from sqlalchemy import select

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=req.expiresInDays)

    # Check for existing active offer with the same code for this user
    existing_result = await db.execute(
        select(JourneyOffer).where(
            JourneyOffer.user_id == req.userId,
            JourneyOffer.code == req.voucherCode,
            JourneyOffer.status == JourneyService.OFFER_STATUS_ACTIVE,
            JourneyOffer.expires_at >= now,
            JourneyOffer.is_deleted.is_(False),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        return IssueVoucherResponse(
            voucherCode=existing.code,
            discountAmount=float(existing.max_discount),
            expiresAt=existing.expires_at,
            isExisting=True,
        )

    offer = JourneyOffer(
        user_id=req.userId,
        journey_type="n8n_marketing",
        source_cart_id=f"marketing:{req.userId}:{req.voucherCode}",
        offer_type="discount",
        code=req.voucherCode,
        max_discount=req.discountAmount,
        min_cart_value=0.0,
        status=JourneyService.OFFER_STATUS_ACTIVE,
        expires_at=expires_at,
        metadata_json=str({
            "reason": req.reason,
            "free_delivery_orders": req.freeDeliveryOrders,
            "discount_amount": req.discountAmount,
        }),
    )
    db.add(offer)
    await db.flush()
    await db.refresh(offer)

    return IssueVoucherResponse(
        voucherCode=offer.code,
        discountAmount=float(offer.max_discount),
        expiresAt=offer.expires_at,
        isExisting=False,
    )
