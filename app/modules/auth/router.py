from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.modules.auth.schemas import (
    AuthUserResponse,
    ChangePasswordRequest,
    ConfirmResetPasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from app.modules.auth.service import AuthService
from app.shared.dto import MessageResponse

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={
        401: {"description": "Authentication failed"},
        422: {"description": "Validation error"},
    },
)


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    """Dependency injection for AuthService."""
    return AuthService(db)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticate user with email and password, returns JWT tokens.",
)
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Authenticate user and return access/refresh tokens.
    """
    return await service.login(request)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User registration",
    description="Register a new user account.",
)
async def register(
    request: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> RegisterResponse:
    """
    Register a new user account.
    """
    return await service.register(request)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh tokens",
    description="Get new access token using refresh token.",
)
async def refresh_token(
    request: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Refresh access token using valid refresh token.
    """
    return await service.refresh_token(request.refresh_token)


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Send password reset email.",
)
async def request_password_reset(
    request: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Request password reset. Sends email if account exists.
    """
    await service.request_password_reset(request.email)
    return MessageResponse(
        message="If the email exists, a reset link has been sent."
    )


@router.post(
    "/password/reset/confirm",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset",
    description="Reset password using token from email.",
)
async def confirm_password_reset(
    request: ConfirmResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Reset password using token received via email.
    """
    await service.reset_password(request.token, request.new_password)
    return MessageResponse(message="Password has been reset successfully.")


@router.get(
    "/me",
    response_model=AuthUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Get the authenticated user's profile.",
)
async def get_me(
    user: CurrentUser,
    service: AuthService = Depends(get_auth_service),
) -> AuthUserResponse:
    """
    Get current authenticated user's profile.
    """
    return await service.get_current_user(user.user_id)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="Revoke current refresh token.",
)
async def logout(
    request: RefreshTokenRequest,
    user: CurrentUser,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Logout by revoking the provided refresh token.
    """
    await service.logout(user.user_id, request.refresh_token)
    return MessageResponse(message="Logged out successfully.")


@router.post(
    "/logout/all",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout from all devices",
    description="Revoke all refresh tokens for the user.",
)
async def logout_all(
    user: CurrentUser,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Logout from all devices by revoking all refresh tokens.
    """
    await service.logout_all(user.user_id)
    return MessageResponse(message="Logged out from all devices.")


@router.post(
    "/password/change",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description="Change password for authenticated user.",
)
async def change_password(
    request: ChangePasswordRequest,
    user: CurrentUser,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Change password for the current user.
    """
    await service.change_password(
        user.user_id,
        request.current_password,
        request.new_password,
    )
    return MessageResponse(message="Password changed successfully.")


@router.get(
    "/verify/{token}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify email",
    description="Verify user email with verification token.",
)
async def verify_email(
    token: str,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Verify user's email address with token.
    """
    await service.verify_email(token)
    return MessageResponse(message="Email verified successfully.")
