# =============================================================================
# Admin Module - Service Layer
# =============================================================================

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.schemas import (
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
from app.shared.enums import DriverStatus, MerchantStatus, OrderStatus, Role


class AdminService:
    """
    Admin service.
    Provides administrative functions and statistics.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

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
        # TODO: Implement
        raise NotImplementedError()

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
        # TODO: Implement
        pass

    # System configuration
    async def get_config(self, key: str) -> SystemConfigResponse | None:
        """Get a system configuration value."""
        # TODO: Implement
        raise NotImplementedError()

    async def get_all_configs(self) -> list[SystemConfigResponse]:
        """Get all system configurations."""
        # TODO: Implement
        raise NotImplementedError()

    async def update_config(
        self,
        key: str,
        data: SystemConfigUpdate,
        admin_id: str,
    ) -> SystemConfigResponse:
        """Update a system configuration."""
        # TODO: Implement
        raise NotImplementedError()
