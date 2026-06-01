from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.modules.driver.models import Driver
from app.modules.merchant.models import Merchant
from app.modules.order.models import Order
from app.shared.enums import MerchantStatus, OrderStatus, Role


def _auth_header(user_id: str, role: Role) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


async def _seed_chat_order(db_session):
    merchant = Merchant(
        user_id="merchant-chat-owner",
        name="Chat Merchant",
        slug=f"chat-merchant-{uuid4().hex[:8]}",
        address="1 Chat St",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
    )
    driver = Driver(
        user_id="driver-chat-user",
        status="BUSY",
        is_approved=True,
    )
    db_session.add_all([merchant, driver])
    await db_session.flush()

    order = Order(
        order_number=f"ORD-CHAT-{uuid4().hex[:8].upper()}",
        user_id="user-chat",
        merchant_id=merchant.id,
        driver_id=driver.id,
        status=OrderStatus.PICKING_UP.value,
        subtotal=100,
        delivery_fee=10,
        tax=0,
        discount=0,
        total=110,
        delivery_address="123 Chat Delivery St",
    )
    db_session.add(order)
    await db_session.flush()
    return order, driver


@pytest.mark.asyncio
async def test_user_driver_chat_emits_realtime_to_both_participants(
    client: AsyncClient,
    db_session,
    monkeypatch,
):
    order, driver = await _seed_chat_order(db_session)
    sent: list[tuple[str, dict]] = []

    async def fake_send_personal(user_id: str, message: dict):
        sent.append((user_id, message))

    monkeypatch.setattr(
        "app.modules.chat.service.connection_manager.send_personal",
        fake_send_personal,
    )

    response = await client.post(
        f"/api/v1/chats/orders/{order.id}/messages",
        json={"conversation_type": "USER_DRIVER", "content": "toi dang toi"},
        headers=_auth_header(order.user_id, Role.USER),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["content"] == "toi dang toi"
    assert payload["conversation_type"] == "USER_DRIVER"

    assert [user_id for user_id, _message in sent] == [order.user_id, driver.user_id]
    for _user_id, message in sent:
        assert message["event"] == "chat.message"
        assert message["data"]["id"] == payload["id"]
        assert message["data"]["order_id"] == order.id
        assert message["data"]["content"] == "toi dang toi"


@pytest.mark.asyncio
async def test_driver_user_chat_emits_driver_message_to_both_participants(
    client: AsyncClient,
    db_session,
    monkeypatch,
):
    order, driver = await _seed_chat_order(db_session)
    sent: list[tuple[str, dict]] = []

    async def fake_send_personal(user_id: str, message: dict):
        sent.append((user_id, message))

    monkeypatch.setattr(
        "app.modules.chat.service.connection_manager.send_personal",
        fake_send_personal,
    )

    response = await client.post(
        f"/api/v1/chats/orders/{order.id}/messages",
        json={"conversation_type": "USER_DRIVER", "content": "toi da den"},
        headers=_auth_header(driver.user_id, Role.DRIVER),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["sender_role"] == "DRIVER"

    assert [user_id for user_id, _message in sent] == [order.user_id, driver.user_id]
    assert all(message["event"] == "chat.message" for _user_id, message in sent)


@pytest.mark.asyncio
async def test_merchant_driver_chat_emits_realtime_to_merchant_and_driver(
    client: AsyncClient,
    db_session,
    monkeypatch,
):
    order, driver = await _seed_chat_order(db_session)
    sent: list[tuple[str, dict]] = []

    async def fake_send_personal(user_id: str, message: dict):
        sent.append((user_id, message))

    monkeypatch.setattr(
        "app.modules.chat.service.connection_manager.send_personal",
        fake_send_personal,
    )

    response = await client.post(
        f"/api/v1/chats/orders/{order.id}/messages",
        json={"conversation_type": "MERCHANT_DRIVER", "content": "don hang san sang"},
        headers=_auth_header("merchant-chat-owner", Role.MERCHANT),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["sender_role"] == "MERCHANT"
    assert payload["conversation_type"] == "MERCHANT_DRIVER"

    assert [user_id for user_id, _message in sent] == ["merchant-chat-owner", driver.user_id]
    for _user_id, message in sent:
        assert message["event"] == "chat.message"
        assert message["data"]["id"] == payload["id"]
        assert message["data"]["order_id"] == order.id
        assert message["data"]["content"] == "don hang san sang"


@pytest.mark.asyncio
async def test_driver_merchant_chat_emits_driver_message_to_merchant_and_driver(
    client: AsyncClient,
    db_session,
    monkeypatch,
):
    order, driver = await _seed_chat_order(db_session)
    sent: list[tuple[str, dict]] = []

    async def fake_send_personal(user_id: str, message: dict):
        sent.append((user_id, message))

    monkeypatch.setattr(
        "app.modules.chat.service.connection_manager.send_personal",
        fake_send_personal,
    )

    response = await client.post(
        f"/api/v1/chats/orders/{order.id}/messages",
        json={"conversation_type": "MERCHANT_DRIVER", "content": "toi dang den lay"},
        headers=_auth_header(driver.user_id, Role.DRIVER),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["sender_role"] == "DRIVER"

    assert [user_id for user_id, _message in sent] == ["merchant-chat-owner", driver.user_id]
    assert all(message["event"] == "chat.message" for _user_id, message in sent)
