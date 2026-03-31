# =============================================================================
# Tests — n8n Internal Endpoints & HMAC Webhook Validation
# =============================================================================
"""
Tests for all 4 checklist items:
  1. /internal/... endpoints (19 routes)
  2. HMAC validation
  3. WebhookEvent deduplication
  4. Real n8n payload fixtures
"""

import hashlib
import hmac
import json
import os

import pytest
from httpx import AsyncClient

from app.modules.merchant.models import Merchant
from app.modules.order.models import Order
from app.modules.user.models import User
from app.shared.enums import MerchantStatus, OrderStatus, Role

INTERNAL_TOKEN = os.environ.get("INTERNAL_API_TOKEN", "TEST_INTERNAL_TOKEN")
N8N_WEBHOOK_SECRET = os.environ.get("N8N_WEBHOOK_SECRET", "test-n8n-secret")


def _internal_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {INTERNAL_TOKEN}"}


def _hmac_header(body: bytes, secret: str = N8N_WEBHOOK_SECRET) -> dict[str, str]:
    """Generate valid X-Bitenex-Signature header."""
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Bitenex-Signature": f"sha256={sig}",
    }


# =============================================================================
# 1. /internal/orders/active-deliveries
# =============================================================================

@pytest.mark.asyncio
async def test_active_deliveries_empty(client: AsyncClient, db_session):
    """No DELIVERING orders → empty list."""
    resp = await client.get(
        "/api/v1/internal/orders/active-deliveries",
        headers=_internal_header(),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 0
    assert payload["items"] == []


@pytest.mark.asyncio
async def test_active_deliveries_with_order(client: AsyncClient, db_session):
    """One DELIVERING order should appear in list."""
    order = Order(
        order_number="ORD-TEST-001",
        user_id="user-deliver-001",
        merchant_id="merchant-001",
        status=OrderStatus.DELIVERING.value,
        subtotal=105000,
        total=120000,
        delivery_address="1 Test Street",
        delivery_fee=15000,
    )
    db_session.add(order)
    await db_session.flush()

    resp = await client.get(
        "/api/v1/internal/orders/active-deliveries",
        headers=_internal_header(),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1
    assert payload["items"][0]["orderId"] == order.id


# =============================================================================
# 2. /internal/notifications/push
# =============================================================================

@pytest.mark.asyncio
async def test_send_push_notification(client: AsyncClient, db_session):
    """WF-01 welcome push — should return notificationId."""
    resp = await client.post(
        "/api/v1/internal/notifications/push",
        headers=_internal_header(),
        json={
            "userId": "user-wf01-001",
            "title": "Chào mừng đến Bitenex! 🎉",
            "body": "Cảm ơn bạn đã đăng ký. Nhận ngay voucher 50K cho đơn đầu!",
            "data": {"type": "WELCOME", "voucherCode": "WELCOME50K"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sent"] is True
    assert data["notificationId"] is not None


# =============================================================================
# 3. /internal/notifications/in-app
# =============================================================================

@pytest.mark.asyncio
async def test_send_in_app_notification(client: AsyncClient, db_session):
    """WF-03 order status change in-app notification."""
    resp = await client.post(
        "/api/v1/internal/notifications/in-app",
        headers=_internal_header(),
        json={
            "userId": "user-wf03-001",
            "type": "ORDER_UPDATE",
            "channel": "IN_APP",
            "title": "Đơn hàng của bạn đang được chuẩn bị",
            "body": "Nhà hàng đã xác nhận và đang chuẩn bị món ăn",
            "data": {"orderId": "ord-001", "status": "PREPARING"},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["sent"] is True


# =============================================================================
# 4. /internal/merchants/active-list
# =============================================================================

@pytest.mark.asyncio
async def test_active_merchant_list(client: AsyncClient, db_session):
    """WF-07 merchant digest — should include active merchants."""
    merchant = Merchant(
        user_id="owner-wf07-001",
        name="Phở Hà Nội",
        slug="pho-ha-noi",
        address="123 Đinh Tiên Hoàng",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
        delivery_fee=15000,
    )
    db_session.add(merchant)
    await db_session.flush()

    resp = await client.get(
        "/api/v1/internal/merchants/active-list",
        headers=_internal_header(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [m["merchantId"] for m in data["items"]]
    assert merchant.id in ids


# =============================================================================
# 5. /internal/merchants/:id/daily-stats
# =============================================================================

@pytest.mark.asyncio
async def test_merchant_daily_stats(client: AsyncClient, db_session):
    """WF-07 daily stats — today date should return aggregate."""
    merchant = Merchant(
        user_id="owner-stats-001",
        name="Bún Bò Huế",
        slug="bun-bo-hue",
        address="1 Le Loi",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
        delivery_fee=15000,
    )
    db_session.add(merchant)
    await db_session.flush()

    from datetime import date
    today = date.today().isoformat()
    resp = await client.get(
        f"/api/v1/internal/merchants/{merchant.id}/daily-stats?date={today}",
        headers=_internal_header(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["merchantId"] == merchant.id
    assert data["totalOrders"] == 0  # No orders seeded
    assert data["cancelRate"] == 0.0


# =============================================================================
# 6. /internal/users/lapsed
# =============================================================================

@pytest.mark.asyncio
async def test_lapsed_users_empty(client: AsyncClient, db_session):
    """No users → empty lapsed list."""
    resp = await client.get(
        "/api/v1/internal/users/lapsed?segments=7d",
        headers=_internal_header(),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# =============================================================================
# 7. /internal/journeys/users/:id/first-order-status (WF-01)
# =============================================================================

@pytest.mark.asyncio
async def test_first_order_status_no_order(client: AsyncClient, db_session):
    """User with no orders → hasFirstOrder=false."""
    resp = await client.get(
        "/api/v1/internal/journeys/users/user-new-001/first-order-status",
        headers=_internal_header(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["hasFirstOrder"] is False
    assert data["orderId"] is None


@pytest.mark.asyncio
async def test_first_order_status_with_order(client: AsyncClient, db_session):
    """User with an order → hasFirstOrder=true."""
    order = Order(
        order_number="ORD-FIRST-001",
        user_id="user-firstorder-001",
        merchant_id="m-001",
        status=OrderStatus.DELIVERED.value,
        subtotal=70000,
        total=85000,
        delivery_address="10 Test Ave",
        delivery_fee=15000,
    )
    db_session.add(order)
    await db_session.flush()

    resp = await client.get(
        "/api/v1/internal/journeys/users/user-firstorder-001/first-order-status",
        headers=_internal_header(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["hasFirstOrder"] is True
    assert data["orderId"] == order.id


# =============================================================================
# 8. /internal/marketing/issue-voucher (WF-01, WF-04, WF-08)
# =============================================================================

@pytest.mark.asyncio
async def test_issue_voucher(client: AsyncClient, db_session):
    """First voucher issuance → isExisting=false."""
    resp = await client.post(
        "/api/v1/internal/marketing/issue-voucher",
        headers=_internal_header(),
        json={
            "userId": "user-voucher-001",
            "voucherCode": "WELCOME50K",
            "discountAmount": 50000,
            "expiresInDays": 7,
            "reason": "wf01_welcome",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["voucherCode"] == "WELCOME50K"
    assert data["isExisting"] is False
    assert data["discountAmount"] == 50000


@pytest.mark.asyncio
async def test_issue_voucher_dedup(client: AsyncClient, db_session):
    """Second call with same code → isExisting=true (idempotent)."""
    payload = {
        "userId": "user-voucher-002",
        "voucherCode": "REORDER30K",
        "discountAmount": 30000,
        "expiresInDays": 3,
        "reason": "wf04_reorder",
    }
    first = await client.post(
        "/api/v1/internal/marketing/issue-voucher",
        headers=_internal_header(),
        json=payload,
    )
    assert first.status_code == 200
    assert first.json()["isExisting"] is False

    second = await client.post(
        "/api/v1/internal/marketing/issue-voucher",
        headers=_internal_header(),
        json=payload,
    )
    assert second.status_code == 200
    assert second.json()["isExisting"] is True
    assert second.json()["voucherCode"] == first.json()["voucherCode"]


# =============================================================================
# 9. /internal/events/track
# =============================================================================

@pytest.mark.asyncio
async def test_track_event(client: AsyncClient):
    """WF-01 user_registered event should track successfully."""
    resp = await client.post(
        "/api/v1/internal/events/track",
        headers=_internal_header(),
        json={
            "event": "user_registered",
            "userId": "user-evt-001",
            "properties": {
                "source": "organic",
                "city": "HCM",
                "platform": "ios",
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tracked"] is True
    assert data["event"] == "user_registered"


@pytest.mark.asyncio
async def test_track_event_accepts_stringified_properties(client: AsyncClient):
    """n8n may send properties as a JSON string; API should normalize it."""
    resp = await client.post(
        "/api/v1/internal/events/track",
        headers=_internal_header(),
        json={
            "event": "user_registered",
            "userId": "user-evt-002",
            "properties": "{\"source\":\"organic\",\"city\":\"HCM\",\"platform\":\"ios\"}",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tracked"] is True
    assert data["event"] == "user_registered"


# =============================================================================
# 10. HMAC Signature Validation
# =============================================================================

@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature(client: AsyncClient):
    """Requests without X-Bitenex-Signature should be rejected with 401."""
    body = json.dumps({"userId": "u001", "registeredAt": "2026-01-01T00:00:00Z"}).encode()
    resp = await client.post(
        "/api/v1/webhook/bitenex/user-registered",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(client: AsyncClient):
    """Requests with wrong signature should be rejected with 401."""
    body = json.dumps({"userId": "u001"}).encode()
    resp = await client.post(
        "/api/v1/webhook/bitenex/user-registered",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Bitenex-Signature": "sha256=badhash123",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_valid_signature(client: AsyncClient, db_session):
    """Valid HMAC signature should be accepted and processed."""
    payload = {"userId": "u-hmac-001", "registeredAt": "2026-01-01T00:00:00Z"}
    body = json.dumps(payload).encode()
    headers = _hmac_header(body)

    resp = await client.post(
        "/api/v1/webhook/bitenex/user-registered",
        content=body,
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert data["duplicate"] is False


# =============================================================================
# 11. WebhookEvent Deduplication
# =============================================================================

@pytest.mark.asyncio
async def test_webhook_order_delivered_dedup(client: AsyncClient, db_session):
    """Same order.delivered event sent twice → second is marked duplicate."""
    payload = {
        "orderId": "ord-dedup-001",
        "userId": "user-dedup-001",
        "deliveredAt": "2026-03-30T10:00:00Z",
        "totalAmount": 120000,
    }
    body = json.dumps(payload).encode()
    headers = _hmac_header(body)

    # First call
    resp1 = await client.post(
        "/api/v1/webhook/bitenex/order-delivered",
        content=body,
        headers=headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["duplicate"] is False

    # Second call — identical payload
    resp2 = await client.post(
        "/api/v1/webhook/bitenex/order-delivered",
        content=body,
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["duplicate"] is True


@pytest.mark.asyncio
async def test_webhook_order_status_different_transitions_not_dedup(client: AsyncClient, db_session):
    """Same order but DIFFERENT status transitions should each be processed."""
    order_id = "ord-transition-001"

    for status in ["PREPARING", "DELIVERING", "DELIVERED"]:
        payload = {"orderId": order_id, "fromStatus": "PENDING", "toStatus": status}
        body = json.dumps(payload).encode()
        headers = _hmac_header(body)
        resp = await client.post(
            "/api/v1/webhook/bitenex/order-status-changed",
            content=body,
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["duplicate"] is False, f"Should not be duplicate for status={status}"


# =============================================================================
# 12. /internal/journeys/orders/:id/review-status (WF-04)
# =============================================================================

@pytest.mark.asyncio
async def test_review_status_no_review(client: AsyncClient, db_session):
    """Order with no review → hasReview=false."""
    resp = await client.get(
        "/api/v1/internal/journeys/orders/ord-review-001/review-status",
        headers=_internal_header(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["orderId"] == "ord-review-001"
    assert data["hasReview"] is False
