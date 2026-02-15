# =============================================================================
# Order Module - Service Layer
# =============================================================================

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.modules.merchant.models import MenuItemOption, MenuItemOptionGroup
from app.modules.order.schemas import (
    OrderCreate,
    OrderResponse,
    OrderStatusUpdate,
    SelectedOptionInput,
)
from app.shared.enums import OrderStatus


class OrderService:
    """
    Order management service.
    Handles order lifecycle from creation to completion.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _validate_and_snapshot_options(
        self,
        menu_item_id: str,
        selected_options: list[SelectedOptionInput],
    ) -> tuple[list[dict[str, Any]], float]:
        """
        Validate selected options belong to the menu item and snapshot their details.

        Returns:
            tuple of (snapshot list, total option price delta)
        """
        if not selected_options:
            return [], 0.0

        snapshot: list[dict[str, Any]] = []
        total_delta = 0.0

        for sel in selected_options:
            # Verify option group belongs to menu item
            group_result = await self.db.execute(
                select(MenuItemOptionGroup).where(
                    MenuItemOptionGroup.id == sel.option_group_id,
                    MenuItemOptionGroup.menu_item_id == menu_item_id,
                    MenuItemOptionGroup.is_deleted.is_(False),
                )
            )
            group = group_result.scalar_one_or_none()
            if not group:
                raise ValidationError(
                    message=f"Option group '{sel.option_group_id}' not found for this menu item"
                )

            # Verify option belongs to the group
            option_result = await self.db.execute(
                select(MenuItemOption).where(
                    MenuItemOption.id == sel.option_id,
                    MenuItemOption.option_group_id == sel.option_group_id,
                    MenuItemOption.is_deleted.is_(False),
                )
            )
            option = option_result.scalar_one_or_none()
            if not option:
                raise ValidationError(
                    message=f"Option '{sel.option_id}' not found in group '{sel.option_group_id}'"
                )

            snapshot.append(
                {
                    "option_group_id": group.id,
                    "option_group_name": group.name,
                    "option_id": option.id,
                    "option_name": option.name,
                    "price_delta": option.price_delta,
                }
            )
            total_delta += option.price_delta

        return snapshot, total_delta

    async def create_order(
        self,
        user_id: str,
        data: OrderCreate,
    ) -> OrderResponse:
        """
        Create a new order.

        Steps:
        1. Validate merchant is active
        2. Validate menu items exist and are available
        3. Validate and snapshot selected options per item
        4. Calculate totals (base_price + option_deltas) * quantity
        5. Create order and items with selected_options JSON
        6. Emit OrderCreatedEvent
        """
        # TODO: Implement full order creation
        # For each item in data.items:
        #   - Fetch MenuItem, verify it belongs to merchant and is available
        #   - Call _validate_and_snapshot_options for selected_options
        #   - Compute item price = menu_item.price + options_delta
        #   - Compute item subtotal = price * quantity
        #   - Create OrderItem with selected_options=json.dumps(snapshot)
        raise NotImplementedError()

    async def get_order_by_id(self, order_id: str) -> OrderResponse | None:
        """Get order by ID."""
        # TODO: Implement
        raise NotImplementedError()

    async def get_order_by_number(self, order_number: str) -> OrderResponse | None:
        """Get order by order number."""
        # TODO: Implement
        raise NotImplementedError()

    async def update_status(
        self,
        order_id: str,
        data: OrderStatusUpdate,
        changed_by: str | None = None,
    ) -> OrderResponse:
        """
        Update order status.

        Validates status transitions and emits events.
        """
        # TODO: Implement
        # 1. Validate status transition
        # 2. Update order status
        # 3. Create status history entry
        # 4. Emit OrderStatusChangedEvent
        raise NotImplementedError()

    async def get_user_orders(
        self,
        user_id: str,
        status: OrderStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[OrderResponse], int]:
        """Get orders for a user."""
        # TODO: Implement
        raise NotImplementedError()

    async def get_merchant_orders(
        self,
        merchant_id: str,
        status: OrderStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[OrderResponse], int]:
        """Get orders for a merchant."""
        # TODO: Implement
        raise NotImplementedError()

    async def get_driver_orders(
        self,
        driver_id: str,
        status: OrderStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[OrderResponse], int]:
        """Get orders for a driver."""
        # TODO: Implement
        raise NotImplementedError()

    async def cancel_order(
        self,
        order_id: str,
        reason: str,
        cancelled_by: str,
    ) -> OrderResponse:
        """Cancel an order."""
        # TODO: Implement
        # 1. Validate order can be cancelled
        # 2. Update status
        # 3. Trigger refund if paid
        # 4. Notify parties
        raise NotImplementedError()

    async def assign_driver(
        self,
        order_id: str,
        driver_id: str,
    ) -> OrderResponse:
        """Assign driver to order."""
        # TODO: Implement
        raise NotImplementedError()

    def _validate_status_transition(
        self,
        current: OrderStatus,
        new: OrderStatus,
    ) -> bool:
        """Validate if status transition is allowed."""
        # Define allowed transitions
        allowed_transitions: dict[OrderStatus, list[OrderStatus]] = {
            OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
            OrderStatus.CONFIRMED: [OrderStatus.PREPARING, OrderStatus.CANCELLED],
            OrderStatus.PREPARING: [OrderStatus.READY, OrderStatus.CANCELLED],
            OrderStatus.READY: [OrderStatus.PICKING_UP, OrderStatus.CANCELLED],
            OrderStatus.PICKING_UP: [OrderStatus.DELIVERING],
            OrderStatus.DELIVERING: [OrderStatus.DELIVERED],
            OrderStatus.DELIVERED: [],
            OrderStatus.CANCELLED: [OrderStatus.REFUNDED],
            OrderStatus.REFUNDED: [],
        }

        return new in allowed_transitions.get(current, [])

