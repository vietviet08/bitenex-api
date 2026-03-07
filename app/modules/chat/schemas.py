# =============================================================================
# Chat Module - Pydantic Schemas
# =============================================================================

from app.shared.dto import BaseDTO


class ChatMessageResponse(BaseDTO):
    """
    Chat message payload used by REST history endpoint and realtime socket events.
    """

    message_id: str
    order_id: str
    sender_id: str
    receiver_id: str
    content: str
    message_type: str = "text"
    timestamp: str


class ChatMessageListResponse(BaseDTO):
    """Paginated chat messages for an order."""

    items: list[ChatMessageResponse]
    total: int
