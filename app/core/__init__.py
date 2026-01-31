# =============================================================================
# Core Module Exports
# =============================================================================

from app.core.config import get_settings
from app.core.database import Base, async_session_maker, engine, get_db
from app.core.dependencies import (
    CurrentUser,
    OptionalUser,
    RequireAdmin,
    RequireDriver,
    RequireMerchant,
    RequireUser,
    get_current_user,
    get_current_user_optional,
    require_role,
)
from app.core.events import Event, dispatcher, emit_event
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BitenexException,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)

__all__ = [
    # Config
    "get_settings",
    # Database
    "Base",
    "get_db",
    "async_session_maker",
    "engine",
    # Dependencies
    "CurrentUser",
    "OptionalUser",
    "get_current_user",
    "get_current_user_optional",
    "require_role",
    "RequireAdmin",
    "RequireMerchant",
    "RequireDriver",
    "RequireUser",
    # Exceptions
    "BitenexException",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    # Security
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "create_token_pair",
    "decode_token",
    # Events
    "dispatcher",
    "emit_event",
    "Event",
]
