from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.modules.merchant.models import Merchant
from app.shared.enums import MerchantStatus, Role, VoucherDiscountType


def _auth_header(user_id: str, role: Role) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_create_list_update_and_validate_voucher(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-owner-voucher-api",
        name="Voucher API Merchant",
        slug=f"voucher-api-{uuid4().hex[:8]}",
        address="11 Merchant St",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    create_response = await client.post(
        "/api/v1/vouchers",
        json={
            "code": "HOTDEAL",
            "description": "10% off",
            "merchant_id": merchant.id,
            "discount_type": VoucherDiscountType.PERCENTAGE.value,
            "discount_value": 10,
            "max_discount_amount": 25,
            "min_order_amount": 100,
            "usage_limit": 100,
            "per_user_limit": 2,
            "starts_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "is_active": True,
        },
        headers=_auth_header("admin-voucher-api", Role.ADMIN),
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["code"] == "HOTDEAL"
    assert created["usage_count"] == 0

    list_response = await client.get(
        "/api/v1/vouchers",
        params={"merchant_id": merchant.id},
        headers=_auth_header("admin-voucher-api", Role.ADMIN),
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["code"] == "HOTDEAL"

    update_response = await client.put(
        f"/api/v1/vouchers/{created['id']}",
        json={
            "discount_type": VoucherDiscountType.FIXED_AMOUNT.value,
            "discount_value": 30000,
        },
        headers=_auth_header("admin-voucher-api", Role.ADMIN),
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["discount_type"] == VoucherDiscountType.FIXED_AMOUNT.value
    assert updated["discount_value"] == 30000.0

    validate_response = await client.post(
        "/api/v1/vouchers/validate",
        json={
            "code": "hotdeal",
            "merchant_id": merchant.id,
            "subtotal": 150000,
        },
        headers=_auth_header("user-voucher-api", Role.USER),
    )
    assert validate_response.status_code == 200
    validate_payload = validate_response.json()
    assert validate_payload["is_valid"] is True
    assert validate_payload["discount_amount"] == 30000.0
    assert validate_payload["total_after_discount"] == 120000.0
