# =============================================================================
# Driver Module - Service Layer
# =============================================================================

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.driver.models import Driver, DriverLocation
from app.modules.driver.schemas import (
    DriverCreate,
    DriverLocationUpdate,
    DriverResponse,
    DriverStatusUpdate,
    DriverUpdate,
    NearbyDriverResponse,
)
from app.modules.order.models import Order
from app.realtime import connection_manager
from app.realtime.events import RealtimeEventType
from app.shared.enums import DriverStatus, OrderStatus
from app.shared.utils import calculate_distance


class DriverService:
    """
    Driver management service.
    Handles driver profiles, locations, and status.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_driver_by_id(self, driver_id: str) -> DriverResponse | None:
        """Get driver by ID."""
        result = await self.db.execute(
            select(Driver).where(
                Driver.id == driver_id,
                Driver.is_deleted.is_(False),
            )
        )
        driver = result.scalar_one_or_none()
        if driver is None:
            return None
        return DriverResponse.model_validate(driver)

    async def get_driver_by_user_id(self, user_id: str) -> DriverResponse | None:
        """Get driver by user ID."""
        result = await self.db.execute(
            select(Driver).where(
                Driver.user_id == user_id,
                Driver.is_deleted.is_(False),
            )
        )
        driver = result.scalar_one_or_none()
        if driver is None:
            return None
        return DriverResponse.model_validate(driver)

    async def get_driver_model_by_id(self, driver_id: str) -> Driver | None:
        """Get raw Driver ORM model by ID (for internal mutations)."""
        result = await self.db.execute(
            select(Driver).where(
                Driver.id == driver_id,
                Driver.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def create_driver(self, data: DriverCreate) -> DriverResponse:
        """Create driver profile."""
        driver = Driver(
            user_id=data.user_id,
            vehicle_type=data.vehicle_type,
            vehicle_plate=data.vehicle_plate,
            vehicle_model=data.vehicle_model,
            license_number=data.license_number,
        )
        self.db.add(driver)
        await self.db.flush()
        await self.db.refresh(driver)
        return DriverResponse.model_validate(driver)

    async def update_driver(
        self,
        driver_id: str,
        data: DriverUpdate,
    ) -> DriverResponse:
        """Update driver profile."""
        driver = await self.get_driver_model_by_id(driver_id)
        if driver is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Driver", driver_id)

        if data.vehicle_type is not None:
            driver.vehicle_type = data.vehicle_type
        if data.vehicle_plate is not None:
            driver.vehicle_plate = data.vehicle_plate
        if data.vehicle_model is not None:
            driver.vehicle_model = data.vehicle_model

        await self.db.flush()
        await self.db.refresh(driver)
        return DriverResponse.model_validate(driver)

    async def update_status(
        self,
        driver_id: str,
        data: DriverStatusUpdate,
    ) -> DriverResponse:
        """Update driver availability status."""
        driver = await self.get_driver_model_by_id(driver_id)
        if driver is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Driver", driver_id)

        driver.status = (
            data.status.value
            if isinstance(data.status, DriverStatus)
            else DriverStatus(data.status).value
        )
        await self.db.flush()
        await self.db.refresh(driver)
        return DriverResponse.model_validate(driver)

    async def update_location(
        self,
        driver_id: str,
        data: DriverLocationUpdate,
    ) -> None:
        """Update driver's current location."""
        driver = await self.get_driver_model_by_id(driver_id)
        if driver is None:
            return

        # Update current location on driver record
        driver.current_latitude = data.latitude
        driver.current_longitude = data.longitude

        # Persist a historical record
        location_record = DriverLocation(
            driver_id=driver_id,
            latitude=data.latitude,
            longitude=data.longitude,
            accuracy=data.accuracy,
            speed=data.speed,
        )
        self.db.add(location_record)
        await self.db.flush()
        await self._emit_active_order_location(driver, data)

    async def _emit_active_order_location(
        self,
        driver: Driver,
        data: DriverLocationUpdate,
    ) -> None:
        """Push the latest driver GPS point to users with active deliveries."""
        result = await self.db.execute(
            select(Order).where(
                Order.driver_id == driver.id,
                Order.status.in_(
                    [
                        OrderStatus.PICKING_UP.value,
                        OrderStatus.DELIVERING.value,
                    ]
                ),
                Order.is_deleted.is_(False),
            )
        )
        active_orders = result.scalars().all()
        timestamp = datetime.now(timezone.utc).isoformat()
        for order in active_orders:
            await connection_manager.send_personal(
                order.user_id,
                {
                    "event": RealtimeEventType.DRIVER_LOCATION_UPDATED.value,
                    "data": {
                        "order_id": order.id,
                        "driver_id": driver.id,
                        "latitude": data.latitude,
                        "longitude": data.longitude,
                        "speed": data.speed,
                        "timestamp": timestamp,
                    },
                },
            )

    async def get_nearby_drivers(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 5.0,
    ) -> list[NearbyDriverResponse]:
        """Find available (ONLINE) drivers near a location, sorted by distance."""
        result = await self.db.execute(
            select(Driver).where(
                Driver.status == DriverStatus.ONLINE.value,
                Driver.is_approved.is_(True),
                Driver.is_deleted.is_(False),
                Driver.current_latitude.is_not(None),
                Driver.current_longitude.is_not(None),
            )
        )
        drivers = result.scalars().all()

        nearby: list[NearbyDriverResponse] = []
        fallback: list[NearbyDriverResponse] = []
        for driver in drivers:
            dist = calculate_distance(
                latitude,
                longitude,
                driver.current_latitude,  # type: ignore[arg-type]
                driver.current_longitude,  # type: ignore[arg-type]
            )
            response = NearbyDriverResponse(
                driver_id=driver.id,
                user_id=driver.user_id,
                distance_km=round(dist, 3),
                latitude=driver.current_latitude,  # type: ignore[arg-type]
                longitude=driver.current_longitude,  # type: ignore[arg-type]
                status=DriverStatus(driver.status),
            )
            fallback.append(response)
            if dist <= radius_km:
                nearby.append(response)

        if not nearby:
            nearby = fallback

        # Sort closest first
        nearby.sort(key=lambda d: d.distance_km)
        return nearby

    async def set_driver_busy(self, driver_id: str) -> None:
        """Mark driver as BUSY (assigned to an active delivery)."""
        await self.db.execute(
            update(Driver)
            .where(Driver.id == driver_id, Driver.is_deleted.is_(False))
            .values(status=DriverStatus.BUSY.value)
        )

    async def set_driver_online(self, driver_id: str) -> None:
        """Revert driver from BUSY back to ONLINE."""
        await self.db.execute(
            update(Driver)
            .where(Driver.id == driver_id, Driver.is_deleted.is_(False))
            .values(status=DriverStatus.ONLINE.value)
        )

    async def approve_driver(self, driver_id: str) -> DriverResponse:
        """Approve driver application."""
        driver = await self.get_driver_model_by_id(driver_id)
        if driver is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Driver", driver_id)
        driver.is_approved = True
        await self.db.flush()
        await self.db.refresh(driver)
        return DriverResponse.model_validate(driver)

    async def suspend_driver(self, driver_id: str, reason: str) -> None:
        """Suspend a driver."""
        driver = await self.get_driver_model_by_id(driver_id)
        if driver:
            driver.status = DriverStatus.OFFLINE.value
            driver.is_approved = False
            await self.db.flush()
