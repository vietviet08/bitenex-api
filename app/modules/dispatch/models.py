# =============================================================================
# Dispatch Module - ORM Models
# =============================================================================

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel
from app.shared.enums import DispatchStrategy


class DispatchAssignment(BaseModel):
    """
    Driver dispatch assignment for an order.
    Tracks assignment attempts and driver responses.
    """
    
    __tablename__ = "dispatch_assignments"
    
    order_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    
    driver_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    
    # Assignment status
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False,
    )  # PENDING, ACCEPTED, REJECTED, EXPIRED
    
    # Strategy used
    strategy: Mapped[str] = mapped_column(
        String(20),
        default=DispatchStrategy.NEAREST.value,
        nullable=False,
    )
    
    # Distance from driver to pickup
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Response
    response_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class DispatchConfig(BaseModel):
    """
    Dispatch configuration settings.
    Controls how drivers are assigned to orders.
    """
    
    __tablename__ = "dispatch_configs"
    
    # Region-specific config
    region: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    
    # Strategy
    default_strategy: Mapped[str] = mapped_column(
        String(20),
        default=DispatchStrategy.NEAREST.value,
        nullable=False,
    )
    
    # Timeouts
    assignment_timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
    )
    
    max_assignment_attempts: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    
    # Radius
    search_radius_km: Mapped[float] = mapped_column(
        Float,
        default=5.0,
        nullable=False,
    )
    
    max_radius_km: Mapped[float] = mapped_column(
        Float,
        default=15.0,
        nullable=False,
    )
