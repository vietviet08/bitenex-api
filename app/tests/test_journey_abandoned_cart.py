from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.modules.journey.models import AbandonedCartJourney
from app.modules.journey.service import JourneyService
from app.modules.merchant.models import MenuItem, Merchant
from app.shared.enums import MerchantStatus, Role

INTERNAL_TOKEN = "TEST_INTERNAL_TOKEN"


def _internal_auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {INTERNAL_TOKEN}"}


def _user_auth_header(user_id: str, role: Role = Role.USER) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_abandoned_cart_status_changes_after_checkout(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-owner-journey",
        name="Journey Merchant",
        slug="journey-merchant",
        address="1 Journey St",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
        delivery_fee=15000,
    )
    db_session.add(merchant)
    await db_session.flush()

    menu_item = MenuItem(
        merchant_id=merchant.id,
        name="Pho Journey",
        price=65000,
        category="Noodles",
        is_available=True,
        is_featured=True,
    )
    db_session.add(menu_item)
    await db_session.flush()

    upsert_resp = await client.post(
        "/api/v1/internal/journeys/abandoned-carts/activity",
        headers=_internal_auth_header(),
        json={
            "cart_id": "cart-journey-001",
            "user_id": "user-journey-001",
            "merchant_id": merchant.id,
            "merchant_name": merchant.name,
            "cart_value": 185000,
            "currency": "VND",
            "item_count": 2,
            "restaurant_open": True,
            "items_available": True,
            "deep_link": "bitenex://cart/cart-journey-001",
        },
    )
    assert upsert_resp.status_code == 201

    initial_status = await client.post(
        "/api/v1/internal/journeys/abandoned-carts/status",
        headers=_internal_auth_header(),
        json={
            "user_id": "user-journey-001",
            "cart_id": "cart-journey-001",
            "properties": {
                "cart_value": 185000,
                "merchant_id": merchant.id,
            },
        },
    )
    assert initial_status.status_code == 200
    assert initial_status.json()["has_converted"] is False
    assert initial_status.json()["cart_status"] == "ACTIVE"

    order_resp = await client.post(
        "/api/v1/orders",
        headers=_user_auth_header("user-journey-001"),
        json={
            "merchant_id": merchant.id,
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "quantity": 2,
                    "selected_options": [],
                }
            ],
            "delivery_address": "123 Checkout Street",
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["id"]

    final_status = await client.post(
        "/api/v1/internal/journeys/abandoned-carts/status",
        headers=_internal_auth_header(),
        json={
            "user_id": "user-journey-001",
            "cart_id": "cart-journey-001",
            "properties": {
                "cart_value": 185000,
                "merchant_id": merchant.id,
            },
        },
    )
    assert final_status.status_code == 200
    payload = final_status.json()
    assert payload["has_converted"] is True
    assert payload["cart_status"] == "CHECKED_OUT"
    assert payload["recovery_order_id"] == order_id


@pytest.mark.asyncio
async def test_user_can_sync_own_cart_activity(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-owner-public-journey",
        name="Public Journey Merchant",
        slug="public-journey-merchant",
        address="2 Journey St",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    menu_item = MenuItem(
        merchant_id=merchant.id,
        name="Bun Bo Public",
        price=72000,
        category="Noodles",
        is_available=True,
        is_featured=False,
    )
    db_session.add(menu_item)
    await db_session.flush()

    response = await client.post(
        "/api/v1/journeys/abandoned-carts/activity",
        headers=_user_auth_header("user-public-journey"),
        json={
            "cart_id": "cart-public-journey-001",
            "merchant_id": merchant.id,
            "cart_value": 72000,
            "item_count": 1,
            "deep_link": "bitenex://cart/cart-public-journey-001",
            "payload_snapshot": {
                "items": [
                    {
                        "menu_item_id": menu_item.id,
                        "quantity": 1,
                    }
                ]
            },
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["user_id"] == "user-public-journey"
    assert payload["merchant_id"] == merchant.id
    assert payload["merchant_name"] == merchant.name
    assert payload["restaurant_open"] is True
    assert payload["items_available"] is True


@pytest.mark.asyncio
async def test_freeship_offer_is_reused_for_same_cart(client: AsyncClient):
    first = await client.post(
        "/api/v1/internal/journeys/abandoned-carts/offers/freeship",
        headers=_internal_auth_header(),
        json={
            "user_id": "user-offer-001",
            "cart_id": "cart-offer-001",
            "cart_value": 200000,
            "coupon_type": "freeship",
            "max_discount": 30000,
            "min_cart_value": 150000,
            "expires_in_hours": 24,
        },
    )
    assert first.status_code == 201
    first_payload = first.json()
    assert first_payload["offer_type"] == "freeship"
    assert first_payload["is_existing"] is False

    second = await client.post(
        "/api/v1/internal/journeys/abandoned-carts/offers/freeship",
        headers=_internal_auth_header(),
        json={
            "user_id": "user-offer-001",
            "cart_id": "cart-offer-001",
            "cart_value": 200000,
            "coupon_type": "freeship",
            "max_discount": 30000,
            "min_cart_value": 150000,
            "expires_in_hours": 24,
        },
    )
    assert second.status_code == 201
    second_payload = second.json()
    assert second_payload["code"] == first_payload["code"]
    assert second_payload["is_existing"] is True


@pytest.mark.asyncio
async def test_dispatch_due_abandoned_cart_webhooks(db_session, monkeypatch):
    journey = AbandonedCartJourney(
        cart_id="cart-dispatch-001",
        user_id="user-dispatch-001",
        merchant_id="merchant-dispatch-001",
        merchant_name="Dispatch Merchant",
        cart_value=185000,
        currency="VND",
        item_count=3,
        restaurant_open=True,
        items_available=True,
        deep_link="bitenex://cart/cart-dispatch-001",
        status="ACTIVE",
        last_activity_at=datetime.now(timezone.utc) - timedelta(minutes=45),
    )
    db_session.add(journey)
    await db_session.flush()

    calls: list[tuple[str, dict]] = []

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict):
            calls.append((url, json))
            return _FakeResponse()

    monkeypatch.setattr("app.modules.journey.service.httpx.AsyncClient", _FakeAsyncClient)

    service = JourneyService(db_session)
    dispatched = await service.dispatch_due_abandoned_cart_webhooks()
    await db_session.flush()

    assert dispatched == 1
    assert len(calls) == 1
    assert calls[0][1]["journey"] == "abandoned_cart_recovery"
    assert journey.status == "ABANDONED"
    assert journey.webhook_triggered_at is not None
