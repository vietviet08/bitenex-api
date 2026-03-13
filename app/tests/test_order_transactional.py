from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.modules.driver.models import Driver
from app.modules.merchant.models import MenuItem, Merchant
from app.modules.order.models import Order, OrderStatusHistory
from app.modules.payment.models import Payment, Refund
from app.shared.enums import MerchantStatus, OrderStatus, PaymentStatus, Role


def _auth_header(user_id: str, role: Role) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


def _build_order(
    *,
    user_id: str,
    merchant_id: str,
    status: OrderStatus = OrderStatus.PENDING,
    driver_id: str | None = None,
) -> Order:
    return Order(
        order_number=f"ORD-TEST-{uuid4().hex[:8].upper()}",
        user_id=user_id,
        merchant_id=merchant_id,
        driver_id=driver_id,
        status=status.value,
        subtotal=100.0,
        delivery_fee=10.0,
        tax=0.0,
        discount=0.0,
        total=110.0,
        delivery_address="123 Test St",
    )


@pytest.mark.asyncio
async def test_create_order_atomic_and_invalid_item_rejected(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-owner-create-order",
        name="Create Order Merchant",
        slug=f"create-order-{uuid4().hex[:8]}",
        address="1 Merchant St",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    menu_item = MenuItem(
        merchant_id=merchant.id,
        name="Pho",
        price=50.0,
        is_available=True,
    )
    db_session.add(menu_item)
    await db_session.flush()

    user_id = "user-create-order"
    ok_response = await client.post(
        "/api/v1/orders",
        json={
            "merchant_id": merchant.id,
            "delivery_address": "123 Test St",
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 2,
                }
            ],
        },
        headers=_auth_header(user_id, Role.USER),
    )
    assert ok_response.status_code == 201
    assert ok_response.json()["status"] == OrderStatus.PENDING.value
    assert len(ok_response.json()["items"]) == 1

    bad_response = await client.post(
        "/api/v1/orders",
        json={
            "merchant_id": merchant.id,
            "delivery_address": "123 Test St",
            "items": [
                {
                    "menu_item_id": "not-found-item",
                    "quantity": 1,
                }
            ],
        },
        headers=_auth_header(user_id, Role.USER),
    )
    assert bad_response.status_code == 400
    assert bad_response.json()["error"]["error_code"] == "VALIDATION_ERROR"

    total_orders = (
        await db_session.execute(
            select(func.count(Order.id)).where(Order.user_id == user_id, Order.is_deleted == False)
        )
    ).scalar_one()
    assert total_orders == 1


