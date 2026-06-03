from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel


class ChatMessage(BaseModel):
    """Persisted message for an order-scoped conversation."""

    __tablename__ = "chat_messages"

    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    conversation_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    sender_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sender_role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
