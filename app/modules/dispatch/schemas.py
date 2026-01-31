# =============================================================================
# Dispatch Module - Pydantic Schemas
# =============================================================================

from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin
from app.shared.enums import DispatchStrategy


class DispatchRequest(BaseDTO):
    """Request to dispatch a driver for an order."""

    order_id: str
    pickup_latitude: float
    pickup_longitude: float
    strategy: DispatchStrategy = DispatchStrategy.NEAREST


class DispatchResponse(BaseDTO):
    """Dispatch assignment response."""

    assignment_id: str
    order_id: str
    driver_id: str
    status: str
    distance_km: float | None = None


class DriverAssignmentResponse(BaseDTO):
    """Driver's view of an assignment."""

    assignment_id: str
    order_id: str
    status: str
    pickup_address: str
    pickup_latitude: float
    pickup_longitude: float
    delivery_address: str
    estimated_earnings: float | None = None


class AssignmentAction(BaseDTO):
    """Driver action on assignment (accept/reject)."""

    action: str = Field(pattern="^(accept|reject)$")
    rejection_reason: str | None = None


class DispatchConfigUpdate(BaseDTO):
    """Update dispatch configuration."""

    default_strategy: DispatchStrategy | None = None
    assignment_timeout_seconds: int | None = Field(default=None, ge=30, le=300)
    max_assignment_attempts: int | None = Field(default=None, ge=1, le=10)
    search_radius_km: float | None = Field(default=None, ge=1, le=50)
    max_radius_km: float | None = Field(default=None, ge=5, le=100)


class DispatchConfigResponse(BaseDTO, TimestampMixin):
    """Dispatch configuration response."""

    id: str
    region: str
    default_strategy: DispatchStrategy
    assignment_timeout_seconds: int
    max_assignment_attempts: int
    search_radius_km: float
    max_radius_km: float