@pytest.mark.asyncio
async def test_role_scoped_order_queries(client: AsyncClient, db_session):
    merchant_owner_user_id = "merchant-owner-scope"
    merchant = Merchant(
        user_id=merchant_owner_user_id,
        name="Scope Merchant",
        slug=f"scope-merchant-{uuid4().hex[:8]}",
        address="2 Merchant St",
        city="Hanoi",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    driver = Driver(
        user_id="driver-scope-user",
        status="ONLINE",
        is_approved=True,
    )
    db_session.add(driver)
    await db_session.flush()

    order_user_1 = _build_order(
        user_id="user-scope-1",
        merchant_id=merchant.id,
        driver_id=driver.id,
    )
    order_user_2 = _build_order(
        user_id="user-scope-2",
        merchant_id=merchant.id,
    )
    db_session.add_all([order_user_1, order_user_2])
    await db_session.flush()

    user_resp = await client.get(
        "/api/v1/orders/my",
        headers=_auth_header("user-scope-1", Role.USER),
    )
    assert user_resp.status_code == 200
    assert user_resp.json()["total"] == 1
    assert user_resp.json()["items"][0]["user_id"] == "user-scope-1"

    merchant_resp = await client.get(
        "/api/v1/orders/merchant/incoming",
        headers=_auth_header(merchant_owner_user_id, Role.MERCHANT),
    )
    assert merchant_resp.status_code == 200
    assert merchant_resp.json()["total"] == 2

    driver_resp = await client.get(
        "/api/v1/orders/driver/assigned",
        headers=_auth_header(driver.user_id, Role.DRIVER),
    )
    assert driver_resp.status_code == 200
    assert driver_resp.json()["total"] == 1
    assert driver_resp.json()["items"][0]["driver_id"] == driver.id


@pytest.mark.asyncio
async def test_order_status_transition_guard(client: AsyncClient, db_session):
    merchant_owner_user_id = "merchant-owner-transition"
    merchant = Merchant(
        user_id=merchant_owner_user_id,
        name="Transition Merchant",
        slug=f"transition-merchant-{uuid4().hex[:8]}",
        address="3 Merchant St",
        city="Da Nang",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    order = _build_order(user_id="user-transition", merchant_id=merchant.id)
    db_session.add(order)
    await db_session.flush()

    invalid_resp = await client.post(
        f"/api/v1/orders/{order.id}/status",
        json={"status": OrderStatus.PREPARING.value},
        headers=_auth_header(merchant_owner_user_id, Role.MERCHANT),
    )
    assert invalid_resp.status_code == 400
    assert invalid_resp.json()["error"]["error_code"] == "INVALID_STATE_TRANSITION"

    valid_resp = await client.post(
        f"/api/v1/orders/{order.id}/status",
        json={"status": OrderStatus.CONFIRMED.value},
        headers=_auth_header(merchant_owner_user_id, Role.MERCHANT),
    )
    assert valid_resp.status_code == 200
    assert valid_resp.json()["status"] == OrderStatus.CONFIRMED.value

    history_count = (
        await db_session.execute(
            select(func.count(OrderStatusHistory.id)).where(
                OrderStatusHistory.order_id == order.id,
                OrderStatusHistory.to_status == OrderStatus.CONFIRMED.value,
            )
        )
    ).scalar_one()
    assert history_count == 1


@pytest.mark.asyncio
async def test_cancel_paid_order_creates_single_refund(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-owner-cancel",
        name="Cancel Merchant",
        slug=f"cancel-merchant-{uuid4().hex[:8]}",
        address="4 Merchant St",
        city="Can Tho",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    order = _build_order(
        user_id="user-cancel",
        merchant_id=merchant.id,
        status=OrderStatus.CONFIRMED,
    )
    db_session.add(order)
    await db_session.flush()

    payment = Payment(
        transaction_id=f"TXN-{uuid4().hex[:8].upper()}",
        order_id=order.id,
        user_id=order.user_id,
        amount=order.total,
        currency="VND",
        method="VNPAY",
        status=PaymentStatus.COMPLETED.value,
        gateway="vnpay",
    )
    db_session.add(payment)
    await db_session.flush()

    cancel_response = await client.post(
        f"/api/v1/orders/{order.id}/cancel?reason=customer+request",
        headers=_auth_header(order.user_id, Role.USER),
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == OrderStatus.CANCELLED.value

    refund_count_after_first_cancel = (
        await db_session.execute(
            select(func.count(Refund.id)).where(
                Refund.payment_id == payment.id,
                Refund.is_deleted == False,
            )
        )
    ).scalar_one()
    assert refund_count_after_first_cancel == 1

    cancel_again_response = await client.post(
        f"/api/v1/orders/{order.id}/cancel?reason=repeat",
        headers=_auth_header(order.user_id, Role.USER),
    )
    assert cancel_again_response.status_code == 200
    assert cancel_again_response.json()["status"] == OrderStatus.CANCELLED.value

    refund_count_after_second_cancel = (
        await db_session.execute(
            select(func.count(Refund.id)).where(
                Refund.payment_id == payment.id,
                Refund.is_deleted == False,
            )
        )
    ).scalar_one()
    assert refund_count_after_second_cancel == 1
