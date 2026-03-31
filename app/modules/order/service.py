# =============================================================================
# Order Module - Service Layer
# =============================================================================

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from app.modules.driver.models import Driver
from app.modules.merchant.models import (
    MenuItem,
    MenuItemOption,
    MenuItemOptionGroup,
    Merchant,
)
from app.modules.order.models import Order, OrderItem, OrderStatusHistory
from app.modules.order.schemas import (
    AdminOrderListItem,
    OrderCreate,
    OrderItemCreate,
    OrderItemResponse,
    OrderResponse,
    OrderStatusUpdate,
    SelectedOptionInput,
)
from app.modules.payment.models import Payment, Refund
from app.shared.enums import MerchantStatus, OrderStatus, PaymentStatus, Role
from app.shared.n8n_client import N8nClient


class OrderService:
    """
    Order management service.
    Handles order lifecycle from creation to completion.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _generate_order_number() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        suffix = uuid4().hex[:6].upper()
        return f"ORD-{ts}-{suffix}"

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

    async def _get_order_model_by_id(self, order_id: str) -> Order:
        result = await self.db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.is_deleted == False,
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError(message="Order not found")
        return order

    async def _get_order_model_by_number(self, order_number: str) -> Order:
        result = await self.db.execute(
            select(Order).where(
                Order.order_number == order_number,
                Order.is_deleted == False,
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError(message="Order not found")
        return order

    async def _get_order_items_for_orders(
        self,
        order_ids: list[str],
    ) -> dict[str, list[OrderItem]]:
        if not order_ids:
            return {}

        result = await self.db.execute(
            select(OrderItem)
            .where(
                OrderItem.order_id.in_(order_ids),
                OrderItem.is_deleted == False,
            )
            .order_by(OrderItem.created_at.asc())
        )
        grouped: dict[str, list[OrderItem]] = defaultdict(list)
        for item in result.scalars().all():
            grouped[item.order_id].append(item)
        return grouped

    async def _get_order_items(self, order_id: str) -> list[OrderItem]:
        result = await self.db.execute(
            select(OrderItem).where(
                OrderItem.order_id == order_id,
                OrderItem.is_deleted == False,
            )
        )
        return result.scalars().all()

    async def _get_merchant_id_by_user_id(self, user_id: str) -> str:
        result = await self.db.execute(
            select(Merchant.id).where(
                Merchant.user_id == user_id,
                Merchant.is_deleted == False,
            )
        )
        merchant_id = result.scalar_one_or_none()
        if not merchant_id:
            raise NotFoundError(message="Merchant profile not found")
        return merchant_id

    async def _get_driver_id_by_user_id(self, user_id: str) -> str:
        result = await self.db.execute(
            select(Driver.id).where(
                Driver.user_id == user_id,
                Driver.is_deleted == False,
            )
        )
        driver_id = result.scalar_one_or_none()
        if not driver_id:
            raise NotFoundError(message="Driver profile not found")
        return driver_id

    async def _enforce_order_access(
        self,
        order: Order,
        *,
        actor_user_id: str | None = None,
        actor_role: Role | str | None = None,
    ) -> None:
        if not actor_user_id or actor_role is None:
            return

        normalized_role = actor_role if isinstance(actor_role, Role) else Role(actor_role)
        if normalized_role == Role.ADMIN:
            return

        if normalized_role == Role.USER:
            if order.user_id != actor_user_id:
                raise AuthorizationError(message="You can only access your own orders")
            return

        if normalized_role == Role.MERCHANT:
            merchant_id = await self._get_merchant_id_by_user_id(actor_user_id)
            if order.merchant_id != merchant_id:
                raise AuthorizationError(message="You can only access your merchant orders")
            return

        if normalized_role == Role.DRIVER:
            driver_id = await self._get_driver_id_by_user_id(actor_user_id)
            if order.driver_id != driver_id:
                raise AuthorizationError(message="You can only access assigned orders")
            return

    @staticmethod
    def _to_order_response(
        order: Order,
        items: list[OrderItem],
    ) -> OrderResponse:
        response = OrderResponse.model_validate(order)
        response.items = [OrderItemResponse.model_validate(item) for item in items]
        return response

    @staticmethod
    def _to_admin_order_item(
        order: Order,
        latest_payment: Payment | None = None,
    ) -> AdminOrderListItem:
        return AdminOrderListItem(
            id=order.id,
            order_number=order.order_number,
            user_id=order.user_id,
            merchant_id=order.merchant_id,
            driver_id=order.driver_id,
            status=OrderStatus(order.status),
            subtotal=float(order.subtotal),
            delivery_fee=float(order.delivery_fee),
            tax=float(order.tax),
            discount=float(order.discount),
            total=float(order.total),
            delivery_address=order.delivery_address,
            customer_note=order.customer_note,
            created_at=order.created_at,
            updated_at=order.updated_at,
            payment_status=(
                PaymentStatus(latest_payment.status) if latest_payment is not None else None
            ),
            latest_payment_id=latest_payment.id if latest_payment is not None else None,
            latest_transaction_id=(
                latest_payment.transaction_id if latest_payment is not None else None
            ),
        )

    async def resolve_merchant_id_by_user_id(self, user_id: str) -> str:
        return await self._get_merchant_id_by_user_id(user_id)

    async def resolve_driver_id_by_user_id(self, user_id: str) -> str:
        return await self._get_driver_id_by_user_id(user_id)

    async def _list_orders(
        self,
        *,
        filters: list,
        status: OrderStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[OrderResponse], int]:
        scoped_filters = list(filters)
        if status:
            scoped_filters.append(Order.status == status.value)

        query = (
            select(Order)
            .where(*scoped_filters)
            .order_by(Order.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        count_query = select(func.count(Order.id)).where(*scoped_filters)

        orders = (await self.db.execute(query)).scalars().all()
        total = (await self.db.execute(count_query)).scalar_one()

        grouped_items = await self._get_order_items_for_orders([order.id for order in orders])
        responses = [
            self._to_order_response(order, grouped_items.get(order.id, [])) for order in orders
        ]
        return responses, total

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
        merchant_result = await self.db.execute(
            select(Merchant).where(
                Merchant.id == data.merchant_id,
                Merchant.is_deleted == False,
                Merchant.status == MerchantStatus.ACTIVE.value,
            )
        )
        merchant = merchant_result.scalar_one_or_none()
        if not merchant:
            raise NotFoundError(message="Merchant not found")

        subtotal = 0.0
        pending_items: list[tuple[OrderItemCreate, MenuItem, list[dict], float]] = []

        for requested_item in data.items:
            menu_result = await self.db.execute(
                select(MenuItem).where(
                    MenuItem.id == requested_item.menu_item_id,
                    MenuItem.merchant_id == data.merchant_id,
                    MenuItem.is_deleted == False,
                )
            )
            menu_item = menu_result.scalar_one_or_none()
            if not menu_item:
                raise ValidationError(
                    message=f"Menu item '{requested_item.menu_item_id}' not found"
                )
            if not menu_item.is_available:
                raise ValidationError(message=f"Menu item '{menu_item.name}' is unavailable")

            option_snapshot, option_delta = await self._validate_and_snapshot_options(
                menu_item.id,
                requested_item.selected_options,
            )
            unit_price = float(menu_item.price) + option_delta
            line_subtotal = unit_price * requested_item.quantity
            subtotal += line_subtotal
            pending_items.append((requested_item, menu_item, option_snapshot, unit_price))

        delivery_fee = float(merchant.delivery_fee or 0.0)
        tax = 0.0
        discount = 0.0
        total = subtotal + delivery_fee + tax - discount

        order = Order(
            order_number=self._generate_order_number(),
            user_id=user_id,
            merchant_id=data.merchant_id,
            status=OrderStatus.PENDING.value,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            tax=tax,
            discount=discount,
            total=total,
            delivery_address=data.delivery_address,
            delivery_latitude=data.delivery_latitude,
            delivery_longitude=data.delivery_longitude,
            customer_note=data.customer_note,
        )
        self.db.add(order)
        await self.db.flush()

        order_items: list[OrderItem] = []
        for requested_item, menu_item, option_snapshot, unit_price in pending_items:
            item_subtotal = unit_price * requested_item.quantity
            order_item = OrderItem(
                order_id=order.id,
                menu_item_id=menu_item.id,
                name=menu_item.name,
                price=unit_price,
                quantity=requested_item.quantity,
                subtotal=item_subtotal,
                notes=requested_item.notes,
                selected_options=(json.dumps(option_snapshot) if option_snapshot else None),
            )
            order_items.append(order_item)
            self.db.add(order_item)

        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=None,
                to_status=OrderStatus.PENDING.value,
                changed_by=user_id,
                reason="Order created",
            )
        )

        await self.db.flush()
        from app.modules.journey.service import JourneyService

        await JourneyService(self.db).mark_cart_checked_out_for_order(order)
        await self.db.refresh(order)
        return self._to_order_response(order, order_items)

    async def get_order_by_id(
        self,
        order_id: str,
        *,
        actor_user_id: str | None = None,
        actor_role: Role | str | None = None,
    ) -> OrderResponse:
        """Get order by ID."""
        order = await self._get_order_model_by_id(order_id)
        await self._enforce_order_access(
            order,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        order_items = await self._get_order_items(order.id)
        return self._to_order_response(order, order_items)

    async def get_order_by_number(
        self,
        order_number: str,
        *,
        actor_user_id: str | None = None,
        actor_role: Role | str | None = None,
    ) -> OrderResponse:
        """Get order by order number."""
        order = await self._get_order_model_by_number(order_number)
        await self._enforce_order_access(
            order,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        order_items = await self._get_order_items(order.id)
        return self._to_order_response(order, order_items)

    async def update_status(
        self,
        order_id: str,
        data: OrderStatusUpdate,
        changed_by: str | None = None,
        actor_role: Role | str | None = None,
    ) -> OrderResponse:
        """
        Update order status.

        Validates status transitions and emits events.
        """
        order = await self._get_order_model_by_id(order_id)
        await self._enforce_order_access(
            order,
            actor_user_id=changed_by,
            actor_role=actor_role,
        )
        current_status = OrderStatus(order.status)
        new_status = (
            data.status if isinstance(data.status, OrderStatus) else OrderStatus(data.status)
        )

        if current_status == new_status:
            order_items = await self._get_order_items(order.id)
            return self._to_order_response(order, order_items)

        if not self._validate_status_transition(current_status, new_status):
            raise InvalidStateTransitionError(
                message=f"Invalid transition from {current_status.value} to {new_status.value}"
            )

        order.status = new_status.value
        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=current_status.value,
                to_status=new_status.value,
                changed_by=changed_by,
                reason=data.reason,
            )
        )
        await self.db.flush()
        await self.db.refresh(order)

        # --- n8n Triggers ---
        # WF-03: fire on every status transition
        N8nClient.trigger(
            "/webhook/bitenex/order-status-changed",
            {
                "orderId": order.id,
                "orderNumber": order.order_number,
                "userId": order.user_id,
                "merchantId": order.merchant_id,
                "fromStatus": current_status.value,
                "toStatus": new_status.value,
                "changedAt": order.updated_at.isoformat() if order.updated_at else None,
            },
        )
        # WF-04: fire extra trigger when order is delivered
        if new_status == OrderStatus.DELIVERED:
            N8nClient.trigger(
                "/webhook/bitenex/order-delivered",
                {
                    "orderId": order.id,
                    "orderNumber": order.order_number,
                    "userId": order.user_id,
                    "merchantId": order.merchant_id,
                    "deliveredAt": order.updated_at.isoformat() if order.updated_at else None,
                    "total": float(order.total),
                },
            )

        order_items = await self._get_order_items(order.id)
        return self._to_order_response(order, order_items)

    async def get_user_orders(
        self,
        user_id: str,
        status: OrderStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[OrderResponse], int]:
        """Get orders for a user."""
        return await self._list_orders(
            filters=[
                Order.user_id == user_id,
                Order.is_deleted == False,
            ],
            status=status,
            page=page,
            per_page=per_page,
        )

    async def get_merchant_orders(
        self,
        merchant_id: str,
        status: OrderStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[OrderResponse], int]:
        """Get orders for a merchant."""
        if not merchant_id:
            raise ValidationError(message="merchant_id is required")
        return await self._list_orders(
            filters=[
                Order.merchant_id == merchant_id,
                Order.is_deleted == False,
            ],
            status=status,
            page=page,
            per_page=per_page,
        )

    async def get_driver_orders(
        self,
        driver_id: str,
        status: OrderStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[OrderResponse], int]:
        """Get orders for a driver."""
        if not driver_id:
            raise ValidationError(message="driver_id is required")
        return await self._list_orders(
            filters=[
                Order.driver_id == driver_id,
                Order.is_deleted == False,
            ],
            status=status,
            page=page,
            per_page=per_page,
        )

    async def get_admin_orders(
        self,
        *,
        search: str | None = None,
        status: OrderStatus | None = None,
        user_id: str | None = None,
        merchant_id: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[AdminOrderListItem], int]:
        """List orders for admin management."""
        filters = [Order.is_deleted.is_(False)]
        if status:
            filters.append(Order.status == status.value)
        if user_id:
            filters.append(Order.user_id == user_id.strip())
        if merchant_id:
            filters.append(Order.merchant_id == merchant_id.strip())
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Order.id.ilike(term),
                    Order.order_number.ilike(term),
                    Order.user_id.ilike(term),
                    Order.merchant_id.ilike(term),
                    Order.delivery_address.ilike(term),
                )
            )

        query = (
            select(Order)
            .where(*filters)
            .order_by(Order.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        count_query = select(func.count(Order.id)).where(*filters)

        orders = (await self.db.execute(query)).scalars().all()
        total = (await self.db.execute(count_query)).scalar_one()

        order_ids = [order.id for order in orders]
        latest_payment_map: dict[str, Payment] = {}
        if order_ids:
            payments = (
                (
                    await self.db.execute(
                        select(Payment)
                        .where(
                            Payment.order_id.in_(order_ids),
                            Payment.is_deleted.is_(False),
                        )
                        .order_by(Payment.order_id.asc(), Payment.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )

            for payment in payments:
                latest_payment_map[payment.order_id] = payment

        items = [
            self._to_admin_order_item(order, latest_payment_map.get(order.id)) for order in orders
        ]
        return items, total

    async def cancel_order(
        self,
        order_id: str,
        reason: str,
        cancelled_by: str,
        actor_role: Role | str | None = None,
    ) -> OrderResponse:
        """Cancel an order."""
        order = await self._get_order_model_by_id(order_id)
        await self._enforce_order_access(
            order,
            actor_user_id=cancelled_by,
            actor_role=actor_role,
        )
        cancellable_statuses = {
            OrderStatus.PENDING,
            OrderStatus.CONFIRMED,
            OrderStatus.PREPARING,
            OrderStatus.READY,
        }

        current_status = OrderStatus(order.status)
        if current_status == OrderStatus.CANCELLED:
            order_items = await self._get_order_items(order.id)
            return self._to_order_response(order, order_items)

        if current_status not in cancellable_statuses:
            raise ValidationError(message=f"Order cannot be cancelled from {current_status.value}")

        order.status = OrderStatus.CANCELLED.value
        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=current_status.value,
                to_status=OrderStatus.CANCELLED.value,
                changed_by=cancelled_by,
                reason=reason or "Order cancelled",
            )
        )

        completed_payment = (
            await self.db.execute(
                select(Payment)
                .where(
                    Payment.order_id == order.id,
                    Payment.is_deleted == False,
                    Payment.status == PaymentStatus.COMPLETED.value,
                )
                .order_by(Payment.created_at.desc())
            )
        ).scalar_one_or_none()

        if completed_payment:
            existing_refund = (
                await self.db.execute(
                    select(Refund).where(
                        Refund.payment_id == completed_payment.id,
                        Refund.is_deleted == False,
                    )
                )
            ).scalar_one_or_none()
            if not existing_refund:
                self.db.add(
                    Refund(
                        payment_id=completed_payment.id,
                        order_id=order.id,
                        amount=completed_payment.amount,
                        reason=reason or "Auto refund on cancellation",
                        status="PENDING",
                        refunded_by=cancelled_by,
                    )
                )

        await self.db.flush()
        await self.db.refresh(order)

        order_items = await self._get_order_items(order.id)
        return self._to_order_response(order, order_items)

    async def assign_driver(
        self,
        order_id: str,
        driver_id: str,
    ) -> OrderResponse:
        """Assign driver to order."""
        order = await self._get_order_model_by_id(order_id)
        order.driver_id = driver_id
        await self.db.flush()
        await self.db.refresh(order)
        order_items = await self._get_order_items(order.id)
        return self._to_order_response(order, order_items)

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
