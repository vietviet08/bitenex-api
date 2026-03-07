from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.modules.chat.models import ChatMessage
from app.modules.merchant.models import Merchant
from app.modules.order.models import Order
from app.shared.enums import MerchantStatus, OrderStatus, Role


def _auth_header(user_id: str, role: Role) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


def _build_order(*, user_id: str, merchant_id: str, status: OrderStatus) -> Order:
    return Order(
        order_number=f"ORD-CHAT-{uuid4().hex[:8].upper()}",
        user_id=user_id,
        merchant_id=merchant_id,
        status=status.value,
        subtotal=100.0,
        delivery_fee=10.0,
        tax=0.0,
        discount=0.0,
        total=110.0,
        delivery_address="123 Chat Street",
    )


@pytest.mark.asyncio
async def test_order_chat_history_visible_to_user_and_merchant(client: AsyncClient, db_session):
    user_id = "chat-user-1"
    merchant_owner_user_id = "chat-merchant-owner-1"
    merchant = Merchant(
        user_id=merchant_owner_user_id,
        name="Chat Merchant",
        slug=f"chat-merchant-{uuid4().hex[:8]}",
        address="1 Merchant St",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    order = _build_order(
        user_id=user_id,
        merchant_id=merchant.id,
        status=OrderStatus.PREPARING,
    )
    db_session.add(order)
    await db_session.flush()

    db_session.add_all(
        [
            ChatMessage(
                order_id=order.id,
                sender_id=user_id,
                receiver_id=merchant_owner_user_id,
                message_type="text",
                content="Hello merchant",
            ),
            ChatMessage(
                order_id=order.id,
                sender_id=merchant_owner_user_id,
                receiver_id=user_id,
                message_type="text",
                content="Hi user, your order is preparing",
            ),
        ]
    )
    await db_session.flush()

    user_response = await client.get(
        f"/api/v1/chat/orders/{order.id}/messages",
        headers=_auth_header(user_id, Role.USER),
    )
    assert user_response.status_code == 200
    user_payload = user_response.json()
    assert user_payload["total"] == 2
    assert user_payload["items"][0]["content"] == "Hello merchant"
    assert user_payload["items"][1]["content"] == "Hi user, your order is preparing"

    merchant_response = await client.get(
        f"/api/v1/chat/orders/{order.id}/messages",
        headers=_auth_header(merchant_owner_user_id, Role.MERCHANT),
    )
    assert merchant_response.status_code == 200
    merchant_payload = merchant_response.json()
    assert merchant_payload["total"] == 2


@pytest.mark.asyncio
async def test_order_chat_history_forbidden_for_non_participant(client: AsyncClient, db_session):
    user_id = "chat-user-2"
    merchant_owner_user_id = "chat-merchant-owner-2"
    merchant = Merchant(
        user_id=merchant_owner_user_id,
        name="Chat Merchant 2",
        slug=f"chat-merchant-2-{uuid4().hex[:8]}",
        address="2 Merchant St",
        city="Hanoi",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    order = _build_order(
        user_id=user_id,
        merchant_id=merchant.id,
        status=OrderStatus.PREPARING,
    )
    db_session.add(order)
    await db_session.flush()

    db_session.add(
        ChatMessage(
            order_id=order.id,
            sender_id=user_id,
            receiver_id=merchant_owner_user_id,
            message_type="text",
            content="Hidden message",
        )
    )
    await db_session.flush()

    other_user_response = await client.get(
        f"/api/v1/chat/orders/{order.id}/messages",
        headers=_auth_header("other-chat-user", Role.USER),
    )
    assert other_user_response.status_code == 403
    assert other_user_response.json()["error"]["error_code"] == "AUTHORIZATION_ERROR"
