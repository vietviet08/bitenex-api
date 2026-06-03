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


class AdminDriverResponse(DriverResponse):
    """Admin driver response with user details."""

    user_name: str | None = None
    user_email: str | None = None
    user_phone: str | None = None


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


class DriverReviewResponse(BaseDTO, TimestampMixin):
    """Driver review response."""

    id: str
    driver_id: str
    user_id: str
    order_id: str
    order_number: str | None = None
    rating: int
    comment: str | None = None
    tip_amount: float
    reviewer_name: str | None = None
    reviewer_avatar: str | None = None


class DriverRatingSummaryResponse(BaseDTO):
    """Driver rating summary with recent feedback."""

    average_rating: float
    total_ratings: int
    rating_distribution: dict[str, int]
    recent_feedback: list[DriverReviewResponse]


class DriverEarningActivityResponse(BaseDTO):
    """Single earning activity."""

    id: str
    order_id: str
    order_number: str
    merchant_name: str
    amount: float
    delivery_fee: float
    tip_amount: float
    delivered_at: str


class DriverEarningsResponse(BaseDTO):
    """Driver earnings summary."""

    period: str
    total: float
    delivery_total: float
    tip_total: float
    trips: int
    chart: list[dict[str, object]]
    recent_activity: list[DriverEarningActivityResponse]
