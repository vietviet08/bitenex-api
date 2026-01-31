# =============================================================================
# Driver Module - Pydantic Schemas
# =============================================================================

from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin
from app.shared.enums import DriverStatus


class DriverBase(BaseDTO):
    """Base driver fields."""

    vehicle_type: str | None = Field(default=None, max_length=50)
    vehicle_plate: str | None = Field(default=None, max_length=20)
    vehicle_model: str | None = Field(default=None, max_length=100)
    license_number: str | None = Field(default=None, max_length=50)


class DriverCreate(DriverBase):
    """Create driver profile request."""

    user_id: str


class DriverUpdate(BaseDTO):
    """Update driver profile request."""

    vehicle_type: str | None = None
    vehicle_plate: str | None = None
    vehicle_model: str | None = None


class DriverResponse(DriverBase, TimestampMixin):
    """Driver response."""

    id: str
    user_id: str
    status: DriverStatus
    is_approved: bool
    current_latitude: float | None = None
    current_longitude: float | None = None
    total_deliveries: int
    average_rating: float


class DriverLocationUpdate(BaseDTO):
    """Driver location update request."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float | None = None
    speed: float | None = None


class DriverStatusUpdate(BaseDTO):
    """Driver status update request."""

    status: DriverStatus


class NearbyDriverResponse(BaseDTO):
    """Nearby driver for dispatch."""

    driver_id: str
    user_id: str
    distance_km: float
    latitude: float
    longitude: float
    status: DriverStatus
