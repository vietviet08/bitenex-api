from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel


class RefreshToken(BaseModel):
    """
    Stores refresh tokens for JWT rotation.
    Enables token revocation and session management.
    """
    
    __tablename__ = "refresh_tokens"
    
    # Token data
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Owner
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Expiration
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    
    # Revocation
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Device/session info
    device_info: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )


class TokenBlacklist(BaseModel):
    """
    Blacklisted tokens for immediate invalidation.
    Used when tokens need to be revoked before expiry.
    """
    
    __tablename__ = "token_blacklist"
    
    token_jti: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
    )
    
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    
    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
