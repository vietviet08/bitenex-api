# =============================================================================
# Voucher Module - Public Router
# =============================================================================

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.modules.voucher.schemas import (
    VoucherListResponse,
    VoucherResponse,
    VoucherValidateRequest,
    VoucherValidateResponse,
)
from app.modules.voucher.service import VoucherService
from app.shared.enums import VoucherStatus

router = APIRouter(
    prefix="/vouchers",
    tags=["Vouchers"],
)


def get_voucher_service(
    db: AsyncSession = Depends(get_db),
) -> VoucherService:
    return VoucherService(db)


# =============================================================================
# User Endpoints
# =============================================================================
@router.get(
    "",
    response_model=VoucherListResponse,
    summary="List user vouchers",
)
async def list_user_vouchers(
    user: CurrentUser,
    status_filter: VoucherStatus | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: VoucherService = Depends(get_voucher_service),
) -> VoucherListResponse:
    """Get all vouchers for the authenticated user."""
    items, total = await service.list_user_vouchers(
        user.user_id,
        status_filter=status_filter,
        page=page,
        per_page=per_page,
    )
    return VoucherListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get(
    "/{voucher_id}",
    response_model=VoucherResponse,
    summary="Get voucher details",
)
async def get_voucher(
    voucher_id: UUID,
    user: CurrentUser,
    service: VoucherService = Depends(get_voucher_service),
) -> VoucherResponse:
    """Get details of a specific voucher."""
    return await service.get_voucher(str(voucher_id), user_id=user.user_id)


@router.post(
    "/validate",
    response_model=VoucherValidateResponse,
    summary="Validate voucher code",
)
async def validate_voucher(
    data: VoucherValidateRequest,
    user: CurrentUser,
    service: VoucherService = Depends(get_voucher_service),
) -> VoucherValidateResponse:
    """Validate if a voucher code can be applied to a cart."""
    return await service.validate_voucher(
        code=data.code,
        user_id=user.user_id,
        cart_value=data.cart_value,
    )
