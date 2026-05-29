# =============================================================================
# Dispatch Module - Service Layer
# =============================================================================

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dispatch.models import DispatchAssignment
from app.modules.dispatch.schemas import (
    AssignmentAction,
    DispatchRequest,
    DispatchResponse,
    DriverAssignmentResponse,
)
from app.modules.driver.service import DriverService
from app.modules.order.models import Order
from app.shared.enums import DispatchStrategy, DriverStatus, OrderStatus

logger = logging.getLogger(__name__)

# Default assignment timeout in seconds when no DispatchConfig row exists
_DEFAULT_TIMEOUT_SECONDS = 60


class DispatchService:
    """
    Driver dispatch service.
    Handles automatic and manual driver assignment for orders.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._driver_service = DriverService(db)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def dispatch_order(
        self,
        request: DispatchRequest,
    ) -> DispatchResponse:
        """
        Find and assign the nearest available driver for an order.

        Steps:
        1. Find nearby available drivers sorted by proximity
        2. For each candidate, create a PENDING assignment and notify via Socket.IO
        3. Wait up to _DEFAULT_TIMEOUT_SECONDS for the driver to respond
        4. On accept → mark ACCEPTED, set order driver, transition order to PICKING_UP
        5. On reject / timeout → mark REJECTED/EXPIRED, try next driver
        """
        nearby = await self._driver_service.get_nearby_drivers(
            request.pickup_latitude,
            request.pickup_longitude,
        )

        if not nearby:
            raise ValueError("No available drivers nearby")

        for candidate in nearby:
            assignment = DispatchAssignment(
                order_id=request.order_id,
                driver_id=candidate.driver_id,
                status="PENDING",
                strategy=request.strategy.value,
                distance_km=candidate.distance_km,
            )
            self.db.add(assignment)
            await self.db.flush()
            await self.db.refresh(assignment)

            # Emit assignment to the driver via Socket.IO room
            await self._emit_assignment(assignment, candidate.user_id, request)

            # Schedule timeout task in background (non-blocking)
            asyncio.create_task(
                self._handle_timeout(assignment.id, candidate.driver_id)
            )

            # Return immediately – the driver will respond asynchronously
            return DispatchResponse(
                assignment_id=assignment.id,
                order_id=request.order_id,
                driver_id=candidate.driver_id,
                status="PENDING",
                distance_km=candidate.distance_km,
            )

        raise ValueError("All dispatch attempts exhausted")

    async def find_best_driver(
        self,
        latitude: float,
        longitude: float,
        strategy: DispatchStrategy = DispatchStrategy.NEAREST,
    ) -> str | None:
        """
        Find the best driver ID for a pickup location.
        Currently only NEAREST strategy is implemented.
        """
        nearby = await self._driver_service.get_nearby_drivers(latitude, longitude)
        if not nearby:
            return None
        return nearby[0].driver_id

    async def get_pending_assignments(
        self,
        driver_id: str,
    ) -> list[DriverAssignmentResponse]:
        """Get all PENDING assignments for a driver."""
        result = await self.db.execute(
            select(DispatchAssignment).where(
                DispatchAssignment.driver_id == driver_id,
                DispatchAssignment.status == "PENDING",
                DispatchAssignment.is_deleted.is_(False),
            )
        )
        assignments = result.scalars().all()

        responses: list[DriverAssignmentResponse] = []
        for a in assignments:
            order = await self._get_order(a.order_id)
            if order is None:
                continue
            responses.append(
                DriverAssignmentResponse(
                    assignment_id=a.id,
                    order_id=a.order_id,
                    status=a.status,
                    pickup_address=order.delivery_address or "",
                    pickup_latitude=order.delivery_latitude or 0.0,
                    pickup_longitude=order.delivery_longitude or 0.0,
                    delivery_address=order.delivery_address or "",
                    estimated_earnings=float(order.delivery_fee or 0),
                )
            )
        return responses

    async def respond_to_assignment(
        self,
        assignment_id: str,
        driver_id: str,
        action: AssignmentAction,
    ) -> DispatchResponse:
        """
        Driver responds (accept / reject) to an assignment.

        Accept:
        - Set assignment → ACCEPTED
        - Set driver → BUSY
        - Set order driver_id, transition to PICKING_UP

        Reject:
        - Set assignment → REJECTED
        - Revert driver → ONLINE
        - Auto-dispatch to next nearest driver
        """
        assignment = await self._get_assignment(assignment_id)

        if assignment.status != "PENDING":
            return DispatchResponse(
                assignment_id=assignment.id,
                order_id=assignment.order_id,
                driver_id=assignment.driver_id,
                status=assignment.status,
                distance_km=assignment.distance_km,
            )

        elapsed = (
            datetime.now(timezone.utc) - assignment.created_at.replace(tzinfo=timezone.utc)
        ).seconds
        assignment.response_time_seconds = elapsed

        if action.action == "accept":
            assignment.status = "ACCEPTED"
            await self.db.flush()

            # Mark driver busy
            await self._driver_service.set_driver_busy(driver_id)

            # Assign driver to order and transition to PICKING_UP
            order = await self._get_order(assignment.order_id)
            if order:
                order.driver_id = driver_id
                from app.shared.enums import OrderStatus
                if order.status == OrderStatus.READY.value:
                    order.status = OrderStatus.PICKING_UP.value
            await self.db.flush()

            return DispatchResponse(
                assignment_id=assignment.id,
                order_id=assignment.order_id,
                driver_id=driver_id,
                status="ACCEPTED",
                distance_km=assignment.distance_km,
            )

        else:  # reject
            assignment.status = "REJECTED"
            assignment.rejection_reason = action.rejection_reason
            await self.db.flush()

            # Revert driver to ONLINE
            await self._driver_service.set_driver_online(driver_id)

            # Try next driver
            order = await self._get_order(assignment.order_id)
            if order and order.delivery_latitude and order.delivery_longitude:
                try:
                    return await self.dispatch_order(
                        DispatchRequest(
                            order_id=assignment.order_id,
                            pickup_latitude=order.delivery_latitude,
                            pickup_longitude=order.delivery_longitude,
                        )
                    )
                except ValueError:
                    logger.warning(
                        f"No more drivers available for order {assignment.order_id}"
                    )

            return DispatchResponse(
                assignment_id=assignment.id,
                order_id=assignment.order_id,
                driver_id=driver_id,
                status="REJECTED",
                distance_km=assignment.distance_km,
            )

    async def cancel_assignment(
        self,
        assignment_id: str,
        reason: str,
    ) -> None:
        """Cancel a pending assignment."""
        assignment = await self._get_assignment(assignment_id)
        if assignment.status == "PENDING":
            assignment.status = "CANCELLED"
            await self.db.flush()

    async def reassign_order(
        self,
        order_id: str,
        reason: str,
    ) -> DispatchResponse:
        """
        Reassign an order to a different driver.
        Used when current driver can't complete delivery.
        """
        order = await self._get_order(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")

        if order.delivery_latitude is None or order.delivery_longitude is None:
            raise ValueError("Order has no delivery coordinates")

        return await self.dispatch_order(
            DispatchRequest(
                order_id=order_id,
                pickup_latitude=order.delivery_latitude,
                pickup_longitude=order.delivery_longitude,
            )
        )

    async def manual_assign(
        self,
        order_id: str,
        driver_id: str,
        assigned_by: str,
    ) -> DispatchResponse:
        """
        Manually assign a driver to an order (admin).
        """
        assignment = DispatchAssignment(
            order_id=order_id,
            driver_id=driver_id,
            status="ACCEPTED",
            strategy=DispatchStrategy.MANUAL.value,
        )
        self.db.add(assignment)
        await self.db.flush()

        order = await self._get_order(order_id)
        if order:
            order.driver_id = driver_id
            if order.status == OrderStatus.READY.value:
                order.status = OrderStatus.PICKING_UP.value

        await self._driver_service.set_driver_busy(driver_id)
        await self.db.flush()

        return DispatchResponse(
            assignment_id=assignment.id,
            order_id=order_id,
            driver_id=driver_id,
            status="ACCEPTED",
        )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _get_order(self, order_id: str) -> Order | None:
        result = await self.db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _get_assignment(self, assignment_id: str) -> DispatchAssignment:
        result = await self.db.execute(
            select(DispatchAssignment).where(
                DispatchAssignment.id == assignment_id,
                DispatchAssignment.is_deleted.is_(False),
            )
        )
        assignment = result.scalar_one_or_none()
        if assignment is None:
            raise ValueError(f"Assignment {assignment_id} not found")
        return assignment

    async def _emit_assignment(
        self,
        assignment: DispatchAssignment,
        driver_user_id: str,
        request: DispatchRequest,
    ) -> None:
        """Emit a dispatch.assignment event to the driver via Socket.IO."""
        from app.realtime import connection_manager
        from app.realtime.events import RealtimeEventType

        order = await self._get_order(request.order_id)
        estimated_earnings = float(order.delivery_fee) if order else 0.0

        payload = {
            "event": RealtimeEventType.DISPATCH_ASSIGNMENT.value,
            "data": {
                "assignment_id": assignment.id,
                "order_id": assignment.order_id,
                "distance_km": assignment.distance_km,
                "estimated_earnings": estimated_earnings,
                "pickup_latitude": request.pickup_latitude,
                "pickup_longitude": request.pickup_longitude,
                "delivery_address": order.delivery_address if order else "",
                "expires_in_seconds": _DEFAULT_TIMEOUT_SECONDS,
            },
        }
        await connection_manager.send_personal(driver_user_id, payload)
        logger.info(
            f"Dispatched assignment {assignment.id} to driver user {driver_user_id}"
        )

    async def _handle_timeout(self, assignment_id: str, driver_id: str) -> None:
        """
        Background task: expire assignment after timeout and re-dispatch.
        Uses a fresh DB session to avoid SQLAlchemy session conflicts.
        """
        await asyncio.sleep(_DEFAULT_TIMEOUT_SECONDS)

        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(DispatchAssignment).where(
                        DispatchAssignment.id == assignment_id,
                        DispatchAssignment.is_deleted.is_(False),
                    )
                )
                assignment = result.scalar_one_or_none()
                if assignment is None or assignment.status != "PENDING":
                    return

                assignment.status = "EXPIRED"
                await session.flush()

                # Revert driver to ONLINE
                driver_service = DriverService(session)
                await driver_service.set_driver_online(driver_id)

                # Attempt re-dispatch
                order_result = await session.execute(
                    select(Order).where(
                        Order.id == assignment.order_id,
                        Order.is_deleted.is_(False),
                    )
                )
                order = order_result.scalar_one_or_none()
                if (
                    order
                    and order.delivery_latitude
                    and order.delivery_longitude
                    and order.status == OrderStatus.READY.value
                ):
                    dispatch_svc = DispatchService(session)
                    try:
                        await dispatch_svc.dispatch_order(
                            DispatchRequest(
                                order_id=assignment.order_id,
                                pickup_latitude=order.delivery_latitude,
                                pickup_longitude=order.delivery_longitude,
                            )
                        )
                    except ValueError:
                        logger.warning(
                            f"Timeout re-dispatch failed for order {assignment.order_id}"
                        )

                await session.commit()
            except Exception as exc:
                logger.exception(
                    f"Error handling assignment timeout {assignment_id}: {exc}"
                )
                await session.rollback()
