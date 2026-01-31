from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class BaseDTO(BaseModel):
    """
    Base class for all DTOs with common configuration.
    """

    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM mode (from SQLAlchemy models)
        populate_by_name=True,  # Allow population by field name or alias
        str_strip_whitespace=True,  # Strip whitespace from strings
        use_enum_values=True,  # Use enum values instead of enum objects
    )


class MessageResponse(BaseDTO):
    """Simple message response."""

    message: str


class SuccessResponse(BaseDTO):
    """Generic success response."""

    success: bool = True
    message: str = "Operation completed successfully"


class ErrorDetail(BaseDTO):
    """Error detail structure."""

    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseDTO):
    """Standard error response."""

    error: ErrorDetail


T = TypeVar("T")


class PaginationMeta(BaseDTO):
    """Pagination metadata."""

    page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, le=100, description="Items per page")
    total_items: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")


class PaginatedResponse(BaseDTO, Generic[T]):
    """
    Paginated response wrapper.

    Usage:
        class UserListResponse(PaginatedResponse[UserDTO]):
            pass
    """

    items: list[T]
    meta: PaginationMeta


class PaginationParams(BaseDTO):
    """
    Pagination query parameters.

    Usage:
        @router.get("/users")
        async def list_users(pagination: PaginationParams = Depends()):
            ...
    """

    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.per_page


class TimestampMixin:
    """Mixin for created/updated timestamps."""

    created_at: datetime
    updated_at: datetime


class SoftDeleteMixin(BaseDTO):
    """Mixin for soft delete fields."""

    is_deleted: bool = False
    deleted_at: datetime | None = None


class IDResponse(BaseDTO):
    """Response containing just an ID."""

    id: str


class IDListResponse(BaseDTO):
    """Response containing a list of IDs."""

    ids: list[str]


class HealthCheckResponse(BaseDTO):
    """Health check response."""

    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: dict[str, str] = Field(default_factory=dict)


class SortParams(BaseDTO):
    """Sorting query parameters."""

    sort_by: str = "created_at"
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
