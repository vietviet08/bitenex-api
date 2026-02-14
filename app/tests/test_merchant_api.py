import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.modules.merchant.models import Merchant
from app.shared.enums import MerchantStatus, Role


def _auth_header(user_id: str, role: Role) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_public_list_only_active_merchants(client: AsyncClient, db_session):
    active = Merchant(
        user_id="api-active-user",
        name="Active Merchant",
        slug="active-merchant",
        address="1 Active St",
        city="Hanoi",
        status=MerchantStatus.ACTIVE.value,
    )
    pending = Merchant(
        user_id="api-pending-user",
        name="Pending Merchant",
        slug="pending-merchant",
        address="2 Pending St",
        city="Hanoi",
        status=MerchantStatus.PENDING.value,
    )
    db_session.add_all([active, pending])
    await db_session.flush()

    response = await client.get("/api/v1/merchants")
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == active.id


@pytest.mark.asyncio
async def test_public_get_menu_not_found(client: AsyncClient):
    response = await client.get("/api/v1/merchants/not-found/menu")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["error_code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_owner_menu_create_and_ownership_guard(client: AsyncClient, db_session):
    owner = Merchant(
        user_id="merchant-owner-api",
        name="Owner API Merchant",
        slug="owner-api-merchant",
        address="5 Owner St",
        city="Hue",
        status=MerchantStatus.ACTIVE.value,
    )
    other = Merchant(
        user_id="merchant-other-api",
        name="Other API Merchant",
        slug="other-api-merchant",
        address="6 Other St",
        city="Hue",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add_all([owner, other])
    await db_session.flush()

    create_resp = await client.post(
        "/api/v1/merchants/owner/menu",
        json={
            "name": "Bun Bo",
            "description": "Spicy noodle",
            "price": 15.5,
            "category": "Main",
            "is_available": True,
        },
        headers=_auth_header(owner.user_id, Role.MERCHANT),
    )
    assert create_resp.status_code == 201
    item_payload = create_resp.json()
    item_id = item_payload["id"]
    assert item_payload["merchant_id"] == owner.id

    forbidden_resp = await client.patch(
        f"/api/v1/merchants/owner/menu/{item_id}",
        json={"name": "Hack Attempt"},
        headers=_auth_header(other.user_id, Role.MERCHANT),
    )
    assert forbidden_resp.status_code == 403
    assert forbidden_resp.json()["error"]["error_code"] == "AUTHORIZATION_ERROR"


@pytest.mark.asyncio
async def test_owner_endpoints_require_merchant_role(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-role-required",
        name="Role Required Merchant",
        slug="role-required-merchant",
        address="7 Role St",
        city="HCM",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    response = await client.get(
        "/api/v1/merchants/owner/profile",
        headers=_auth_header("normal-user", Role.USER),
    )
    assert response.status_code == 403
    assert response.json()["error"]["error_code"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_admin_can_approve_merchant(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-to-approve",
        name="Approve Me",
        slug="approve-me",
        address="8 Approve St",
        city="Da Nang",
        status=MerchantStatus.PENDING.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/merchants/{merchant.id}/approve",
        headers=_auth_header("admin-user", Role.ADMIN),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == merchant.id
    assert data["status"] == MerchantStatus.ACTIVE.value
