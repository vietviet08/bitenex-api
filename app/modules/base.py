# =============================================================================
# Base ORM Model
# =============================================================================
# This module provides the base model class that all ORM models should inherit.
# Includes common fields like timestamps and soft delete.
#
# Architectural Intent:
# - Consistent model structure across all modules
# - Automatic timestamp management
# - Soft delete support for data retention
# =============================================================================

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BaseModel(Base):
    """
    Abstract base model with common fields.
    All domain models should inherit from this class.
    
    Provides:
    - UUID primary key
    - Created/updated timestamps with automatic management
    - Soft delete support
    """
    
    __abstract__ = True
    
    # Primary key - UUID string
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    
    # Timestamps - automatically managed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
    
    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"


class TimestampMixin:
    """
    Mixin for models that only need timestamps without soft delete.
    Useful for junction tables or audit logs.
    """
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
