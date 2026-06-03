import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket connection manager.
    Handles connection lifecycle and message broadcasting.
    """

    def __init__(self) -> None:
        # Active connections: {user_id: [websocket, ...]}
        self._connections: dict[str, list[WebSocket]] = {}
        # Room subscriptions: {room_name: set(user_id)}
        self._rooms: dict[str, set[str]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
    ) -> None:
        """Accept and register a WebSocket connection."""
        if user_id not in self._connections:
            self._connections[user_id] = []

        self._connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket")

    def disconnect(
        self,
        websocket: WebSocket,
        user_id: str,
    ) -> None:
        """Unregister a WebSocket connection."""
        if user_id in self._connections:
            if websocket in self._connections[user_id]:
                self._connections[user_id].remove(websocket)

            # Cleanup empty lists
            if not self._connections[user_id]:
                del self._connections[user_id]

                # Remove from all rooms
                for room in self._rooms.values():
                    room.discard(user_id)

        logger.info(f"User {user_id} disconnected from WebSocket")

    def _remove_connection(
        self,
        websocket: WebSocket,
        user_id: str,
    ) -> None:
        """Remove a stale socket without relying on a disconnect frame."""
        if user_id not in self._connections:
            return

        if websocket in self._connections[user_id]:
            self._connections[user_id].remove(websocket)

        if self._connections[user_id]:
            return

        del self._connections[user_id]
        for room in list(self._rooms):
            self._rooms[room].discard(user_id)
            if not self._rooms[room]:
                del self._rooms[room]

    async def send_personal(
        self,
        user_id: str,
        message: dict[str, Any],
    ) -> None:
        """Send a message to a specific user.

        If *message* contains an ``'event'`` key the payload is encoded as a
        Socket.IO v4 event frame:  ``42["event_name", {data}]``
        Otherwise it is sent as plain JSON (backward-compat).
        """
        import json as _json

        if user_id not in self._connections:
            return

        if "event" in message:
            frame = f'42{_json.dumps([message["event"], message.get("data", {})])}'
            for websocket in list(self._connections.get(user_id, [])):
                try:
                    await websocket.send_text(frame)
                except Exception as e:
                    logger.error(f"Failed to send SIO event to {user_id}: {e}")
                    self._remove_connection(websocket, user_id)
        else:
            for websocket in list(self._connections.get(user_id, [])):
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send message to {user_id}: {e}")
                    self._remove_connection(websocket, user_id)

    async def broadcast(
        self,
        message: dict[str, Any],
    ) -> None:
        """Broadcast a message to all connected users."""
        for user_id in list(self._connections):
            await self.send_personal(user_id, message)

    def join_room(self, user_id: str, room: str) -> None:
        """Add user to a room."""
        if room not in self._rooms:
            self._rooms[room] = set()
        self._rooms[room].add(user_id)
        logger.debug(f"User {user_id} joined room {room}")

    def leave_room(self, user_id: str, room: str) -> None:
        """Remove user from a room."""
        if room in self._rooms:
            self._rooms[room].discard(user_id)
            if not self._rooms[room]:
                del self._rooms[room]
        logger.debug(f"User {user_id} left room {room}")

    async def broadcast_to_room(
        self,
        room: str,
        message: dict[str, Any],
        exclude_user: str | None = None,
    ) -> None:
        """Broadcast a message to all users in a room."""
        if room not in self._rooms:
            return

        for user_id in list(self._rooms[room]):
            if user_id != exclude_user:
                await self.send_personal(user_id, message)

    def is_connected(self, user_id: str) -> bool:
        """Check if a user is connected."""
        return user_id in self._connections

    def get_connection_count(self) -> int:
        """Get total number of connected users."""
        return len(self._connections)

    def get_room_members(self, room: str) -> set[str]:
        """Get all members of a room."""
        return self._rooms.get(room, set()).copy()


# Global connection manager instance
connection_manager = ConnectionManager()
