# =============================================================================
# Internal Event Dispatcher (Pub/Sub Pattern)
# =============================================================================
# This module provides a simple in-process event dispatcher for
# decoupling business logic using the pub/sub pattern.
#
# Architectural Intent:
# - Decouple modules through events instead of direct calls
# - Enable reactive patterns within the application
# - Foundation for future distributed event system
#
# Note: This is an in-memory implementation. For production distributed
# systems, consider Redis Pub/Sub, RabbitMQ, or Kafka.
# =============================================================================

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4


# =============================================================================
# Event Base Class
# =============================================================================
@dataclass
class Event:
    """
    Base class for all internal events.
    
    Attributes:
        event_id: Unique identifier for this event instance
        timestamp: When the event was created
        event_type: String identifier for the event type
    """
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def event_type(self) -> str:
        """Returns the event type name based on class name."""
        return self.__class__.__name__


# =============================================================================
# Example Event Definitions
# =============================================================================
# These are placeholder events - actual events will be defined per module

@dataclass
class OrderCreatedEvent(Event):
    """Emitted when a new order is created."""
    order_id: str = ""
    user_id: str = ""
    merchant_id: str = ""
    total_amount: float = 0.0


@dataclass
class OrderStatusChangedEvent(Event):
    """Emitted when order status changes."""
    order_id: str = ""
    old_status: str = ""
    new_status: str = ""


@dataclass
class PaymentCompletedEvent(Event):
    """Emitted when payment is successfully processed."""
    order_id: str = ""
    payment_id: str = ""
    amount: float = 0.0


@dataclass
class DriverAssignedEvent(Event):
    """Emitted when a driver is assigned to an order."""
    order_id: str = ""
    driver_id: str = ""


# =============================================================================
# Event Handler Type
# =============================================================================
EventHandler = Callable[[Event], Awaitable[None]]


# =============================================================================
# Event Dispatcher (Singleton)
# =============================================================================
class EventDispatcher:
    """
    In-process event dispatcher implementing the pub/sub pattern.
    
    Usage:
        # Subscribe to events
        @dispatcher.on("OrderCreatedEvent")
        async def handle_order_created(event: OrderCreatedEvent):
            await send_notification(event.user_id, "Order received!")
        
        # Or programmatic subscription
        dispatcher.subscribe("PaymentCompletedEvent", handle_payment)
        
        # Emit events
        await dispatcher.emit(OrderCreatedEvent(order_id="123", ...))
    """
    
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._is_processing = False
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
    
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Subscribe a handler to an event type.
        
        Args:
            event_type: Name of the event type
            handler: Async function to handle the event
        """
        self._handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Unsubscribe a handler from an event type.
        
        Args:
            event_type: Name of the event type
            handler: Handler to remove
        """
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
    
    def on(self, event_type: str) -> Callable[[EventHandler], EventHandler]:
        """
        Decorator to subscribe a handler to an event type.
        
        Usage:
            @dispatcher.on("OrderCreatedEvent")
            async def handle_order(event: OrderCreatedEvent):
                ...
        """
        def decorator(handler: EventHandler) -> EventHandler:
            self.subscribe(event_type, handler)
            return handler
        return decorator
    
    async def emit(self, event: Event) -> None:
        """
        Emit an event to all subscribed handlers.
        Handlers are executed concurrently.
        
        Args:
            event: Event instance to emit
        """
        event_type = event.event_type
        handlers = self._handlers.get(event_type, [])
        
        if not handlers:
            return
        
        # Execute all handlers concurrently
        await asyncio.gather(
            *[self._safe_execute(handler, event) for handler in handlers],
            return_exceptions=True,
        )
    
    async def emit_later(self, event: Event, delay_seconds: float = 0) -> None:
        """
        Emit an event after a delay.
        
        Args:
            event: Event to emit
            delay_seconds: Delay before emitting
        """
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        await self.emit(event)
    
    async def _safe_execute(self, handler: EventHandler, event: Event) -> None:
        """
        Execute a handler with error handling.
        Errors in one handler should not affect others.
        """
        try:
            await handler(event)
        except Exception as e:
            # In production, log this error
            print(f"Error in event handler: {e}")
    
    def get_handlers(self, event_type: str) -> list[EventHandler]:
        """Get all handlers for an event type."""
        return self._handlers.get(event_type, [])
    
    def clear(self) -> None:
        """Clear all handlers. Useful for testing."""
        self._handlers.clear()


# =============================================================================
# Global Dispatcher Instance
# =============================================================================
# Singleton pattern for application-wide event dispatching
dispatcher = EventDispatcher()


# =============================================================================
# Helper Functions
# =============================================================================
async def emit_event(event: Event) -> None:
    """Convenience function to emit events using the global dispatcher."""
    await dispatcher.emit(event)


def subscribe_to(event_type: str) -> Callable[[EventHandler], EventHandler]:
    """Convenience decorator to subscribe to events."""
    return dispatcher.on(event_type)
