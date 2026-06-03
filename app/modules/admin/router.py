# =============================================================================
# Admin Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdmin
from app.core.exceptions import NotFoundError
from app.modules.admin.schemas import (
    AIModelListRequest,
    AIModelListResponse,
    AISettingsResponse,
    AISettingsUpdate,
    AuditLogListResponse,
    DashboardStats,
    DriverStatsResponse,
    MerchantStatsResponse,
    OrderStatsResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
    UserStatsResponse,
)
from app.modules.admin.service import AdminService

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[RequireAdmin],  # All endpoints require admin role
)


def get_admin_service(
    db: AsyncSession = Depends(get_db),
) -> AdminService:
    return AdminService(db)


# =============================================================================
# Dashboard
# =============================================================================
@router.get(
    "/dashboard",
    response_model=DashboardStats,
    summary="Get dashboard stats",
)
async def get_dashboard(
    service: AdminService = Depends(get_admin_service),
) -> DashboardStats:
    """Get dashboard statistics overview."""
    return await service.get_dashboard_stats()


# =============================================================================
# Statistics
# =============================================================================
@router.get(
    "/stats/users",
    response_model=UserStatsResponse,
    summary="Get user statistics",
)
async def get_user_stats(
    service: AdminService = Depends(get_admin_service),
) -> UserStatsResponse:
    """Get detailed user statistics."""
    return await service.get_user_stats()


@router.get(
    "/stats/orders",
    response_model=OrderStatsResponse,
    summary="Get order statistics",
)
async def get_order_stats(
    service: AdminService = Depends(get_admin_service),
) -> OrderStatsResponse:
    """Get detailed order statistics."""
    return await service.get_order_stats()


@router.get(
    "/stats/merchants",
    response_model=MerchantStatsResponse,
    summary="Get merchant statistics",
)
async def get_merchant_stats(
    service: AdminService = Depends(get_admin_service),
) -> MerchantStatsResponse:
    """Get detailed merchant statistics."""
    return await service.get_merchant_stats()


@router.get(
    "/stats/drivers",
    response_model=DriverStatsResponse,
    summary="Get driver statistics",
)
async def get_driver_stats(
    service: AdminService = Depends(get_admin_service),
) -> DriverStatsResponse:
    """Get detailed driver statistics."""
    return await service.get_driver_stats()


# =============================================================================
# Audit Logs
# =============================================================================
@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="Get audit logs",
)
async def get_audit_logs(
    admin_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: AdminService = Depends(get_admin_service),
) -> AuditLogListResponse:
    """Get audit logs with optional filters."""
    items, total = await service.get_audit_logs(admin_id, action, resource_type, page, per_page)
    return AuditLogListResponse(items=items, total=total)


# =============================================================================
# System Configuration
# =============================================================================
@router.get(
    "/config",
    response_model=list[SystemConfigResponse],
    summary="Get all configurations",
)
async def get_all_configs(
    service: AdminService = Depends(get_admin_service),
) -> list[SystemConfigResponse]:
    """Get all system configurations."""
    return await service.get_all_configs()


@router.get(
    "/config/{key}",
    response_model=SystemConfigResponse,
    summary="Get configuration",
)
async def get_config(
    key: str,
    service: AdminService = Depends(get_admin_service),
) -> SystemConfigResponse:
    """Get a specific configuration value."""
    config = await service.get_config(key)
    if config is None:
        raise NotFoundError("Config", key)
    return config


@router.put(
    "/config/{key}",
    response_model=SystemConfigResponse,
    summary="Update configuration",
)
async def update_config(
    key: str,
    data: SystemConfigUpdate,
    user: CurrentUser,
    service: AdminService = Depends(get_admin_service),
) -> SystemConfigResponse:
    """Update a system configuration value."""
    return await service.update_config(key, data, user.user_id)


# =============================================================================
# AI Settings
# =============================================================================
@router.get(
    "/ai-settings",
    response_model=AISettingsResponse,
    summary="Get AI provider settings",
)
async def get_ai_settings(
    service: AdminService = Depends(get_admin_service),
) -> AISettingsResponse:
    """Get OpenAI-compatible provider settings without exposing the API key."""
    return await service.get_ai_settings()


@router.put(
    "/ai-settings",
    response_model=AISettingsResponse,
    summary="Update AI provider settings",
)
async def update_ai_settings(
    data: AISettingsUpdate,
    user: CurrentUser,
    service: AdminService = Depends(get_admin_service),
) -> AISettingsResponse:
    """Update OpenAI-compatible provider settings."""
    return await service.update_ai_settings(data, user.user_id)


@router.post(
    "/ai-settings/models",
    response_model=AIModelListResponse,
    summary="Load AI provider models",
)
async def list_ai_models(
    data: AIModelListRequest,
    service: AdminService = Depends(get_admin_service),
) -> AIModelListResponse:
    """Load available models using supplied or saved provider credentials."""
    return await service.list_ai_models(api_key=data.api_key, base_url=data.base_url)
