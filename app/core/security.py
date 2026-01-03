# =============================================================================
# Security Module - JWT & Password Hashing
# =============================================================================
# This module provides security infrastructure for authentication.
# It handles JWT token creation/validation and password hashing.
#
# Architectural Intent:
# - Centralized security utilities
# - Stateless JWT authentication
# - Secure password hashing with bcrypt
# - Support for both access and refresh tokens
# =============================================================================

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthenticationError, TokenExpiredError


# =============================================================================
# Password Hashing Configuration
# =============================================================================
# Using bcrypt for password hashing - industry standard
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# Password Utilities
# =============================================================================
def hash_password(password: str) -> str:
    """
    Hash a plain text password.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


# =============================================================================
# JWT Token Types
# =============================================================================
class TokenType:
    """Token type constants for JWT claims."""
    ACCESS = "access"
    REFRESH = "refresh"


# =============================================================================
# JWT Token Creation
# =============================================================================
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
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
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
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
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
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "sub": user_id,
        "role": role,
        "type": TokenType.REFRESH,
        "iat": now,
        "exp": expire,
    }
    
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
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


# =============================================================================
# JWT Token Validation
# =============================================================================
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
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except JWTError as e:
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
