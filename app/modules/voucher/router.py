# =============================================================================
# Voucher Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_role
from app.modules.voucher.schemas import (
    VoucherCreate,
    VoucherListResponse,
    VoucherResponse,
    VoucherUpdate,
    VoucherValidationRequest,
    VoucherValidationResponse,
)
from app.modules.voucher.service import VoucherService
from app.shared.enums import Role

router = APIRouter(
    prefix="/vouchers",
    tags=["Vouchers"],
)


def get_voucher_service(db: AsyncSession = Depends(get_db)) -> VoucherService:
    return VoucherService(db)


@router.post(
    "",
    response_model=VoucherResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create voucher",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def create_voucher(
    data: VoucherCreate,
    service: VoucherService = Depends(get_voucher_service),
) -> VoucherResponse:
    return await service.create_voucher(data)


@router.get(
    "",
    response_model=VoucherListResponse,
    summary="List vouchers",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def list_vouchers(
    merchant_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    service: VoucherService = Depends(get_voucher_service),
) -> VoucherListResponse:
    return await service.list_vouchers(
        merchant_id=merchant_id,
        is_active=is_active,
        page=page,
        per_page=per_page,
    )


@router.put(
    "/{voucher_id}",
    response_model=VoucherResponse,
    summary="Update voucher",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def update_voucher(
    voucher_id: str,
    data: VoucherUpdate,
    service: VoucherService = Depends(get_voucher_service),
) -> VoucherResponse:
    return await service.update_voucher(voucher_id, data)


@router.post(
    "/validate",
    response_model=VoucherValidationResponse,
    summary="Validate voucher",
)
async def validate_voucher(
    data: VoucherValidationRequest,
    user: CurrentUser,
    service: VoucherService = Depends(get_voucher_service),
) -> VoucherValidationResponse:
    return await service.validate_voucher(user.user_id, data)
