from datetime import datetime
from enum import Enum

from pydantic import Field, field_validator, model_validator

from app.shared.dto import BaseDTO
from app.shared.enums import Role


class ChatConversationType(str, Enum):
    USER_DRIVER = "USER_DRIVER"
    MERCHANT_DRIVER = "MERCHANT_DRIVER"


class ChatMessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"


class ChatMessageCreate(BaseDTO):
    conversation_type: ChatConversationType
    content: str | None = Field(default=None, max_length=1000)
    message_type: ChatMessageType = ChatMessageType.TEXT
    media_url: str | None = Field(default=None, max_length=2048)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        content = value.strip()
        if len(content) > 1000:
            raise ValueError("Message content must be 1000 characters or fewer")
        return content

    @field_validator("media_url")
    @classmethod
    def validate_media_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        media_url = value.strip()
        if not media_url:
            return None
        return media_url

    @model_validator(mode="after")
    def validate_message_payload(self) -> "ChatMessageCreate":
        if self.message_type == ChatMessageType.TEXT and not self.content:
            raise ValueError("Message content is required")
        if self.message_type == ChatMessageType.IMAGE and not self.media_url:
            raise ValueError("Image message requires media_url")
        return self


class ChatMessageResponse(BaseDTO):
    id: str
    order_id: str
    conversation_type: ChatConversationType
    sender_user_id: str
    sender_role: Role
    sender_name: str | None = None
    sender_avatar_url: str | None = None
    content: str
    message_type: ChatMessageType
    media_url: str | None = None
    created_at: datetime


class ChatMessageListResponse(BaseDTO):
    items: list[ChatMessageResponse]
    total: int
