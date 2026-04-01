from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import create_access_token
from app.modules.merchant.models import Merchant
from app.modules.order.models import Order, OrderStatusHistory
from app.modules.payment.models import Payment, WebhookEvent
from app.shared.n8n_client import N8nClient
from app.modules.payment.vnpay import build_vnpay_payment_url, verify_vnpay_signature
from app.shared.enums import MerchantStatus, OrderStatus, PaymentStatus, Role

settings = get_settings()


def _auth_header(user_id: str, role: Role, *, idempotency_key: str | None = None) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _build_order(*, user_id: str, merchant_id: str) -> Order:
    return Order(
        order_number=f"ORD-PAY-{uuid4().hex[:8].upper()}",
        user_id=user_id,
        merchant_id=merchant_id,
        status=OrderStatus.PENDING.value,
        subtotal=100.0,
        delivery_fee=10.0,
        tax=0.0,
        discount=0.0,
        total=110.0,
        delivery_address="123 Payment St",
    )


@pytest.mark.asyncio
async def test_vnpay_signature_utility() -> None:
    payload = {
        "vnp_Amount": "11000",
        "vnp_Command": "pay",
        "vnp_CreateDate": "20260215120000",
        "vnp_CurrCode": "VND",
        "vnp_IpAddr": "127.0.0.1",
        "vnp_OrderInfo": "test",
        "vnp_OrderType": "billpayment",
        "vnp_ReturnUrl": "bitenexuser://payment/result",
        "vnp_TmnCode": settings.vnp_tmn_code,
        "vnp_TxnRef": "PAY-TEST-123",
        "vnp_Version": "2.1.0",
    }
    signed_url = build_vnpay_payment_url(
        base_url="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
        hash_secret=settings.vnp_hash_secret,
        params=payload,
    )
    secure_hash = parse_qs(urlparse(signed_url).query).get("vnp_SecureHash", [""])[0]
    signed_payload = {
        **payload,
        "vnp_SecureHash": secure_hash,
    }
    assert verify_vnpay_signature(signed_payload, settings.vnp_hash_secret) is True
    assert (
        verify_vnpay_signature({**signed_payload, "vnp_Amount": "999"}, settings.vnp_hash_secret)
        is False
    )


