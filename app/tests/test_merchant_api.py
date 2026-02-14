import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.modules.merchant.models import Merchant
from app.modules.user.models import User
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

    owner_menu_resp = await client.get(
        "/api/v1/merchants/owner/menu/list?available_only=true&page=1&per_page=10",
        headers=_auth_header(owner.user_id, Role.MERCHANT),
    )
    assert owner_menu_resp.status_code == 200
    owner_menu_payload = owner_menu_resp.json()
    assert owner_menu_payload["total"] == 1
    assert owner_menu_payload["items"][0]["id"] == item_id


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


@pytest.mark.asyncio
async def test_admin_list_pending_merchants_with_owner_metadata(
    client: AsyncClient, db_session
):
    owner = User(
        email="pending.owner@example.com",
        password_hash="hash",
        full_name="Pending Owner",
        role=Role.MERCHANT.value,
        is_active=True,
        is_verified=True,
    )
    db_session.add(owner)
    await db_session.flush()

    pending = Merchant(
        user_id=owner.id,
        name="Pending List Merchant",
        slug="pending-list-merchant",
        address="9 Pending St",
        city="Can Tho",
        status=MerchantStatus.PENDING.value,
    )
    db_session.add(pending)
    await db_session.flush()

    response = await client.get(
        "/api/v1/merchants/admin/list?status=PENDING",
        headers=_auth_header("admin-user", Role.ADMIN),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == pending.id
    assert payload["items"][0]["owner_email"] == owner.email
    assert payload["items"][0]["owner_full_name"] == owner.full_name


@pytest.mark.asyncio
async def test_admin_detail_includes_menu_and_enforces_access(client: AsyncClient, db_session):
    owner = User(
        email="detail.owner@example.com",
        password_hash="hash",
        full_name="Detail Owner",
        role=Role.MERCHANT.value,
        is_active=True,
        is_verified=True,
    )
    db_session.add(owner)
    await db_session.flush()

    merchant = Merchant(
        user_id=owner.id,
        name="Detail Merchant",
        slug="detail-merchant",
        address="10 Detail St",
        city="Hanoi",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    created_item = await client.post(
        "/api/v1/merchants/owner/menu",
        json={
            "name": "Pho Bo",
            "description": "Special noodle",
            "price": 5.2,
            "category": "Noodles",
            "is_available": True,
        },
        headers=_auth_header(owner.id, Role.MERCHANT),
    )
    assert created_item.status_code == 201

    admin_detail = await client.get(
        f"/api/v1/merchants/admin/{merchant.id}?category=noodles",
        headers=_auth_header("admin-user", Role.ADMIN),
    )
    assert admin_detail.status_code == 200
    detail_payload = admin_detail.json()
    assert detail_payload["merchant"]["id"] == merchant.id
    assert detail_payload["merchant"]["owner_email"] == owner.email
    assert detail_payload["menu"]["total"] == 1
    assert detail_payload["menu"]["items"][0]["category"] == "Noodles"

    forbidden = await client.get(
        f"/api/v1/merchants/admin/{merchant.id}",
        headers=_auth_header(owner.id, Role.MERCHANT),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["error_code"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_owner_profile_validation_error_shape(client: AsyncClient, db_session):
    merchant = Merchant(
        user_id="merchant-validation-api",
        name="Validation Merchant",
        slug="validation-merchant",
        address="11 Validation St",
        city="Hue",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    response = await client.patch(
        "/api/v1/merchants/owner/profile",
        json={"latitude": 120},
        headers=_auth_header(merchant.user_id, Role.MERCHANT),
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["error_code"] == "VALIDATION_ERROR"
    assert "latitude" in error["details"]


@pytest.mark.asyncio
async def test_merchant_onboarding_end_to_end_flow(client: AsyncClient):
    register_response = await client.post(
        "/api/v1/auth/register/merchant",
        json={
            "email": "flow.merchant@example.com",
            "password": "SecurePass123",
            "full_name": "Flow Merchant",
            "business_name": "Flow Bistro",
            "phone": "+84901234567",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "flow.merchant@example.com", "password": "SecurePass123"},
    )
    assert login_response.status_code == 200
    merchant_access_token = login_response.json()["tokens"]["access_token"]

    pending_profile_response = await client.get(
        "/api/v1/merchants/owner/profile",
        headers={"Authorization": f"Bearer {merchant_access_token}"},
    )
    assert pending_profile_response.status_code == 200
    pending_profile = pending_profile_response.json()
    assert pending_profile["status"] == MerchantStatus.PENDING.value
    assert pending_profile["is_profile_complete"] is False

    approve_response = await client.post(
        f"/api/v1/merchants/{pending_profile['id']}/approve",
        headers=_auth_header("admin-user", Role.ADMIN),
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == MerchantStatus.ACTIVE.value

    setup_response = await client.patch(
        "/api/v1/merchants/owner/profile",
        json={
            "name": "Flow Bistro Updated",
            "description": "Profile completed",
            "address": "100 Flow St",
            "city": "Ho Chi Minh",
            "phone": "+84901234567",
            "latitude": 10.7626,
            "longitude": 106.6602,
            "min_order_amount": 0,
            "delivery_fee": 1.5,
            "estimated_prep_time": 25,
        },
        headers={"Authorization": f"Bearer {merchant_access_token}"},
    )
    assert setup_response.status_code == 200
    setup_payload = setup_response.json()
    assert setup_payload["status"] == MerchantStatus.ACTIVE.value
    assert setup_payload["is_profile_complete"] is True


@pytest.mark.asyncio
async def test_cross_app_visibility_flow_after_merchant_updates(client: AsyncClient):
    register_response = await client.post(
        "/api/v1/auth/register/merchant",
        json={
            "email": "cross.flow@example.com",
            "password": "SecurePass123",
            "full_name": "Cross Flow",
            "business_name": "Cross Kitchen",
            "phone": "+84901112233",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "cross.flow@example.com", "password": "SecurePass123"},
    )
    assert login_response.status_code == 200
    merchant_token = login_response.json()["tokens"]["access_token"]

    profile_response = await client.get(
        "/api/v1/merchants/owner/profile",
        headers={"Authorization": f"Bearer {merchant_token}"},
    )
    assert profile_response.status_code == 200
    merchant_profile = profile_response.json()

    approve_response = await client.post(
        f"/api/v1/merchants/{merchant_profile['id']}/approve",
        headers=_auth_header("admin-user", Role.ADMIN),
    )
    assert approve_response.status_code == 200

    patch_response = await client.patch(
        "/api/v1/merchants/owner/profile",
        json={
            "description": "Cross app profile",
            "address": "98 Visibility St",
            "city": "HCM",
            "latitude": 10.7,
            "longitude": 106.6,
            "min_order_amount": 0,
            "delivery_fee": 2.0,
            "estimated_prep_time": 20,
        },
        headers={"Authorization": f"Bearer {merchant_token}"},
    )
    assert patch_response.status_code == 200

    create_menu = await client.post(
        "/api/v1/merchants/owner/menu",
        json={
            "name": "Cross Burger",
            "description": "Visible on user + admin",
            "price": 6.5,
            "category": "Main",
            "is_available": True,
        },
        headers={"Authorization": f"Bearer {merchant_token}"},
    )
    assert create_menu.status_code == 201

    public_list = await client.get("/api/v1/merchants")
    assert public_list.status_code == 200
    list_payload = public_list.json()
    assert any(item["id"] == merchant_profile["id"] for item in list_payload["items"])

    public_menu = await client.get(
        f"/api/v1/merchants/{merchant_profile['id']}/menu?available_only=true",
    )
    assert public_menu.status_code == 200
    assert len(public_menu.json()) == 1
    assert public_menu.json()[0]["name"] == "Cross Burger"

    admin_detail = await client.get(
        f"/api/v1/merchants/admin/{merchant_profile['id']}",
        headers=_auth_header("admin-user", Role.ADMIN),
    )
    assert admin_detail.status_code == 200
    admin_payload = admin_detail.json()
    assert admin_payload["merchant"]["id"] == merchant_profile["id"]
    assert admin_payload["menu"]["total"] == 1
    assert admin_payload["menu"]["items"][0]["name"] == "Cross Burger"
