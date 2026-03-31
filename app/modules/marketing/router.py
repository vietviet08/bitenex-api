# =============================================================================
# Marketing Module - Router
# =============================================================================

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
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


def _voucher_source_key(user_id: str, voucher_code: str) -> str:
    return f"marketing:{user_id}:{voucher_code}"


async def _generate_unique_voucher_code(
    db: AsyncSession,
    base_code: str,
    user_id: str,
) -> str:
    """
    Generate a globally unique voucher code while keeping a readable base prefix.
    """
    normalized_user = "".join(ch for ch in user_id.upper() if ch.isalnum()) or "USER"
    candidates = [base_code]

    for suffix_length in (6, 8, 12):
        suffix = normalized_user[-suffix_length:]
        max_base_length = 50 - len(suffix) - 1
        trimmed_base = base_code[:max_base_length]
        candidates.append(f"{trimmed_base}-{suffix}")

    for candidate in candidates:
        existing = await db.execute(
            select(JourneyOffer.id).where(JourneyOffer.code == candidate)
        )
        if existing.scalar_one_or_none() is None:
            return candidate

    raise ValueError(f"Unable to generate unique voucher code for base '{base_code}'")


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
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=req.expiresInDays)
    source_key = _voucher_source_key(req.userId, req.voucherCode)

    # Check for existing active offer for this workflow/user pair.
    existing_result = await db.execute(
        select(JourneyOffer).where(
            JourneyOffer.user_id == req.userId,
            JourneyOffer.source_cart_id == source_key,
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

    generated_code = await _generate_unique_voucher_code(
        db=db,
        base_code=req.voucherCode,
        user_id=req.userId,
    )

    offer = JourneyOffer(
        user_id=req.userId,
        journey_type="n8n_marketing",
        source_cart_id=source_key,
        offer_type="discount",
        code=generated_code,
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
