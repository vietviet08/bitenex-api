# =============================================================================
# Driver Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdmin, require_role
from app.modules.driver.schemas import (
    DriverCreate,
    DriverLocationUpdate,
    DriverResponse,
    DriverStatusUpdate,
    DriverUpdate,
    NearbyDriverResponse,
)
from app.modules.driver.service import DriverService
from app.shared.dto import MessageResponse
from app.shared.enums import Role

router = APIRouter(
    prefix="/drivers",
    tags=["Drivers"],
)


async def get_driver_service(db: AsyncSession = Depends(get_db)) -> DriverService:
    return DriverService(db)


@router.get(
    "/me",
    response_model=DriverResponse,
    summary="Get my driver profile",
    dependencies=[Depends(require_role(Role.DRIVER))],
)
async def get_my_driver_profile(
    user: CurrentUser,
    service: DriverService = Depends(get_driver_service),
) -> DriverResponse:
    """Get current driver's profile."""
    return await service.get_driver_by_user_id(user.user_id)


@router.patch(
    "/me",
    response_model=DriverResponse,
    summary="Update my driver profile",
    dependencies=[Depends(require_role(Role.DRIVER))],
)
async def update_my_driver_profile(
    data: DriverUpdate,
    user: CurrentUser,
    service: DriverService = Depends(get_driver_service),
) -> DriverResponse:
    """Update current driver's profile."""
    driver = await service.get_driver_by_user_id(user.user_id)
    return await service.update_driver(driver.id, data)


@router.post(
    "/me/location",
    response_model=MessageResponse,
    summary="Update location",
    dependencies=[Depends(require_role(Role.DRIVER))],
)
async def update_location(
    data: DriverLocationUpdate,
    user: CurrentUser,
    service: DriverService = Depends(get_driver_service),
) -> MessageResponse:
    """Update driver's current location."""
    driver = await service.get_driver_by_user_id(user.user_id)
    await service.update_location(driver.id, data)
    return MessageResponse(message="Location updated")


@router.post(
    "/me/status",
    response_model=DriverResponse,
    summary="Update status",
    dependencies=[Depends(require_role(Role.DRIVER))],
)
async def update_status(
    data: DriverStatusUpdate,
    user: CurrentUser,
    service: DriverService = Depends(get_driver_service),
) -> DriverResponse:
    """Update driver's availability status (online/offline)."""
    driver = await service.get_driver_by_user_id(user.user_id)
    return await service.update_status(driver.id, data)


@router.get(
    "/nearby",
    response_model=list[NearbyDriverResponse],
    summary="Get nearby drivers",
    dependencies=[RequireAdmin],
)
async def get_nearby_drivers(
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
    service: DriverService = Depends(get_driver_service),
) -> list[NearbyDriverResponse]:
    """Find available drivers near a location. Admin/internal use."""
    return await service.get_nearby_drivers(latitude, longitude, radius_km)


@router.get(
    "/{driver_id}",
    response_model=DriverResponse,
    summary="Get driver by ID",
    dependencies=[RequireAdmin],
)
async def get_driver(
    driver_id: str,
    service: DriverService = Depends(get_driver_service),
) -> DriverResponse:
    """Get driver by ID. Admin only."""
    return await service.get_driver_by_id(driver_id)


@router.post(
    "/{driver_id}/approve",
    response_model=DriverResponse,
    summary="Approve driver",
    dependencies=[RequireAdmin],
)
async def approve_driver(
    driver_id: str,
    service: DriverService = Depends(get_driver_service),
) -> DriverResponse:
    """Approve a driver application. Admin only."""
    return await service.approve_driver(driver_id)
