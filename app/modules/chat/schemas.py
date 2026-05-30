from datetime import datetime
from enum import Enum

from pydantic import Field, field_validator

from app.shared.dto import BaseDTO
from app.shared.enums import Role


class ChatConversationType(str, Enum):
    USER_DRIVER = "USER_DRIVER"
    MERCHANT_DRIVER = "MERCHANT_DRIVER"


class ChatMessageCreate(BaseDTO):
    conversation_type: ChatConversationType
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        content = value.strip()
        if not content:
            raise ValueError("Message content is required")
        if len(content) > 1000:
            raise ValueError("Message content must be 1000 characters or fewer")
        return content


class ChatMessageResponse(BaseDTO):
    id: str
    order_id: str
    conversation_type: ChatConversationType
    sender_user_id: str
    sender_role: Role
    sender_name: str | None = None
    sender_avatar_url: str | None = None
    content: str
    message_type: str
    created_at: datetime


class ChatMessageListResponse(BaseDTO):
    items: list[ChatMessageResponse]
    total: int
