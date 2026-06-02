# =============================================================================
# User Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdmin, RequireUser
from app.modules.user.schemas import (
    AddressCreate,
    AddressResponse,
    AdminUserListResponse,
    AdminUserUpdate,
    UserResponse,
    UserUpdate,
)
from app.modules.user.service import UserService
from app.shared.dto import MessageResponse

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[RequireUser],
)


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get(
    "/profile",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    user: CurrentUser,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Get the current authenticated user's profile."""
    return await service.get_user_by_id(user.user_id)


@router.patch(
    "/profile",
    response_model=UserResponse,
    summary="Update current user profile",
)
async def update_me(
    data: UserUpdate,
    user: CurrentUser,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Update the current user's profile."""
    return await service.update_user(user.user_id, data)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    dependencies=[RequireAdmin],
)
async def get_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Get user by ID. Admin only."""
    return await service.get_user_by_id(user_id)


# Address endpoints
@router.get(
    "/profile/addresses",
    response_model=list[AddressResponse],
    summary="Get my addresses",
)
async def get_my_addresses(
    user: CurrentUser,
    service: UserService = Depends(get_user_service),
) -> list[AddressResponse]:
    """Get current user's saved addresses."""
    return await service.get_addresses(user.user_id)


@router.post(
    "/profile/addresses",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add address",
)
async def add_address(
    data: AddressCreate,
    user: CurrentUser,
    service: UserService = Depends(get_user_service),
) -> AddressResponse:
    """Add a new address for the current user."""
    return await service.add_address(user.user_id, data)


@router.delete(
    "/profile/addresses/{address_id}",
    response_model=MessageResponse,
    summary="Delete address",
)
async def delete_address(
    address_id: str,
    user: CurrentUser,
    service: UserService = Depends(get_user_service),
) -> MessageResponse:
    """Delete a saved address."""
    await service.delete_address(user.user_id, address_id)
    return MessageResponse(message="Address deleted successfully")


# =============================================================================
# Admin User Management Endpoints
# =============================================================================
@router.get(
    "/admin/list",
    response_model=AdminUserListResponse,
    summary="Admin list users",
    dependencies=[RequireAdmin],
)
async def admin_list_users(
    search: str | None = Query(default=None, description="Search by name or email"),
    role: str | None = Query(default=None, description="Filter by role"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: UserService = Depends(get_user_service),
) -> AdminUserListResponse:
    """List users for admin management with search and filters."""
    items, total = await service.admin_list_users(
        search=search,
        role=role,
        is_active=is_active,
        page=page,
        per_page=per_page,
    )
    return AdminUserListResponse(items=items, total=total)


@router.patch(
    "/admin/{user_id}",
    response_model=UserResponse,
    summary="Admin update user",
    dependencies=[RequireAdmin],
)
async def admin_update_user(
    user_id: str,
    data: AdminUserUpdate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Update user details (role, active status, etc.) — Admin only."""
    return await service.admin_update_user(user_id, data)


@router.post(
    "/admin/{user_id}/deactivate",
    response_model=MessageResponse,
    summary="Deactivate user",
    dependencies=[RequireAdmin],
)
async def admin_deactivate_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
) -> MessageResponse:
    """Deactivate a user account. Admin only."""
    await service.set_user_active(user_id, is_active=False)
    return MessageResponse(message="User deactivated successfully")


@router.post(
    "/admin/{user_id}/activate",
    response_model=MessageResponse,
    summary="Activate user",
    dependencies=[RequireAdmin],
)
async def admin_activate_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
) -> MessageResponse:
    """Activate a user account. Admin only."""
    await service.set_user_active(user_id, is_active=True)
    return MessageResponse(message="User activated successfully")


@router.get(
    "/admin/{user_id}/addresses",
    response_model=list[AddressResponse],
    summary="Get user addresses",
    dependencies=[RequireAdmin],
)
async def admin_get_user_addresses(
    user_id: str,
    service: UserService = Depends(get_user_service),
) -> list[AddressResponse]:
    """Get user's saved addresses. Admin only."""
    return await service.get_addresses(user_id)
