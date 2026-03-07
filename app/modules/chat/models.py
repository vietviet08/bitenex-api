# =============================================================================
# Chat Module - ORM Models
# =============================================================================

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel


class ChatMessage(BaseModel):
    """
    Chat message exchanged between user and merchant for a specific order.
    """

    __tablename__ = "chat_messages"

    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    receiver_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="text",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
