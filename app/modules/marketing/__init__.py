# =============================================================================
# Marketing Module
# =============================================================================

from app.modules.marketing.models import Campaign  # noqa: F401
from app.modules.marketing.router import router

__all__ = ["router"]
