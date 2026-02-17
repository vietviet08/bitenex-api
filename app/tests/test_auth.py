import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_verification_token,
    hash_password,
)
from app.modules.merchant.models import Merchant
from app.modules.user.models import User
from app.shared.enums import MerchantStatus, Role


@pytest.fixture
async def test_user(db_session):
    """Create a test user for authentication tests."""
    user = User(
        email="test@example.com",
        password_hash=hash_password("password123"),
        full_name="Test User",
        role=Role.USER.value,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def unverified_user(db_session):
    """Create an unverified test user."""
    user = User(
        email="unverified@example.com",
        password_hash=hash_password("password123"),
        full_name="Unverified User",
        role=Role.USER.value,
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def inactive_user(db_session):
    """Create an inactive test user."""
    user = User(
        email="inactive@example.com",
        password_hash=hash_password("password123"),
        full_name="Inactive User",
        role=Role.USER.value,
        is_active=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


def auth_header(user: User) -> dict[str, str]:
    """Create authorization header for a user."""
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


class TestRegistration:
    """Tests for user registration."""

    async def test_register_success(self, client: AsyncClient):
        """Test successful user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "full_name": "New User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["full_name"] == "New User"
        assert data["user"]["role"] == "USER"
        assert data["user"]["is_verified"] is False
        assert "message" in data

    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration with existing email fails."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "securepassword123",
                "full_name": "Duplicate User",
            },
        )

        assert response.status_code == 409
        data = response.json()
        assert data["error"]["error_code"] == "DUPLICATE"

    async def test_register_weak_password(self, client: AsyncClient):
        """Test registration with short password fails."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@example.com",
                "password": "short",
                "full_name": "Weak Password User",
            },
        )

        assert response.status_code == 400  # Validation error

    async def test_register_merchant_success(self, client: AsyncClient, db_session):
        """Test successful merchant registration contract."""
        response = await client.post(
            "/api/v1/auth/register/merchant",
            json={
                "email": "merchant.new@example.com",
                "password": "securepassword123",
                "full_name": "Merchant Owner",
                "business_name": "Merchant Bistro",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user"]["email"] == "merchant.new@example.com"
        assert data["user"]["role"] == "MERCHANT"
        assert data["user"]["is_verified"] is True
        assert "Merchant registration successful" in data["message"]

        merchant_result = await db_session.execute(
            select(Merchant).where(Merchant.user_id == data["user"]["id"])
        )
        merchant = merchant_result.scalar_one_or_none()
        assert merchant is not None
        assert merchant.status == MerchantStatus.PENDING.value


class TestLogin:
    """Tests for user login."""

    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "tokens" in data
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]
        assert data["tokens"]["token_type"] == "bearer"
        assert data["user"]["email"] == test_user.email

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test login with wrong password fails."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient):
        """Test login with non-existent email fails."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 401

    async def test_login_inactive_user(self, client: AsyncClient, inactive_user: User):
        """Test login with inactive user fails."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": inactive_user.email,
                "password": "password123",
            },
        )

        assert response.status_code == 401


class TestTokenRefresh:
    """Tests for token refresh."""

    async def test_refresh_success(self, client: AsyncClient, test_user: User):
        """Test successful token refresh."""
        # First login to get tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )
        tokens = login_response.json()["tokens"]

        # Refresh the token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # New tokens should be different
        assert data["refresh_token"] != tokens["refresh_token"]

    async def test_refresh_with_revoked_token(self, client: AsyncClient, test_user: User):
        """Test refresh with revoked token fails."""
        # Login to get tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )
        tokens = login_response.json()["tokens"]

        # Refresh once (which revokes the original)
        await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )

        # Try to use the old token again
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert response.status_code == 401


