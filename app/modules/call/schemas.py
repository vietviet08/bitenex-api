from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.shared.enums import Role


class CallStatus(str, Enum):
    RINGING = "RINGING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ENDED = "ENDED"
    MISSED = "MISSED"


class CallEndReason(str, Enum):
    CALLER_CANCELLED = "CALLER_CANCELLED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    FAILED = "FAILED"


class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    caller_user_id: str
    callee_user_id: str
    caller_role: Role
    callee_role: Role
    channel_name: str
    status: CallStatus
    started_at: datetime
    accepted_at: datetime | None
    ended_at: datetime | None
    expires_at: datetime
    ended_by: str | None
    end_reason: str | None


class CallTokenResponse(BaseModel):
    call: CallResponse
    agora_app_id: str
    agora_token: str
    agora_uid: int
    token_expires_at: datetime


class CallActionResponse(BaseModel):
    call: CallResponse
