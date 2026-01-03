# =============================================================================
# User Module - Service Layer
# =============================================================================

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    AddressCreate,
    AddressResponse,
)


class UserService:
    """
    User management service.
    Handles user CRUD operations and profile management.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_id(self, user_id: str) -> UserResponse | None:
        """Get user by ID."""
        # TODO: Implement
        raise NotImplementedError()
    
    async def get_user_by_email(self, email: str) -> UserResponse | None:
        """Get user by email."""
        # TODO: Implement
        raise NotImplementedError()
    
    async def create_user(self, data: UserCreate) -> UserResponse:
        """Create a new user."""
        # TODO: Implement
        raise NotImplementedError()
    
    async def update_user(self, user_id: str, data: UserUpdate) -> UserResponse:
        """Update user profile."""
        # TODO: Implement
        raise NotImplementedError()
    
    async def delete_user(self, user_id: str) -> None:
        """Soft delete user."""
        # TODO: Implement
        pass
    
    async def list_users(
        self,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[UserResponse], int]:
        """List users with pagination."""
        # TODO: Implement
        raise NotImplementedError()
    
    # Address management
    async def add_address(
        self,
        user_id: str,
        data: AddressCreate,
    ) -> AddressResponse:
        """Add user address."""
        # TODO: Implement
        raise NotImplementedError()
    
    async def get_addresses(self, user_id: str) -> list[AddressResponse]:
        """Get user's addresses."""
        # TODO: Implement
        raise NotImplementedError()
    
    async def delete_address(self, user_id: str, address_id: str) -> None:
        """Delete user address."""
        # TODO: Implement
        pass
