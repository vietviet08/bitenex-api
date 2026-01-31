# =============================================================================
# Admin Module - Pydantic Schemas
# =============================================================================

from datetime import datetime
from typing import Any

from pydantic import Field

from app.shared.dto import BaseDTO, TimestampMixin


class DashboardStats(BaseDTO):
    """Dashboard statistics."""

    total_users: int = 0
    total_drivers: int = 0
    total_merchants: int = 0
    total_orders: int = 0
    pending_orders: int = 0
    today_revenue: float = 0.0
    active_drivers: int = 0


class AuditLogResponse(BaseDTO, TimestampMixin):
    """Audit log entry response."""

    id: str
    admin_id: str
    action: str
    resource_type: str
    resource_id: str | None
    description: str
    ip_address: str | None


class AuditLogListResponse(BaseDTO):
    """Paginated audit log list."""

    items: list[AuditLogResponse]
    total: int


class SystemConfigResponse(BaseDTO):
    """System configuration response."""

    key: str
    value: str
    description: str | None


class SystemConfigUpdate(BaseDTO):
    """Update system configuration."""

    value: str
    description: str | None = None


class UserStatsResponse(BaseDTO):
    """User statistics response."""

    total: int
    active: int
    verified: int
    new_today: int
    new_this_week: int
    new_this_month: int


class OrderStatsResponse(BaseDTO):
    """Order statistics response."""

    total: int
    by_status: dict[str, int]
    today_count: int
    today_revenue: float
    week_count: int
    week_revenue: float


class MerchantStatsResponse(BaseDTO):
    """Merchant statistics response."""

    total: int
    pending_approval: int
    active: int
    suspended: int


class DriverStatsResponse(BaseDTO):
    """Driver statistics response."""

    total: int
    online: int
    busy: int
    offline: int
    pending_approval: int
