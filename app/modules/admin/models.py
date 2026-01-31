# =============================================================================
# Admin Module - ORM Models
# =============================================================================

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel


class AdminAuditLog(BaseModel):
    """
    Audit log for admin actions.
    Tracks all administrative operations for accountability.
    """

    __tablename__ = "admin_audit_logs"

    admin_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Store before/after data as JSON
    before_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    after_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )


class SystemConfig(BaseModel):
    """
    System-wide configuration settings.
    Key-value store for dynamic configuration.
    """

    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_sensitive: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
