# =============================================================================
# Modules Package
# =============================================================================
# This package contains all business modules for the application.
# Each module is independent and follows the same structure:
# - router.py: API endpoints
# - service.py: Business logic
# - models.py: ORM models
# - schemas.py: Pydantic schemas
# =============================================================================

from app.modules.base import BaseModel, TimestampMixin

__all__ = ["BaseModel", "TimestampMixin"]
