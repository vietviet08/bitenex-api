# =============================================================================
# Admin Module - Service Layer
# =============================================================================

from datetime import datetime, timezone
from typing import Any

import httpx
from openai import AsyncOpenAI, OpenAIError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.admin.ai_settings import run_ai_request_with_retry
from app.modules.admin.models import AdminAuditLog, SystemConfig
from app.modules.admin.schemas import (
    AIModelItem,
    AIModelListResponse,
    AISettingsResponse,
    AISettingsUpdate,
    AuditLogResponse,
    DashboardStats,
    DriverStatsResponse,
    MerchantStatsResponse,
    OrderStatsResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
    UserStatsResponse,
)
from app.modules.driver.models import Driver
from app.modules.merchant.models import Merchant
from app.modules.order.models import Order
from app.modules.user.models import User
from app.shared.enums import DriverStatus, MerchantStatus, OrderStatus


class AdminService:
    """
    Admin service.
    Provides administrative functions and statistics.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _mask_secret(value: str | None) -> str | None:
        if not value:
            return None
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    async def get_dashboard_stats(self) -> DashboardStats:
        """Get dashboard statistics."""
        # Total users
        total_users = (
            await self.db.execute(
                select(func.count()).where(User.is_deleted.is_(False))
            )
        ).scalar() or 0

        # Total drivers
        total_drivers = (
            await self.db.execute(
                select(func.count()).where(Driver.is_deleted.is_(False))
            )
        ).scalar() or 0

        # Total merchants
        total_merchants = (
            await self.db.execute(
                select(func.count()).where(Merchant.is_deleted.is_(False))
            )
        ).scalar() or 0

        # Total orders
        total_orders = (
            await self.db.execute(
                select(func.count()).where(Order.is_deleted.is_(False))
            )
        ).scalar() or 0

        # Pending orders
        pending_orders = (
            await self.db.execute(
                select(func.count()).where(
                    Order.is_deleted.is_(False),
                    Order.status == OrderStatus.PENDING.value,
                )
            )
        ).scalar() or 0

        # Today's revenue
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_revenue = (
            await self.db.execute(
                select(func.coalesce(func.sum(Order.total), 0.0)).where(
                    Order.is_deleted.is_(False),
                    Order.status == OrderStatus.DELIVERED.value,
                    Order.created_at >= today,
                )
            )
        ).scalar() or 0.0

        # Active drivers (online)
        active_drivers = (
            await self.db.execute(
                select(func.count()).where(
                    Driver.is_deleted.is_(False),
                    Driver.status == DriverStatus.ONLINE.value,
                )
            )
        ).scalar() or 0

        return DashboardStats(
            total_users=total_users,
            total_drivers=total_drivers,
            total_merchants=total_merchants,
            total_orders=total_orders,
            pending_orders=pending_orders,
            today_revenue=float(today_revenue),
            active_drivers=active_drivers,
        )

    async def get_user_stats(self) -> UserStatsResponse:
        """Get user statistics."""
        total = (
            await self.db.execute(
                select(func.count()).where(User.is_deleted.is_(False))
            )
        ).scalar() or 0

        active = (
            await self.db.execute(
                select(func.count()).where(
                    User.is_deleted.is_(False),
                    User.is_active.is_(True),
                )
            )
        ).scalar() or 0

        verified = (
            await self.db.execute(
                select(func.count()).where(
                    User.is_deleted.is_(False),
                    User.is_verified.is_(True),
                )
            )
        ).scalar() or 0

        # New users today
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        new_today = (
            await self.db.execute(
                select(func.count()).where(
                    User.is_deleted.is_(False),
                    User.created_at >= today,
                )
            )
        ).scalar() or 0

        # New users this week (last 7 days)
        from datetime import timedelta

        week_ago = today - timedelta(days=7)
        new_this_week = (
            await self.db.execute(
                select(func.count()).where(
                    User.is_deleted.is_(False),
                    User.created_at >= week_ago,
                )
            )
        ).scalar() or 0

        # New users this month (last 30 days)
        month_ago = today - timedelta(days=30)
        new_this_month = (
            await self.db.execute(
                select(func.count()).where(
                    User.is_deleted.is_(False),
                    User.created_at >= month_ago,
                )
            )
        ).scalar() or 0

        return UserStatsResponse(
            total=total,
            active=active,
            verified=verified,
            new_today=new_today,
            new_this_week=new_this_week,
            new_this_month=new_this_month,
        )

    async def get_order_stats(self) -> OrderStatsResponse:
        """Get order statistics."""
        total = (
            await self.db.execute(
                select(func.count()).where(Order.is_deleted.is_(False))
            )
        ).scalar() or 0

        # Orders by status
        status_counts = (
            await self.db.execute(
                select(Order.status, func.count())
                .where(Order.is_deleted.is_(False))
                .group_by(Order.status)
            )
        ).all()
        by_status = {status: count for status, count in status_counts}

        # Today's stats
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = (
            await self.db.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(Order.total), 0.0),
                ).where(
                    Order.is_deleted.is_(False),
                    Order.created_at >= today,
                )
            )
        ).one()
        today_count = today_result[0] or 0
        today_revenue = float(today_result[1] or 0.0)

        # This week's stats
        from datetime import timedelta

        week_ago = today - timedelta(days=7)
        week_result = (
            await self.db.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(Order.total), 0.0),
                ).where(
                    Order.is_deleted.is_(False),
                    Order.created_at >= week_ago,
                )
            )
        ).one()
        week_count = week_result[0] or 0
        week_revenue = float(week_result[1] or 0.0)

        return OrderStatsResponse(
            total=total,
            by_status=by_status,
            today_count=today_count,
            today_revenue=today_revenue,
            week_count=week_count,
            week_revenue=week_revenue,
        )

    async def get_merchant_stats(self) -> MerchantStatsResponse:
        """Get merchant statistics."""
        total = (
            await self.db.execute(
                select(func.count()).where(Merchant.is_deleted.is_(False))
            )
        ).scalar() or 0

        pending_approval = (
            await self.db.execute(
                select(func.count()).where(
                    Merchant.is_deleted.is_(False),
                    Merchant.status == MerchantStatus.PENDING.value,
                )
            )
        ).scalar() or 0

        active = (
            await self.db.execute(
                select(func.count()).where(
                    Merchant.is_deleted.is_(False),
                    Merchant.status == MerchantStatus.ACTIVE.value,
                )
            )
        ).scalar() or 0

        suspended = (
            await self.db.execute(
                select(func.count()).where(
                    Merchant.is_deleted.is_(False),
                    Merchant.status == MerchantStatus.SUSPENDED.value,
                )
            )
        ).scalar() or 0

        return MerchantStatsResponse(
            total=total,
            pending_approval=pending_approval,
            active=active,
            suspended=suspended,
        )

    async def get_driver_stats(self) -> DriverStatsResponse:
        """Get driver statistics."""
        total = (
            await self.db.execute(
                select(func.count()).where(Driver.is_deleted.is_(False))
            )
        ).scalar() or 0

        online = (
            await self.db.execute(
                select(func.count()).where(
                    Driver.is_deleted.is_(False),
                    Driver.status == DriverStatus.ONLINE.value,
                )
            )
        ).scalar() or 0

        busy = (
            await self.db.execute(
                select(func.count()).where(
                    Driver.is_deleted.is_(False),
                    Driver.status == DriverStatus.BUSY.value,
                )
            )
        ).scalar() or 0

        offline = (
            await self.db.execute(
                select(func.count()).where(
                    Driver.is_deleted.is_(False),
                    Driver.status == DriverStatus.OFFLINE.value,
                )
            )
        ).scalar() or 0

        pending_approval = (
            await self.db.execute(
                select(func.count()).where(
                    Driver.is_deleted.is_(False),
                    Driver.is_approved.is_(False),
                )
            )
        ).scalar() or 0

        return DriverStatsResponse(
            total=total,
            online=online,
            busy=busy,
            offline=offline,
            pending_approval=pending_approval,
        )

    async def get_audit_logs(
        self,
        admin_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[AuditLogResponse], int]:
        """Get audit logs with filters."""
        filters = [AdminAuditLog.is_deleted.is_(False)]
        if admin_id:
            filters.append(AdminAuditLog.admin_id == admin_id)
        if action:
            filters.append(AdminAuditLog.action == action)
        if resource_type:
            filters.append(AdminAuditLog.resource_type == resource_type)

        count_query = select(func.count()).where(*filters)
        total = (await self.db.execute(count_query)).scalar() or 0

        query = (
            select(AdminAuditLog)
            .where(*filters)
            .order_by(AdminAuditLog.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = (await self.db.execute(query)).scalars().all()
        return [AuditLogResponse.model_validate(row) for row in rows], total

    async def log_action(
        self,
        admin_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None,
        description: str,
        before_data: dict[str, Any] | None = None,
        after_data: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log an admin action."""
        log = AdminAuditLog(
            admin_id=admin_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            before_data=str(before_data) if before_data is not None else None,
            after_data=str(after_data) if after_data is not None else None,
            ip_address=ip_address,
        )
        self.db.add(log)
        await self.db.flush()

    # System configuration
    async def _get_config_model(self, key: str) -> SystemConfig | None:
        result = await self.db.execute(
            select(SystemConfig).where(
                SystemConfig.key == key,
                SystemConfig.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _get_config_value(self, key: str) -> str | None:
        config = await self._get_config_model(key)
        return config.value if config else None

    async def _upsert_config(
        self,
        key: str,
        value: str,
        *,
        description: str | None = None,
        is_sensitive: bool = False,
    ) -> SystemConfig:
        config = await self._get_config_model(key)
        if config is None:
            config = SystemConfig(
                key=key,
                value=value,
                description=description,
                is_sensitive=is_sensitive,
            )
            self.db.add(config)
        else:
            config.value = value
            if description is not None:
                config.description = description
            config.is_sensitive = is_sensitive
        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def get_config(self, key: str) -> SystemConfigResponse | None:
        """Get a system configuration value."""
        config = await self._get_config_model(key)
        if config is None:
            return None
        value = self._mask_secret(config.value) if config.is_sensitive else config.value
        return SystemConfigResponse(
            key=config.key,
            value=value or "",
            description=config.description,
        )

    async def get_all_configs(self) -> list[SystemConfigResponse]:
        """Get all system configurations."""
        result = await self.db.execute(
            select(SystemConfig)
            .where(SystemConfig.is_deleted.is_(False))
            .order_by(SystemConfig.key.asc())
        )
        configs = result.scalars().all()
        return [
            SystemConfigResponse(
                key=config.key,
                value=self._mask_secret(config.value) if config.is_sensitive else config.value,
                description=config.description,
            )
            for config in configs
        ]

    async def update_config(
        self,
        key: str,
        data: SystemConfigUpdate,
        admin_id: str,
    ) -> SystemConfigResponse:
        """Update a system configuration."""
        is_sensitive = key.endswith("api_key") or key.endswith("secret")
        config = await self._upsert_config(
            key,
            data.value,
            description=data.description,
            is_sensitive=is_sensitive,
        )
        await self.log_action(
            admin_id=admin_id,
            action="UPDATE_CONFIG",
            resource_type="system_config",
            resource_id=config.id,
            description=f"Updated system config {key}",
            after_data={"key": key},
        )
        return SystemConfigResponse(
            key=config.key,
            value=self._mask_secret(config.value) if config.is_sensitive else config.value,
            description=config.description,
        )

    async def get_ai_settings(self) -> AISettingsResponse:
        """Get AI provider settings without exposing the API key."""
        api_key = await self._get_config_value("ai.openai_api_key")
        base_url = await self._get_config_value("ai.openai_base_url")
        chat_model = await self._get_config_value("ai.openai_chat_model")
        return AISettingsResponse(
            api_key_configured=bool(api_key),
            api_key_masked=self._mask_secret(api_key),
            base_url=base_url,
            chat_model=chat_model,
        )

    async def update_ai_settings(
        self,
        data: AISettingsUpdate,
        admin_id: str,
    ) -> AISettingsResponse:
        """Persist AI provider settings."""
        base_url = data.base_url.strip().rstrip("/")
        chat_model = data.chat_model.strip()
        if not base_url:
            raise ValidationError(message="Base URL is required")
        if not chat_model:
            raise ValidationError(message="Chat model is required")

        if data.api_key is not None:
            api_key = data.api_key.strip()
            if api_key:
                await self._upsert_config(
                    "ai.openai_api_key",
                    api_key,
                    description="OpenAI-compatible API key for AI features",
                    is_sensitive=True,
                )

        await self._upsert_config(
            "ai.openai_base_url",
            base_url,
            description="OpenAI-compatible base URL for AI features",
        )
        await self._upsert_config(
            "ai.openai_chat_model",
            chat_model,
            description="Chat model used by semantic search and review summaries",
        )
        await self.log_action(
            admin_id=admin_id,
            action="UPDATE_AI_SETTINGS",
            resource_type="system_config",
            resource_id=None,
            description="Updated AI provider settings",
            after_data={"base_url": base_url, "chat_model": chat_model},
        )
        return await self.get_ai_settings()

    async def list_ai_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AIModelListResponse:
        """Load available models from an OpenAI-compatible provider."""
        resolved_api_key = (api_key or "").strip() or await self._get_config_value(
            "ai.openai_api_key"
        )
        resolved_base_url = (base_url or "").strip().rstrip("/") or await self._get_config_value(
            "ai.openai_base_url"
        )

        if not resolved_api_key:
            raise ValidationError(message="API key is required to load models")
        if not resolved_base_url:
            raise ValidationError(message="Base URL is required to load models")

        try:
            client = AsyncOpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
                http_client=httpx.AsyncClient(timeout=20),
                max_retries=0,
            )
            model_list = await run_ai_request_with_retry(
                client.models.list,
                operation_name="list models",
            )
            models = sorted(
                [AIModelItem(id=model.id) for model in model_list.data if model.id],
                key=lambda item: item.id,
            )
            return AIModelListResponse(models=models)
        except OpenAIError as exc:
            raise ExternalServiceError(message=f"Unable to load models: {exc}") from exc
        except Exception as exc:
            raise ExternalServiceError(message=f"Unable to load models: {exc}") from exc