@pytest.mark.asyncio
async def test_create_cash_on_delivery_payment_confirms_order_without_redirect(
    client: AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    user_id = "user-payment-cod"
    merchant = Merchant(
        user_id="merchant-payment-cod",
        name="COD Merchant",
        slug=f"cod-merchant-{uuid4().hex[:8]}",
        address="7 Merchant St",
        city="Da Nang",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    order = _build_order(user_id=user_id, merchant_id=merchant.id)
    db_session.add(order)
    await db_session.flush()

    captured_trigger: dict[str, object] = {}

    def _capture_trigger(webhook_path: str, payload: dict) -> None:
        captured_trigger["webhook_path"] = webhook_path
        captured_trigger["payload"] = payload

    monkeypatch.setattr(N8nClient, "trigger", _capture_trigger)

    response = await client.post(
        "/api/v1/payments",
        json={
            "order_id": order.id,
            "amount": order.total,
            "currency": "VND",
            "method": "CASH_ON_DELIVERY",
        },
        headers=_auth_header(
            user_id,
            Role.USER,
            idempotency_key=f"idem-cod-{uuid4().hex[:8]}",
        ),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["method"] == "CASH_ON_DELIVERY"
    assert payload["gateway"] == "cash"
    assert payload["status"] == PaymentStatus.PENDING.value
    assert payload["payment_url"] is None

    refreshed_order = (
        await db_session.execute(select(Order).where(Order.id == order.id))
    ).scalar_one()
    assert refreshed_order.status == OrderStatus.CONFIRMED.value

    confirmed_history_count = (
        await db_session.execute(
            select(func.count(OrderStatusHistory.id)).where(
                OrderStatusHistory.order_id == order.id,
                OrderStatusHistory.to_status == OrderStatus.CONFIRMED.value,
            )
        )
    ).scalar_one()
    assert confirmed_history_count == 1

    assert captured_trigger["webhook_path"] == "/webhook/bitenex/order-status-changed"
    assert captured_trigger["payload"]["orderId"] == order.id
    assert captured_trigger["payload"]["fromStatus"] == OrderStatus.PENDING.value
    assert captured_trigger["payload"]["toStatus"] == OrderStatus.CONFIRMED.value
    assert captured_trigger["payload"]["changedAt"]


@pytest.mark.asyncio
async def test_create_payment_idempotency_replay_and_conflict(client: AsyncClient, db_session):
    user_id = "user-payment-idempotency"
    merchant = Merchant(
        user_id="merchant-payment-idempotency",
        name="Payment Merchant",
        slug=f"payment-merchant-{uuid4().hex[:8]}",
        address="5 Merchant St",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    order = _build_order(user_id=user_id, merchant_id=merchant.id)
    db_session.add(order)
    await db_session.flush()

    payload = {
        "order_id": order.id,
        "amount": order.total,
        "currency": "VND",
        "method": "VNPAY",
    }
    idem_key = f"idem-{uuid4().hex[:8]}"

    first_response = await client.post(
        "/api/v1/payments",
        json=payload,
        headers=_auth_header(user_id, Role.USER, idempotency_key=idem_key),
    )
    assert first_response.status_code == 201
    first_payload = first_response.json()

    replay_response = await client.post(
        "/api/v1/payments",
        json=payload,
        headers=_auth_header(user_id, Role.USER, idempotency_key=idem_key),
    )
    assert replay_response.status_code == 201
    replay_payload = replay_response.json()
    assert replay_payload["id"] == first_payload["id"]
    assert replay_payload["transaction_id"] == first_payload["transaction_id"]

    conflict_response = await client.post(
        "/api/v1/payments",
        json={**payload, "amount": order.total + 1},
        headers=_auth_header(user_id, Role.USER, idempotency_key=idem_key),
    )
    assert conflict_response.status_code == 409
    assert conflict_response.json()["error"]["error_code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_webhook_signature_dedup_and_exactly_once(client: AsyncClient, db_session):
    user_id = "user-payment-webhook"
    merchant = Merchant(
        user_id="merchant-payment-webhook",
        name="Webhook Merchant",
        slug=f"webhook-merchant-{uuid4().hex[:8]}",
        address="6 Merchant St",
        city="Hue",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    order = _build_order(user_id=user_id, merchant_id=merchant.id)
    db_session.add(order)
    await db_session.flush()

    payment = Payment(
        transaction_id=f"PAY-WEBHOOK-{uuid4().hex[:8].upper()}",
        order_id=order.id,
        user_id=user_id,
        amount=order.total,
        currency="VND",
        method="VNPAY",
        status=PaymentStatus.PROCESSING.value,
        gateway="vnpay",
    )
    db_session.add(payment)
    await db_session.flush()

    payload = {
        "vnp_Amount": str(int(order.total * 100)),
        "vnp_Command": "pay",
        "vnp_CreateDate": "20260215121500",
        "vnp_CurrCode": "VND",
        "vnp_IpAddr": "127.0.0.1",
        "vnp_OrderInfo": f"Payment for order {order.id}",
        "vnp_OrderType": "billpayment",
        "vnp_ResponseCode": "00",
        "vnp_ReturnUrl": "bitenexuser://payment/result",
        "vnp_TmnCode": settings.vnp_tmn_code,
        "vnp_TransactionNo": "123456789",
        "vnp_TransactionStatus": "00",
        "vnp_TxnRef": payment.transaction_id,
        "vnp_Version": "2.1.0",
        "vnp_PayDate": "20260215121600",
    }
    signed_url = build_vnpay_payment_url(
        base_url="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
        hash_secret=settings.vnp_hash_secret,
        params=payload,
    )
    payload["vnp_SecureHash"] = parse_qs(urlparse(signed_url).query)["vnp_SecureHash"][0]

    first_webhook = await client.get("/api/v1/payments/webhook/vnpay", params=payload)
    assert first_webhook.status_code == 200
    assert first_webhook.json()["status"] == "processed"

    duplicate_webhook = await client.get("/api/v1/payments/webhook/vnpay", params=payload)
    assert duplicate_webhook.status_code == 200
    assert duplicate_webhook.json()["status"] == "duplicate"

    refreshed_payment = (
        await db_session.execute(select(Payment).where(Payment.id == payment.id))
    ).scalar_one()
    assert refreshed_payment.status == PaymentStatus.COMPLETED.value

    refreshed_order = (
        await db_session.execute(select(Order).where(Order.id == order.id))
    ).scalar_one()
    assert refreshed_order.status == OrderStatus.CONFIRMED.value

    confirmed_history_count = (
        await db_session.execute(
            select(func.count(OrderStatusHistory.id)).where(
                OrderStatusHistory.order_id == order.id,
                OrderStatusHistory.to_status == OrderStatus.CONFIRMED.value,
            )
        )
    ).scalar_one()
    assert confirmed_history_count == 1

    webhook_count = (
        await db_session.execute(
            select(func.count(WebhookEvent.id)).where(
                WebhookEvent.gateway == "vnpay",
                WebhookEvent.transaction_id == payment.transaction_id,
            )
        )
    ).scalar_one()
    assert webhook_count == 1


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-payment-invalid-signature",
        name="Invalid Signature Merchant",
        slug=f"invalid-signature-{uuid4().hex[:8]}",
        address="7 Merchant St",
        city="Hanoi",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    order = _build_order(user_id="user-payment-invalid-signature", merchant_id=merchant.id)
    db_session.add(order)
    await db_session.flush()

    payment = Payment(
        transaction_id=f"PAY-BAD-SIGN-{uuid4().hex[:8].upper()}",
        order_id=order.id,
        user_id=order.user_id,
        amount=order.total,
        currency="VND",
        method="VNPAY",
        status=PaymentStatus.PROCESSING.value,
        gateway="vnpay",
    )
    db_session.add(payment)
    await db_session.flush()

    payload = {
        "vnp_TmnCode": settings.vnp_tmn_code,
        "vnp_TxnRef": payment.transaction_id,
        "vnp_ResponseCode": "00",
        "vnp_TransactionStatus": "00",
        "vnp_TransactionNo": "987654321",
        "vnp_PayDate": "20260215130000",
        "vnp_SecureHash": "INVALID_SIGNATURE",
    }

    response = await client.get("/api/v1/payments/webhook/vnpay", params=payload)
    assert response.status_code == 400
    assert response.json()["error"]["error_code"] == "INVALID_PAYMENT_SIGNATURE"

    refreshed_payment = (
        await db_session.execute(select(Payment).where(Payment.id == payment.id))
    ).scalar_one()
    assert refreshed_payment.status == PaymentStatus.PROCESSING.value
