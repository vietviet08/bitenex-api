from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.modules.merchant.models import Merchant
from app.modules.order.models import Order
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
    total: float = 110.0,
) -> Order:
    return Order(
        order_number=f"ORD-ADMIN-{uuid4().hex[:8].upper()}",
        user_id=user_id,
        merchant_id=merchant_id,
        status=status.value,
        subtotal=100.0,
        delivery_fee=10.0,
        tax=0.0,
        discount=0.0,
        total=total,
        delivery_address="123 Admin St",
    )


@pytest.mark.asyncio
async def test_admin_list_orders_returns_latest_payment_status(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-admin-orders",
        name="Admin Orders Merchant",
        slug=f"admin-orders-{uuid4().hex[:8]}",
        address="1 Merchant St",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    target_order = _build_order(user_id="user-admin-orders-1", merchant_id=merchant.id)
    other_order = _build_order(
        user_id="user-admin-orders-2",
        merchant_id=merchant.id,
        status=OrderStatus.CONFIRMED,
    )
    db_session.add_all([target_order, other_order])
    await db_session.flush()

    db_session.add(
        Payment(
            transaction_id=f"PAY-ADMIN-OLD-{uuid4().hex[:8].upper()}",
            order_id=target_order.id,
            user_id=target_order.user_id,
            amount=target_order.total,
            currency="VND",
            method="VNPAY",
            status=PaymentStatus.PROCESSING.value,
            gateway="vnpay",
        )
    )
    await db_session.flush()

    latest_payment = Payment(
        transaction_id=f"PAY-ADMIN-NEW-{uuid4().hex[:8].upper()}",
        order_id=target_order.id,
        user_id=target_order.user_id,
        amount=target_order.total,
        currency="VND",
        method="VNPAY",
        status=PaymentStatus.COMPLETED.value,
        gateway="vnpay",
    )
    db_session.add(latest_payment)
    await db_session.flush()

    response = await client.get(
        "/api/v1/orders/admin/list",
        headers=_auth_header("admin-orders", Role.ADMIN),
        params={"search": target_order.order_number},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == target_order.id
    assert payload["items"][0]["payment_status"] == PaymentStatus.COMPLETED.value
    assert payload["items"][0]["latest_payment_id"] == latest_payment.id


@pytest.mark.asyncio
async def test_admin_list_payments_returns_refund_metrics(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-admin-payments",
        name="Admin Payments Merchant",
        slug=f"admin-payments-{uuid4().hex[:8]}",
        address="2 Merchant St",
        city="Hanoi",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    order = _build_order(
        user_id="user-admin-payments",
        merchant_id=merchant.id,
        status=OrderStatus.CANCELLED,
        total=210.0,
    )
    db_session.add(order)
    await db_session.flush()

    payment = Payment(
        transaction_id=f"PAY-ADMIN-{uuid4().hex[:8].upper()}",
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

    db_session.add(
        Refund(
            payment_id=payment.id,
            order_id=order.id,
            amount=60.0,
            reason="Partial compensation",
            status="COMPLETED",
            refunded_by="admin-payments",
        )
    )
    await db_session.flush()

    response = await client.get(
        "/api/v1/payments/admin/list",
        headers=_auth_header("admin-payments", Role.ADMIN),
        params={"status": PaymentStatus.COMPLETED.value},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1

    first = payload["items"][0]
    assert first["id"] == payment.id
    assert first["refunded_amount"] == 60.0
    assert first["refundable_amount"] == 150.0
    assert first["order_status"] == OrderStatus.CANCELLED.value
