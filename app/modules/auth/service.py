import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    create_verification_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_password_reset_token,
    verify_refresh_token,
    verify_verification_token,
)
from app.modules.auth.models import RefreshToken
from app.modules.auth.schemas import (
    AuthUserResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.modules.user.models import User
from app.shared.enums import Role
from app.shared.utils import ensure_utc

logger = logging.getLogger(__name__)
settings = get_settings()


class AuthService:
    """
    Authentication service handling login, registration, and token management.
    
    All authentication business logic should be implemented here.
    Routers should only call service methods, not implement logic.
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize service with database session.
        
        Args:
            db: Async database session from dependency injection
        """
        self.db = db
    
    async def _get_user_by_email(self, email: str) -> User | None:
        """Get user by email address."""
        result = await self.db.execute(
            select(User).where(
                User.email == email.lower(),
                User.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()
    
    async def _create_refresh_token_record(
        self,
        user_id: str,
        token: str,
        expires_at: datetime,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshToken:
        """Create and store a refresh token record."""
        token_hash = hash_refresh_token(token)
        
        refresh_token = RefreshToken(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )
        
        self.db.add(refresh_token)
        await self.db.flush()
        
        return refresh_token
    
    def _build_auth_user_response(self, user: User) -> AuthUserResponse:
        """Build AuthUserResponse from User model."""
        return AuthUserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=Role(user.role),
            is_verified=user.is_verified,
            created_at=user.created_at,
        )
    
    async def login(self, request: LoginRequest) -> LoginResponse:
        """
        Authenticate user and return tokens.
        
        Args:
            request: Login credentials
            
        Returns:
            LoginResponse with tokens and user info
            
        Raises:
            AuthenticationError: If credentials are invalid
        """
        # 1. Find user by email
        user = await self._get_user_by_email(str(request.email))
        
        if not user:
            # Use generic message to prevent user enumeration
            raise AuthenticationError("Invalid email or password")
        
        # 2. Verify password
        if not verify_password(request.password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        
        # 3. Check is_active
        if not user.is_active:
            raise AuthenticationError("Account has been deactivated")
        
        # 4. Create token pair
        access_token = create_access_token(user.id, user.role)
        refresh_token = create_refresh_token(user.id, user.role)
        
        # 5. Store refresh token
        # Parse expiry from settings
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
        
        await self._create_refresh_token_record(
            user_id=user.id,
            token=refresh_token,
            expires_at=expires_at,
        )
        
        logger.info(f"User {user.email} logged in successfully")
        
        # 6. Return response
        return LoginResponse(
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=settings.access_token_expire_minutes * 60,
            ),
            user=self._build_auth_user_response(user),
        )
    
    async def register(self, request: RegisterRequest) -> RegisterResponse:
        """
        Register a new user.
        
        Args:
            request: Registration data
            
        Returns:
            RegisterResponse with user info
            
        Raises:
            ConflictError: If email already exists
        """
        # 1. Check if email exists
        existing_user = await self._get_user_by_email(str(request.email))
        
        if existing_user:
            raise ConflictError(
                message="Email already registered",
                error_code="DUPLICATE",
            )
        
        # 2. Hash password
        password_hash = hash_password(request.password)
        
        # 3. Create user record
        user = User(
            email=str(request.email).lower(),
            password_hash=password_hash,
            full_name=request.full_name,
            phone=request.phone,
            role=Role.USER.value,
            is_active=True,
            is_verified=False,
        )
        
        self.db.add(user)
        await self.db.flush()
        
        # 4. Generate verification token
        verification_token = create_verification_token(user.id)
        
        # 5. Log verification URL (email sending out of scope)
        logger.info(
            f"Verification token for {user.email}: "
            f"/api/v1/auth/verify/{verification_token}"
        )
        
        logger.info(f"User {user.email} registered successfully")
        
        # 6. Return response
        return RegisterResponse(
            user=self._build_auth_user_response(user),
            message="Registration successful. Please verify your email.",
        )
    
    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New token pair
            
        Raises:
            AuthenticationError: If refresh token is invalid
        """
        # 1. Verify refresh token signature and type
        payload = verify_refresh_token(refresh_token)
        
        user_id = payload.get("sub")
        role = payload.get("role")
        
        if not user_id or not role:
            raise AuthenticationError("Invalid token payload")
        
        # 2. Find token in DB by hash
        token_hash = hash_refresh_token(refresh_token)
        
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_deleted == False,
            )
        )
        stored_token = result.scalar_one_or_none()
        
        if not stored_token:
            raise AuthenticationError("Refresh token not found")
        
        # 3. Check not revoked and not expired
        if stored_token.is_revoked:
            raise AuthenticationError("Refresh token has been revoked")
        
        expires_at = ensure_utc(stored_token.expires_at)
        if expires_at < datetime.now(timezone.utc):
            raise AuthenticationError("Refresh token has expired")
        
        # 4. Revoke current token
        stored_token.is_revoked = True
        stored_token.revoked_at = datetime.now(timezone.utc)
        
        await self.db.commit()

        # 5. Create new token pair
        new_access_token = create_access_token(user_id, role)
        new_refresh_token = create_refresh_token(user_id, role)
        
        # 6. Store new refresh token
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
        
        await self._create_refresh_token_record(
            user_id=user_id,
            token=new_refresh_token,
            expires_at=expires_at,
        )

        await self.db.commit()
        
        logger.info(f"Tokens refreshed for user {user_id}")
        
        # 7. Return TokenResponse
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
        )
    
    async def logout(self, user_id: str, refresh_token: str) -> None:
        """
        Logout user by revoking refresh token.
        
        Args:
            user_id: Current user ID
            refresh_token: Token to revoke
        """
        # 1. Hash provided refresh token
        token_hash = hash_refresh_token(refresh_token)
        
        # 2. Find and revoke matching token for user
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == user_id,
                RefreshToken.is_deleted == False,
            )
        )
        stored_token = result.scalar_one_or_none()
        
        # 3. No error if token not found (idempotent)
        if stored_token and not stored_token.is_revoked:
            stored_token.is_revoked = True
            stored_token.revoked_at = datetime.now(timezone.utc)
            logger.info(f"User {user_id} logged out")
    
    async def logout_all(self, user_id: str) -> None:
        """
        Logout from all devices by revoking all refresh tokens.
        
        Args:
            user_id: User to logout
        """
        # Bulk update: is_revoked=True, revoked_at=now
        now = datetime.now(timezone.utc)
        
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
                RefreshToken.is_deleted == False,
            )
            .values(
                is_revoked=True,
                revoked_at=now,
            )
        )
        
        logger.info(f"User {user_id} logged out from all devices")
    
    async def verify_email(self, token: str) -> bool:
        """
        Verify user's email with verification token.
        
        Args:
            token: Email verification token
            
        Returns:
            True if verified successfully
            
        Raises:
            ValidationError: If token is invalid
            NotFoundError: If user not found
        """
        # 1. Decode verification token
        try:
            payload = verify_verification_token(token)
        except Exception:
            raise ValidationError(
                message="Invalid or expired verification token",
                error_code="INVALID_TOKEN",
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise ValidationError(
                message="Invalid verification token",
                error_code="INVALID_TOKEN",
            )
        
        # 2. Find user by sub claim
        user = await self._get_user_by_id(user_id)
        
        if not user:
            raise NotFoundError(message="User not found")
        
        # 3. Set is_verified=True
        user.is_verified = True
        
        logger.info(f"Email verified for user {user.email}")
        
        return True
    
    async def request_password_reset(self, email: str) -> None:
        """
        Initiate password reset flow.
        
        Args:
            email: User's email address
        """
        # 1. Find user by email (silent fail if not found)
        user = await self._get_user_by_email(email)
        
        if not user:
            # Silent fail - don't reveal if email exists
            logger.debug(f"Password reset requested for unknown email: {email}")
            return
        
        # 2. Generate reset token
        reset_token = create_password_reset_token(user.id)
        
        # 3. Log reset URL (email sending out of scope)
        logger.info(
            f"Password reset token for {user.email}: "
            f"/api/v1/auth/password/reset/confirm?token={reset_token}"
        )
    
    async def reset_password(self, token: str, new_password: str) -> None:
        """
        Complete password reset with token.
        
        Args:
            token: Password reset token
            new_password: New password
            
        Raises:
            ValidationError: If token is invalid
            NotFoundError: If user not found
        """
        # 1. Verify reset token
        try:
            payload = verify_password_reset_token(token)
        except Exception:
            raise ValidationError(
                message="Invalid or expired reset token",
                error_code="INVALID_TOKEN",
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise ValidationError(
                message="Invalid reset token",
                error_code="INVALID_TOKEN",
            )
        
        # 2. Find user
        user = await self._get_user_by_id(user_id)
        
        if not user:
            raise NotFoundError(message="User not found")
        
        # 3. Update password
        user.password_hash = hash_password(new_password)
        
        # 4. Revoke all refresh tokens
        await self.logout_all(user_id)
        
        logger.info(f"Password reset for user {user.email}")
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> None:
        """
        Change password for authenticated user.
        
        Args:
            user_id: Current user ID
            current_password: Current password for verification
            new_password: New password
            
        Raises:
            NotFoundError: If user not found
            AuthenticationError: If current password is wrong
        """
        # 1. Find user
        user = await self._get_user_by_id(user_id)
        
        if not user:
            raise NotFoundError(message="User not found")
        
        # 2. Verify current password
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")
        
        # 3. Update to new password
        user.password_hash = hash_password(new_password)
        
        logger.info(f"Password changed for user {user.email}")
    
    async def get_current_user(self, user_id: str) -> AuthUserResponse:
        """
        Get current user's profile.
        
        Args:
            user_id: Current user ID
            
        Returns:
            AuthUserResponse with user info
            
        Raises:
            NotFoundError: If user not found
        """
        user = await self._get_user_by_id(user_id)
        
        if not user:
            raise NotFoundError(message="User not found")
        
        return self._build_auth_user_response(user)
