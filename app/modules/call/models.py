from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel


class OrderCall(BaseModel):
    """Voice call session bound to an assigned delivery order."""

    __tablename__ = "order_calls"

    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    caller_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    callee_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    caller_role: Mapped[str] = mapped_column(String(20), nullable=False)
    callee_role: Mapped[str] = mapped_column(String(20), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ended_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
