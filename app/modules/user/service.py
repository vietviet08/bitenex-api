# =============================================================================
# User Module - Service Layer
# =============================================================================

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.user.models import User, UserAddress
from app.modules.user.schemas import (
    AddressCreate,
    AddressResponse,
    AdminUserUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)


class UserService:
    """
    User management service.
    Handles user CRUD operations and profile management.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_id(self, user_id: str) -> UserResponse:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id, User.is_deleted.is_(False)
            )  # noqa: E712
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)
        return UserResponse.model_validate(user)

    async def get_user_by_email(self, email: str) -> UserResponse | None:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(
                User.email == email, User.is_deleted.is_(False)
            )  # noqa: E712
        )
        user = result.scalar_one_or_none()
        if not user:
            return None
        return UserResponse.model_validate(user)

    async def create_user(self, data: UserCreate) -> UserResponse:
        """Create a new user."""
        user = User(
            email=data.email,
            full_name=data.full_name,
            phone=data.phone,
            password_hash=data.password,  # NOTE: caller should hash before passing
            role=data.role.value if hasattr(data.role, "value") else data.role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return UserResponse.model_validate(user)

    async def update_user(self, user_id: str, data: UserUpdate) -> UserResponse:
        """Update user profile."""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id, User.is_deleted.is_(False)
            )  # noqa: E712
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.commit()
        await self.db.refresh(user)
        return UserResponse.model_validate(user)

    async def delete_user(self, user_id: str) -> None:
        """Soft delete user."""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id, User.is_deleted.is_(False)
            )  # noqa: E712
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)

        user.soft_delete()
        await self.db.commit()

    async def list_users(
        self,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[UserResponse], int]:
        """List users with pagination."""
        query = select(User).where(User.is_deleted == False)  # noqa: E712

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        query = query.order_by(User.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        users = result.scalars().all()

        return [UserResponse.model_validate(u) for u in users], total

    # =========================================================================
    # Admin user management
    # =========================================================================
    async def admin_list_users(
        self,
        search: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[UserResponse], int]:
        """List users for admin with search, role and status filters."""
        query = select(User).where(User.is_deleted == False)  # noqa: E712

        # Search by name or email
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    User.full_name.ilike(search_term),
                    User.email.ilike(search_term),
                )
            )

        # Filter by role
        if role:
            query = query.where(User.role == role)

        # Filter by active status
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        # Count total matching
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        query = query.order_by(User.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        users = result.scalars().all()

        return [UserResponse.model_validate(u) for u in users], total

    async def admin_update_user(
        self, user_id: str, data: AdminUserUpdate
    ) -> UserResponse:
        """Admin update user — can change role, active status, etc."""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id, User.is_deleted.is_(False)
            )  # noqa: E712
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(value, "value"):
                value = value.value
            setattr(user, field, value)

        await self.db.commit()
        await self.db.refresh(user)
        return UserResponse.model_validate(user)

    async def set_user_active(self, user_id: str, *, is_active: bool) -> None:
        """Activate or deactivate a user."""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id, User.is_deleted.is_(False)
            )  # noqa: E712
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", user_id)

        user.is_active = is_active
        await self.db.commit()

    # =========================================================================
    # Address management
    # =========================================================================
    async def add_address(
        self,
        user_id: str,
        data: AddressCreate,
    ) -> AddressResponse:
        """Add user address."""
        address = UserAddress(
            user_id=user_id,
            **data.model_dump(),
        )
        self.db.add(address)
        await self.db.commit()
        await self.db.refresh(address)
        return AddressResponse.model_validate(address)

    async def get_addresses(self, user_id: str) -> list[AddressResponse]:
        """Get user's addresses."""
        result = await self.db.execute(
            select(UserAddress).where(
                UserAddress.user_id == user_id,
                UserAddress.is_deleted == False,  # noqa: E712
            )
        )
        addresses = result.scalars().all()
        return [AddressResponse.model_validate(a) for a in addresses]

    async def delete_address(self, user_id: str, address_id: str) -> None:
        """Delete user address."""
        result = await self.db.execute(
            select(UserAddress).where(
                UserAddress.id == address_id,
                UserAddress.user_id == user_id,
                UserAddress.is_deleted == False,  # noqa: E712
            )
        )
        address = result.scalar_one_or_none()
        if not address:
            raise NotFoundError("Address", address_id)

        address.soft_delete()
        await self.db.commit()

