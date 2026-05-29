# =============================================================================
# Driver Module - ORM Models
# =============================================================================

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel
from app.shared.enums import DriverStatus


class Driver(BaseModel):
    """
    Driver profile extending user information.
    Contains driver-specific data like vehicle info and status.
    """

    __tablename__ = "drivers"

    # Link to user account
    user_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=DriverStatus.OFFLINE.value,
        nullable=False,
        index=True,
    )

    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Vehicle info
    vehicle_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    vehicle_plate: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    vehicle_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Documents
    license_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    license_image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Current location (updated in real-time)
    current_latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    current_longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Stats
    total_deliveries: Mapped[int] = mapped_column(default=0, nullable=False)
    average_rating: Mapped[float] = mapped_column(default=0.0, nullable=False)


class DriverLocation(BaseModel):
    """
    Historical driver location tracking.
    Used for analytics and route optimization.
    """

    __tablename__ = "driver_locations"

    driver_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)


class DriverReview(BaseModel):
    """Customer review for a driver after a completed delivery."""

    __tablename__ = "driver_reviews"

    driver_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    tip_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reviewer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewer_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
