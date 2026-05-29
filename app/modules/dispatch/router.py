# =============================================================================
# Dispatch Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdmin, RequireDriver
from app.core.exceptions import NotFoundError
from app.modules.dispatch.schemas import (
    AssignmentAction,
    DispatchRequest,
    DispatchResponse,
    DriverAssignmentResponse,
)
from app.modules.dispatch.service import DispatchService
from app.modules.driver.service import DriverService

router = APIRouter(
    prefix="/dispatch",
    tags=["Dispatch"],
    dependencies=[RequireDriver],
)


def get_dispatch_service(
    db: AsyncSession = Depends(get_db),
) -> DispatchService:
    return DispatchService(db)


# =============================================================================
# Internal/Admin Endpoints
# =============================================================================
@router.post(
    "",
    response_model=DispatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dispatch driver for order",
    dependencies=[RequireAdmin],
)
async def dispatch_order(
    request: DispatchRequest,
    service: DispatchService = Depends(get_dispatch_service),
) -> DispatchResponse:
    """Find and assign a driver for an order."""
    return await service.dispatch_order(request)


@router.post(
    "/manual",
    response_model=DispatchResponse,
    summary="Manual driver assignment",
    dependencies=[RequireAdmin],
)
async def manual_assign(
    order_id: str,
    driver_id: str,
    user: CurrentUser,
    service: DispatchService = Depends(get_dispatch_service),
) -> DispatchResponse:
    """Manually assign a driver to an order."""
    return await service.manual_assign(order_id, driver_id, user.user_id)


@router.post(
    "/{order_id}/reassign",
    response_model=DispatchResponse,
    summary="Reassign order",
    dependencies=[RequireAdmin],
)
async def reassign_order(
    order_id: str,
    reason: str = "",
    service: DispatchService = Depends(get_dispatch_service),
) -> DispatchResponse:
    """Reassign an order to a different driver."""
    return await service.reassign_order(order_id, reason)


# =============================================================================
# Driver Endpoints
# =============================================================================
@router.get(
    "/assignments",
    response_model=list[DriverAssignmentResponse],
    summary="Get pending assignments",
)
async def get_pending_assignments(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    service: DispatchService = Depends(get_dispatch_service),
) -> list[DriverAssignmentResponse]:
    """Get pending assignments for current driver."""
    driver = await DriverService(db).get_driver_by_user_id(user.user_id)
    if driver is None:
        raise NotFoundError("Driver", user.user_id)
    return await service.get_pending_assignments(driver.id)


@router.post(
    "/assignments/{assignment_id}/respond",
    response_model=DispatchResponse,
    summary="Respond to assignment",
)
async def respond_to_assignment(
    assignment_id: str,
    action: AssignmentAction,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    service: DispatchService = Depends(get_dispatch_service),
) -> DispatchResponse:
    """Accept or reject an assignment."""
    driver = await DriverService(db).get_driver_by_user_id(user.user_id)
    if driver is None:
        raise NotFoundError("Driver", user.user_id)
    return await service.respond_to_assignment(assignment_id, driver.id, action)
