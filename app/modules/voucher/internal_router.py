# =============================================================================
# Voucher Module - Internal Router (Admin & n8n)
# =============================================================================

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdmin, RequireInternalService
from app.modules.voucher.schemas import (
    AdminVoucherListResponse,
    IssueVoucherRequest,
    IssueVoucherResponse,
    VoucherCreateRequest,
    VoucherResponse,
    VoucherUpdateRequest,
)
from app.modules.voucher.service import VoucherService
from app.shared.dto import MessageResponse
from app.shared.enums import VoucherStatus

internal_router = APIRouter(
    prefix="/internal/vouchers",
    tags=["Internal — Vouchers"],
)


def get_voucher_service(
    db: AsyncSession = Depends(get_db),
) -> VoucherService:
    return VoucherService(db)


# =============================================================================
# n8n Integration Endpoints
# =============================================================================
@internal_router.post(
    "/issue",
    response_model=IssueVoucherResponse,
    status_code=status.HTTP_200_OK,
    summary="Issue voucher for user",
    dependencies=[RequireInternalService],
)
async def issue_voucher(
    req: IssueVoucherRequest,
    service: VoucherService = Depends(get_voucher_service),
) -> IssueVoucherResponse:
    """
    Issue a voucher to a user (for n8n workflows).
    Returns existing active voucher if one exists for this code+user.
    """
    return await service.issue_voucher(
        user_id=req.userId,
        code=req.voucherCode,
        discount_amount=req.discountAmount,
        expires_in_days=req.expiresInDays,
        reason=req.reason,
    )


# =============================================================================
# Admin Management Endpoints
# =============================================================================
@internal_router.get(
    "/admin/list",
    response_model=AdminVoucherListResponse,
    summary="Admin list all vouchers",
    dependencies=[RequireAdmin],
)
async def admin_list_vouchers(
    status_filter: VoucherStatus | None = Query(default=None, alias="status"),
    user_id: str | None = Query(default=None),
    code: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: VoucherService = Depends(get_voucher_service),
) -> AdminVoucherListResponse:
    """List all vouchers with optional filters."""
    items, total = await service.list_all_vouchers(
        status_filter=status_filter,
        user_id_filter=user_id,
        code_filter=code,
        page=page,
        per_page=per_page,
    )
    return AdminVoucherListResponse(items=items, total=total, page=page, per_page=per_page)


@internal_router.post(
    "/admin/create",
    response_model=VoucherResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin create voucher",
    dependencies=[RequireAdmin],
)
async def admin_create_voucher(
    data: VoucherCreateRequest,
    user: CurrentUser,
    service: VoucherService = Depends(get_voucher_service),
) -> VoucherResponse:
    """Create a manual voucher (admin only)."""
    return await service.create_voucher(user.user_id, data)


@internal_router.patch(
    "/admin/{voucher_id}",
    response_model=VoucherResponse,
    summary="Admin update voucher",
    dependencies=[RequireAdmin],
)
async def admin_update_voucher(
    voucher_id: UUID,
    data: VoucherUpdateRequest,
    user: CurrentUser,
    service: VoucherService = Depends(get_voucher_service),
) -> VoucherResponse:
    """Update a voucher (admin only)."""
    return await service.update_voucher(str(voucher_id), user.user_id, data)


@internal_router.delete(
    "/admin/{voucher_id}",
    response_model=MessageResponse,
    summary="Admin deactivate voucher",
    dependencies=[RequireAdmin],
)
async def admin_deactivate_voucher(
    voucher_id: UUID,
    user: CurrentUser,
    service: VoucherService = Depends(get_voucher_service),
) -> MessageResponse:
    """Deactivate a voucher (admin only)."""
    await service.deactivate_voucher(str(voucher_id), user.user_id)
    return MessageResponse(message="Voucher deactivated")
