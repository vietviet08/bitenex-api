from datetime import datetime

from pydantic import Field

from app.shared.dto import BaseDTO
from app.shared.enums import Role


class LoginRequest(BaseDTO):
    """Login request with email and password."""

    email: str = Field(pattern=r"^.+@.+$", max_length=255)
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseDTO):
    """User registration request."""

    email: str = Field(pattern=r"^.+@.+$", max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)


class MerchantRegisterRequest(RegisterRequest):
    """Merchant registration request."""

    business_name: str | None = Field(default=None, min_length=2, max_length=100)


class RefreshTokenRequest(BaseDTO):
    """Token refresh request."""

    refresh_token: str


class ChangePasswordRequest(BaseDTO):
    """Password change request."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ResetPasswordRequest(BaseDTO):
    """Password reset request (forgot password flow)."""

    email: str = Field(pattern=r"^.+@.+$", max_length=255)


class ConfirmResetPasswordRequest(BaseDTO):
    """Confirm password reset with token."""

    token: str
    new_password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseDTO):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")


class AuthUserResponse(BaseDTO):
    """Authenticated user info response."""

    id: str
    email: str
    full_name: str
    role: Role
    is_verified: bool = False
    created_at: datetime


class LoginResponse(BaseDTO):
    """Complete login response with tokens and user info."""

    tokens: TokenResponse
    user: AuthUserResponse


class RegisterResponse(BaseDTO):
    """Registration response."""

    user: AuthUserResponse
    message: str = "Registration successful. Please verify your email."


class TokenPayloadDTO(BaseDTO):
    """Internal representation of JWT payload."""

    sub: str  # user_id
    role: Role
    type: str  # "access" or "refresh"
    exp: datetime
    iat: datetime
