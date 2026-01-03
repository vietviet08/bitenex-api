# =============================================================================
# Order Module - Service Layer
# =============================================================================

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.order.schemas import (
    OrderCreate,
    OrderResponse,
    OrderStatusUpdate,
    OrderListResponse,
)
from app.shared.enums import OrderStatus


class OrderService:
    """
    Order management service.
    Handles order lifecycle from creation to completion.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
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
        3. Calculate totals
        4. Create order and items
        5. Emit OrderCreatedEvent
        """
        # TODO: Implement
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
        allowed_transitions = {
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
