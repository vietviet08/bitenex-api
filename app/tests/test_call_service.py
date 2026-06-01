from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.modules.call.models import OrderCall
from app.modules.driver.models import Driver
from app.modules.merchant.models import Merchant
from app.modules.order.models import Order
from app.shared.enums import MerchantStatus, OrderStatus, Role


def _auth_header(user_id: str, role: Role) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


async def _seed_assigned_order(db_session, *, status: OrderStatus = OrderStatus.PICKING_UP):
    merchant = Merchant(
        user_id="merchant-call-owner",
        name="Call Merchant",
        slug=f"call-merchant-{uuid4().hex[:8]}",
        address="1 Voice St",
        city="Da Nang",
        status=MerchantStatus.ACTIVE.value,
    )
    driver = Driver(
        user_id="driver-call-user",
        status="BUSY",
        is_approved=True,
    )
    db_session.add_all([merchant, driver])
    await db_session.flush()

    order = Order(
        order_number=f"ORD-CALL-{uuid4().hex[:8].upper()}",
        user_id="user-call",
        merchant_id=merchant.id,
        driver_id=driver.id,
        status=status.value,
        subtotal=100,
        delivery_fee=10,
        tax=0,
        discount=0,
        total=110,
        delivery_address="123 Delivery St",
    )
    db_session.add(order)
    await db_session.flush()
    return order, driver


@pytest.mark.asyncio
async def test_user_can_start_and_driver_can_accept_call(client: AsyncClient, db_session):
    order, driver = await _seed_assigned_order(db_session)

    start_response = await client.post(
        f"/api/v1/calls/orders/{order.id}/start",
        headers=_auth_header(order.user_id, Role.USER),
    )
    assert start_response.status_code == 201
    start_payload = start_response.json()
    assert start_payload["agora_app_id"] == "test-agora-app-id"
    assert start_payload["agora_uid"] == 1
    assert start_payload["call"]["status"] == "RINGING"
    assert start_payload["call"]["channel_name"] == f"call-{start_payload['call']['id']}"
    assert len(start_payload["call"]["channel_name"]) <= 64

    accept_response = await client.post(
        f"/api/v1/calls/{start_payload['call']['id']}/accept",
        headers=_auth_header(driver.user_id, Role.DRIVER),
    )
    assert accept_response.status_code == 200
    accept_payload = accept_response.json()
    assert accept_payload["agora_uid"] == 2
    assert accept_payload["call"]["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_driver_can_start_and_user_can_accept_call_idempotently(client: AsyncClient, db_session):
    order, driver = await _seed_assigned_order(db_session)

    start_response = await client.post(
        f"/api/v1/calls/orders/{order.id}/start",
        headers=_auth_header(driver.user_id, Role.DRIVER),
    )
    assert start_response.status_code == 201
    start_payload = start_response.json()
    assert start_payload["agora_uid"] == 2
    assert start_payload["call"]["caller_role"] == "DRIVER"
    assert start_payload["call"]["callee_role"] == "USER"
    assert start_payload["call"]["channel_name"] == f"call-{start_payload['call']['id']}"
    assert len(start_payload["call"]["channel_name"]) <= 64
    call_id = start_payload["call"]["id"]

    accept_response = await client.post(
        f"/api/v1/calls/{call_id}/accept",
        headers=_auth_header(order.user_id, Role.USER),
    )
    assert accept_response.status_code == 200
    accept_payload = accept_response.json()
    assert accept_payload["agora_uid"] == 1
    assert accept_payload["call"]["status"] == "ACCEPTED"

    retry_response = await client.post(
        f"/api/v1/calls/{call_id}/accept",
        headers=_auth_header(order.user_id, Role.USER),
    )
    assert retry_response.status_code == 200
    retry_payload = retry_response.json()
    assert retry_payload["agora_uid"] == 1
    assert retry_payload["call"]["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_unrelated_user_cannot_start_call(client: AsyncClient, db_session):
    order, _driver = await _seed_assigned_order(db_session)

    response = await client.post(
        f"/api/v1/calls/orders/{order.id}/start",
        headers=_auth_header("not-order-user", Role.USER),
    )

    assert response.status_code == 403
    assert response.json()["error"]["error_code"] == "AUTHORIZATION_ERROR"


@pytest.mark.asyncio
async def test_merchant_cannot_start_driver_user_call(client: AsyncClient, db_session):
    order, _driver = await _seed_assigned_order(db_session)

    response = await client.post(
        f"/api/v1/calls/orders/{order.id}/start",
        headers=_auth_header("merchant-call-owner", Role.MERCHANT),
    )

    assert response.status_code == 403
    assert response.json()["error"]["error_code"] == "AUTHORIZATION_ERROR"


@pytest.mark.asyncio
async def test_call_requires_active_delivery_status(client: AsyncClient, db_session):
    order, _driver = await _seed_assigned_order(db_session, status=OrderStatus.READY)

    response = await client.post(
        f"/api/v1/calls/orders/{order.id}/start",
        headers=_auth_header(order.user_id, Role.USER),
    )

    assert response.status_code == 400
    assert response.json()["error"]["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_only_callee_can_accept_call(client: AsyncClient, db_session):
    order, _driver = await _seed_assigned_order(db_session)
    start_response = await client.post(
        f"/api/v1/calls/orders/{order.id}/start",
        headers=_auth_header(order.user_id, Role.USER),
    )
    call_id = start_response.json()["call"]["id"]

    response = await client.post(
        f"/api/v1/calls/{call_id}/accept",
        headers=_auth_header("not-assigned-driver-user", Role.DRIVER),
    )

    assert response.status_code == 403
    assert response.json()["error"]["error_code"] == "AUTHORIZATION_ERROR"


@pytest.mark.asyncio
async def test_reject_and_end_are_idempotent_for_terminal_call(client: AsyncClient, db_session):
    order, driver = await _seed_assigned_order(db_session)
    start_response = await client.post(
        f"/api/v1/calls/orders/{order.id}/start",
        headers=_auth_header(driver.user_id, Role.DRIVER),
    )
    call_id = start_response.json()["call"]["id"]

    reject_response = await client.post(
        f"/api/v1/calls/{call_id}/reject",
        headers=_auth_header(order.user_id, Role.USER),
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["call"]["status"] == "REJECTED"

    end_response = await client.post(
        f"/api/v1/calls/{call_id}/end",
        headers=_auth_header(driver.user_id, Role.DRIVER),
    )
    assert end_response.status_code == 200
    assert end_response.json()["call"]["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_expired_ringing_call_becomes_missed(client: AsyncClient, db_session):
    order, driver = await _seed_assigned_order(db_session)
    expired_call = OrderCall(
        order_id=order.id,
        caller_user_id=order.user_id,
        callee_user_id=driver.user_id,
        caller_role=Role.USER.value,
        callee_role=Role.DRIVER.value,
        channel_name=f"order-{order.id}-expired",
        status="RINGING",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=4),
    )
    db_session.add(expired_call)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/calls/{expired_call.id}",
        headers=_auth_header(order.user_id, Role.USER),
    )
    assert response.status_code == 200
    assert response.json()["call"]["status"] == "MISSED"

    refreshed = (
        await db_session.execute(select(OrderCall).where(OrderCall.id == expired_call.id))
    ).scalar_one()
    assert refreshed.status == "MISSED"
