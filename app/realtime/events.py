from enum import Enum
from typing import Any

from pydantic import BaseModel


class RealtimeEventType(str, Enum):
    """WebSocket event types."""

    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"

    # Order events
    ORDER_NEW = "order.new"
    ORDER_CREATED = "order.created"
    ORDER_UPDATED = "order.updated"
    ORDER_STATUS_CHANGED = "order.status_changed"
    ORDER_CANCELLED = "order.cancelled"

    # Driver events
    DRIVER_LOCATION_UPDATED = "driver.location_updated"
    DRIVER_STATUS_CHANGED = "driver.status_changed"
    DRIVER_ASSIGNED = "driver.assigned"

    # Dispatch events
    DISPATCH_NEW_ORDER = "dispatch.new_order"
    DISPATCH_ASSIGNMENT = "dispatch.assignment"
    DISPATCH_TIMEOUT = "dispatch.timeout"

    # Merchant events
    MERCHANT_NEW_ORDER = "merchant.new_order"
    MERCHANT_ORDER_UPDATE = "merchant.order_update"

    # Chat/messaging events
    CHAT_MESSAGE = "chat.message"
    CHAT_TYPING = "chat.typing"

    # Notification events
    NOTIFICATION_NEW = "notification.new"


class RealtimeEvent(BaseModel):
    """Base realtime event structure."""

    event: str
    data: dict[str, Any]
    timestamp: str | None = None


class LocationData(BaseModel):
    """Location update data."""

    user_id: str
    latitude: float
    longitude: float
    heading: float | None = None
    speed: float | None = None


class OrderEventData(BaseModel):
    """Order event data."""

    order_id: str
    status: str
    user_id: str | None = None
    driver_id: str | None = None
    merchant_id: str | None = None


class DispatchEventData(BaseModel):
    """Dispatch event data."""

    assignment_id: str
    order_id: str
    driver_id: str
    expires_at: str | None = None


class ChatMessageData(BaseModel):
    """Chat message data."""

    message_id: str
    sender_id: str
    receiver_id: str
    content: str
    message_type: str = "text"


def get_order_room(order_id: str) -> str:
    """Get room name for order updates."""
    return f"order:{order_id}"


def get_merchant_room(merchant_id: str) -> str:
    """Get room name for merchant updates."""
    return f"merchant:{merchant_id}"


def get_driver_room(driver_id: str) -> str:
    """Get room name for driver updates."""
    return f"driver:{driver_id}"


def get_user_room(user_id: str) -> str:
    """Get room name for user updates."""
    return f"user:{user_id}"


def get_chat_room(order_id: str) -> str:
    """Get room name for order chat."""
    return f"chat:{order_id}"
