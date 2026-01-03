# =============================================================================
# Dependency Injection - Authentication & Authorization
# =============================================================================
# This module provides FastAPI dependencies for authentication and
# role-based access control.
#
# Architectural Intent:
# - Centralized authentication logic
# - Declarative role-based authorization
# - Composable dependencies for different access levels
# =============================================================================

from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, InsufficientRoleError
from app.core.security import verify_access_token
from app.shared.enums import Role


# =============================================================================
# Security Scheme
# =============================================================================
# OAuth2 Bearer token authentication
security = HTTPBearer(auto_error=False)


# =============================================================================
# Token Payload Data Class
# =============================================================================
class TokenPayload:
    """
    Represents the decoded JWT token payload.
    Used as a dependency to access current user information.
    """
    
    def __init__(self, user_id: str, role: str):
        self.user_id = user_id
        self.role = Role(role)
    
    def has_role(self, *roles: Role) -> bool:
        """Check if user has any of the specified roles."""
        return self.role in roles
    
    def __repr__(self) -> str:
        return f"TokenPayload(user_id={self.user_id}, role={self.role})"


# =============================================================================
# Authentication Dependency
# =============================================================================
async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security)
    ],
) -> TokenPayload:
    """
    Dependency to get the current authenticated user.
    Extracts and validates the JWT token from Authorization header.
    
    Usage:
        @router.get("/me")
        async def get_me(user: TokenPayload = Depends(get_current_user)):
            return {"user_id": user.user_id, "role": user.role}
    
    Raises:
        AuthenticationError: If token is missing or invalid
    """
    if not credentials:
        raise AuthenticationError("Missing authentication token")
    
    payload = verify_access_token(credentials.credentials)
    
    user_id = payload.get("sub")
    role = payload.get("role")
    
    if not user_id or not role:
        raise AuthenticationError("Invalid token payload")
    
    return TokenPayload(user_id=user_id, role=role)


# Type alias for dependency injection
CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]


# =============================================================================
# Role-Based Authorization Dependencies
# =============================================================================
class RoleChecker:
    """
    Dependency factory for role-based access control.
    
    Usage:
        # Require specific role
        @router.get("/admin-only", dependencies=[Depends(require_role(Role.ADMIN))])
        async def admin_endpoint():
            ...
        
        # Or use in function signature
        @router.get("/drivers")
        async def get_drivers(
            user: TokenPayload = Depends(require_role(Role.ADMIN, Role.MERCHANT))
        ):
            ...
    """
    
    def __init__(self, *allowed_roles: Role):
        self.allowed_roles = allowed_roles
    
    async def __call__(
        self,
        user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if not self.allowed_roles:
            return user
        
        if user.role not in self.allowed_roles:
            raise InsufficientRoleError(
                message=f"Required roles: {[r.value for r in self.allowed_roles]}",
                details={"current_role": user.role.value},
            )
        
        return user


def require_role(*roles: Role) -> RoleChecker:
    """
    Factory function to create role-checking dependencies.
    
    Args:
        *roles: Roles that are allowed to access the endpoint
        
    Returns:
        RoleChecker dependency
        
    Example:
        @router.delete("/users/{id}", dependencies=[Depends(require_role(Role.ADMIN))])
        async def delete_user(id: str):
            ...
    """
    return RoleChecker(*roles)


# =============================================================================
# Pre-configured Role Dependencies
# =============================================================================
# These can be used directly in route decorators for common patterns

RequireAdmin = Depends(require_role(Role.ADMIN))
RequireMerchant = Depends(require_role(Role.MERCHANT, Role.ADMIN))
RequireDriver = Depends(require_role(Role.DRIVER, Role.ADMIN))
RequireUser = Depends(require_role(Role.USER, Role.ADMIN))


# =============================================================================
# Optional Authentication
# =============================================================================
async def get_current_user_optional(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security)
    ],
) -> TokenPayload | None:
    """
    Optional authentication dependency.
    Returns None if no token provided, otherwise validates the token.
    
    Useful for endpoints that behave differently for authenticated users.
    """
    if not credentials:
        return None
    
    try:
        payload = verify_access_token(credentials.credentials)
        return TokenPayload(
            user_id=payload.get("sub", ""),
            role=payload.get("role", ""),
        )
    except Exception:
        return None


OptionalUser = Annotated[TokenPayload | None, Depends(get_current_user_optional)]