class TestLogout:
    """Tests for logout functionality."""

    async def test_logout_success(self, client: AsyncClient, test_user: User):
        """Test successful logout."""
        # Login first
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )
        tokens = login_response.json()["tokens"]

        # Logout
        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        assert response.status_code == 200

        # Try to refresh with the revoked token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert refresh_response.status_code == 401

    async def test_logout_all(self, client: AsyncClient, test_user: User):
        """Test logout from all devices."""
        # Login twice to simulate multiple devices
        login1 = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "password123"},
        )
        tokens1 = login1.json()["tokens"]

        login2 = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "password123"},
        )
        tokens2 = login2.json()["tokens"]

        # Logout all
        response = await client.post(
            "/api/v1/auth/logout/all",
            headers={"Authorization": f"Bearer {tokens1['access_token']}"},
        )

        assert response.status_code == 200

        # Both refresh tokens should be revoked
        refresh1 = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens1["refresh_token"]},
        )
        assert refresh1.status_code == 401

        refresh2 = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens2["refresh_token"]},
        )
        assert refresh2.status_code == 401


class TestGetCurrentUser:
    """Tests for getting current user profile."""

    async def test_get_me_success(self, client: AsyncClient, test_user: User):
        """Test getting current user profile."""
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_header(test_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name
        assert data["role"] == test_user.role

    async def test_get_me_unauthorized(self, client: AsyncClient):
        """Test getting profile without auth fails."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401


class TestEmailVerification:
    """Tests for email verification."""

    async def test_verify_email_success(self, client: AsyncClient, unverified_user: User):
        """Test successful email verification."""
        token = create_verification_token(unverified_user.id)

        response = await client.get(f"/api/v1/auth/verify/{token}")

        assert response.status_code == 200

    async def test_verify_email_invalid_token(self, client: AsyncClient):
        """Test verification with invalid token fails."""
        response = await client.get("/api/v1/auth/verify/invalid-token")

        assert response.status_code == 400


class TestPasswordChange:
    """Tests for password change."""

    async def test_change_password_success(self, client: AsyncClient, test_user: User):
        """Test successful password change."""
        response = await client.post(
            "/api/v1/auth/password/change",
            json={
                "current_password": "password123",
                "new_password": "newpassword456",
            },
            headers=auth_header(test_user),
        )

        assert response.status_code == 200

        # Verify new password works
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "newpassword456",
            },
        )
        assert login_response.status_code == 200

    async def test_change_password_wrong_current(self, client: AsyncClient, test_user: User):
        """Test password change with wrong current password fails."""
        response = await client.post(
            "/api/v1/auth/password/change",
            json={
                "current_password": "wrongpassword",
                "new_password": "newpassword456",
            },
            headers=auth_header(test_user),
        )

        assert response.status_code == 401


class TestPasswordReset:
    """Tests for password reset flow."""

    async def test_request_reset_existing_email(self, client: AsyncClient, test_user: User):
        """Test password reset request for existing email."""
        response = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": test_user.email},
        )

        # Should always return 200 to prevent email enumeration
        assert response.status_code == 200

    async def test_request_reset_nonexistent_email(self, client: AsyncClient):
        """Test password reset request for non-existent email."""
        response = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": "nonexistent@example.com"},
        )

        # Should still return 200 to prevent email enumeration
        assert response.status_code == 200

    async def test_reset_password_success(self, client: AsyncClient, test_user: User):
        """Test successful password reset."""
        token = create_password_reset_token(test_user.id)

        response = await client.post(
            "/api/v1/auth/password/reset/confirm",
            json={
                "token": token,
                "new_password": "resetpassword789",
            },
        )

        assert response.status_code == 200

        # Verify new password works
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "resetpassword789",
            },
        )
        assert login_response.status_code == 200

    async def test_reset_password_invalid_token(self, client: AsyncClient):
        """Test password reset with invalid token fails."""
        response = await client.post(
            "/api/v1/auth/password/reset/confirm",
            json={
                "token": "invalid-token",
                "new_password": "newpassword123",
            },
        )

        assert response.status_code == 400
