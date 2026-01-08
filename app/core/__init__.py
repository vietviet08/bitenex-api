# =============================================================================
# Core Module Exports
# =============================================================================

from app.core.config import get_settings
from app.core.database import Base, get_db, async_session_maker, engine
from app.core.dependencies import (
    CurrentUser,
    OptionalUser,
    get_current_user,
    get_current_user_optional,
    require_role,
    RequireAdmin,
    RequireMerchant,
    RequireDriver,
    RequireUser,
)
from app.core.exceptions import (
    BitenexException,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
)
from app.core.events import dispatcher, emit_event, Event

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
