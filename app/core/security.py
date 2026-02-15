import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, TokenExpiredError

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plain text password.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return cast(str, pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    return cast(bool, pwd_context.verify(plain_password, hashed_password))


def hash_refresh_token(token: str) -> str:
    """
    Hash a refresh token for secure storage.

    Uses SHA-256 to create a consistent hash that can be used
    for database lookups while preventing token theft if DB is compromised.

    Args:
        token: Raw JWT refresh token

    Returns:
        SHA-256 hex digest of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()


class TokenType:
    """Token type constants for JWT claims."""

    ACCESS = "access"
    REFRESH = "refresh"
    VERIFY = "verify"
    RESET = "reset"


def create_access_token(
    user_id: str,
    role: str,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a JWT access token.

    JWT Payload Format:
    {
        "sub": "user_id",
        "role": "USER | DRIVER | MERCHANT | ADMIN",
        "type": "access",
        "exp": <expiration_timestamp>,
        "iat": <issued_at_timestamp>
    }

    Args:
        user_id: Unique user identifier
        role: User role (USER, DRIVER, MERCHANT, ADMIN)
        additional_claims: Optional additional JWT claims

    Returns:
        Encoded JWT token string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": user_id,
        "role": role,
        "type": TokenType.ACCESS,
        "iat": now,
        "exp": expire,
    }

    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: str, role: str) -> str:
    """
    Create a JWT refresh token with longer expiration.

    Args:
        user_id: Unique user identifier
        role: User role

    Returns:
        Encoded JWT refresh token string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)

    payload = {
        "sub": user_id,
        "role": role,
        "type": TokenType.REFRESH,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_token_pair(user_id: str, role: str) -> dict[str, str]:
    """
    Create both access and refresh tokens.

    Args:
        user_id: Unique user identifier
        role: User role

    Returns:
        Dictionary with 'access_token' and 'refresh_token'
    """
    return {
        "access_token": create_access_token(user_id, role),
        "refresh_token": create_refresh_token(user_id, role),
        "token_type": "bearer",
    }


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: Encoded JWT token string

    Returns:
        Decoded token payload

    Raises:
        TokenExpiredError: If token has expired
        AuthenticationError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def verify_access_token(token: str) -> dict[str, Any]:
    """
    Verify that a token is a valid access token.

    Args:
        token: Encoded JWT token string

    Returns:
        Decoded token payload

    Raises:
        AuthenticationError: If not a valid access token
    """
    payload = decode_token(token)

    if payload.get("type") != TokenType.ACCESS:
        raise AuthenticationError("Invalid token type - expected access token")

    return payload


def verify_refresh_token(token: str) -> dict[str, Any]:
    """
    Verify that a token is a valid refresh token.

    Args:
        token: Encoded JWT token string

    Returns:
        Decoded token payload

    Raises:
        AuthenticationError: If not a valid refresh token
    """
    payload = decode_token(token)

    if payload.get("type") != TokenType.REFRESH:
        raise AuthenticationError("Invalid token type - expected refresh token")

    return payload


def create_verification_token(user_id: str) -> str:
    """
    Create a JWT token for email verification.

    Args:
        user_id: User ID to verify

    Returns:
        Encoded JWT verification token
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=24)  # 24 hour expiry

    payload = {
        "sub": user_id,
        "type": TokenType.VERIFY,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_verification_token(token: str) -> dict[str, Any]:
    """
    Verify an email verification token.

    Args:
        token: Encoded JWT verification token

    Returns:
        Decoded token payload

    Raises:
        AuthenticationError: If not a valid verification token
    """
    payload = decode_token(token)

    if payload.get("type") != TokenType.VERIFY:
        raise AuthenticationError("Invalid token type - expected verification token")

    return payload


def create_password_reset_token(user_id: str) -> str:
    """
    Create a JWT token for password reset.

    Args:
        user_id: User ID requesting reset

    Returns:
        Encoded JWT reset token
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=1)  # 1 hour expiry for security

    payload = {
        "sub": user_id,
        "type": TokenType.RESET,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_password_reset_token(token: str) -> dict[str, Any]:
    """
    Verify a password reset token.

    Args:
        token: Encoded JWT reset token

    Returns:
        Decoded token payload

    Raises:
        AuthenticationError: If not a valid reset token
    """
    payload = decode_token(token)

    if payload.get("type") != TokenType.RESET:
        raise AuthenticationError("Invalid token type - expected reset token")

    return payload
