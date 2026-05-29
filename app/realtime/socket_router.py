# =============================================================================
# Custom Socket.IO v4 / Engine.IO WebSocket Router
# =============================================================================
# The bitenex-driver and bitenex-merchant apps connect using the official
# socket.io-client library (v4) with `transports: ['websocket']`.
#
# Socket.IO v4 layered protocol (over raw WebSocket):
#   Engine.IO frame:  <packet_type><data>
#   Packet types:
#     0  = OPEN   (EIO handshake)
#     1  = CLOSE
#     2  = PING
#     3  = PONG
#     4  = MESSAGE  → contains a Socket.IO packet
#
#   Socket.IO packet (inside EIO message):
#     40 = CONNECT      (client initiates namespace connection)
#     42 = EVENT        (client sends an event)
#     43 = ACK
#
#   Client CONNECT frame: 40{"token":"<jwt>"}  OR 40{"auth":{"token":"<jwt>"}}
#   Client EVENT frame:   42["event_name", {...}]
# =============================================================================

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import verify_access_token
from app.realtime import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EIO_SID = "bitenex-sio"  # fixed fake SID (single-process, in-memory)

_HANDSHAKE_PAYLOAD = json.dumps(
    {
        "sid": _EIO_SID,
        "upgrades": [],
        "pingInterval": 25000,
        "pingTimeout": 20000,
    }
)


def _parse_sio_connect_token(raw: str) -> str | None:
    """
    Extract JWT from either:
      40{"token":"<jwt>"}
      40{"auth":{"token":"<jwt>"}}
    Returns the raw token string or None.
    """
    try:
        body = json.loads(raw[2:])  # strip leading "40"
        if isinstance(body, dict):
            token = body.get("token") or body.get("auth", {}).get("token")
            return token
    except Exception:
        pass
    return None


def _parse_sio_event(raw: str) -> tuple[str, dict] | None:
    """
    Parse  42["event_name", {...}]  into (event_name, data_dict).
    Returns None on parse failure.
    """
    try:
        payload = json.loads(raw[2:])  # strip leading "42"
        if isinstance(payload, list) and len(payload) >= 1:
            event_name = str(payload[0])
            data = payload[1] if len(payload) > 1 else {}
            return event_name, data
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/socket.io/")
async def socketio_endpoint(websocket: WebSocket) -> None:
    """
    Raw Engine.IO / Socket.IO v4 WebSocket endpoint.

    Supports:
      - EIO handshake (OPEN frame)
      - Socket.IO CONNECT with JWT auth
      - Socket.IO EVENT frames
      - EIO PING / PONG heartbeat
    """
    await websocket.accept()

    # 1. Send EIO OPEN handshake immediately after accept
    await websocket.send_text(f"0{_HANDSHAKE_PAYLOAD}")

    user_id: str | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            logger.debug(f"[SIO] recv: {raw[:120]}")

            # --- Engine.IO PING heartbeat ---
            if raw == "2":
                await websocket.send_text("3")
                continue

            # --- Socket.IO CONNECT ---
            if raw.startswith("40"):
                token = _parse_sio_connect_token(raw)
                if not token:
                    logger.warning("[SIO] CONNECT without token – closing")
                    await websocket.send_text("1")  # EIO CLOSE
                    await websocket.close(code=4401)
                    return

                try:
                    payload = verify_access_token(token)
                    user_id = payload["sub"]
                except Exception as exc:
                    logger.warning(f"[SIO] Invalid token: {exc}")
                    await websocket.send_text("1")
                    await websocket.close(code=4401)
                    return

                # Accept the namespace connection; do NOT call .accept() again
                await connection_manager.connect(websocket, user_id)

                # Send Socket.IO CONNECT reply (server confirms namespace)
                await websocket.send_text(f'40{{"sid":"{_EIO_SID}"}}')
                logger.info(f"[SIO] User {user_id} connected")
                continue

            # --- Socket.IO EVENT ---
            if raw.startswith("42") and user_id:
                parsed = _parse_sio_event(raw)
                if parsed is None:
                    continue
                event_name, data = parsed
                await _handle_event(websocket, user_id, event_name, data)
                continue

            # Anything else – ignore silently
            logger.debug(f"[SIO] Unhandled frame: {raw[:40]}")

    except WebSocketDisconnect:
        if user_id:
            connection_manager.disconnect(websocket, user_id)
            logger.info(f"[SIO] User {user_id} disconnected")
    except Exception as exc:
        logger.exception(f"[SIO] Unexpected error: {exc}")
        if user_id:
            connection_manager.disconnect(websocket, user_id)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


async def _handle_event(
    websocket: WebSocket,
    user_id: str,
    event: str,
    data: dict,
) -> None:
    """Route an incoming Socket.IO event to the appropriate handler."""

    if event == "join":
        room = str(data.get("room", ""))
        if room:
            connection_manager.join_room(user_id, room)
            logger.debug(f"[SIO] {user_id} joined room {room}")

    elif event == "leave":
        room = str(data.get("room", ""))
        if room:
            connection_manager.leave_room(user_id, room)
            logger.debug(f"[SIO] {user_id} left room {room}")

    else:
        logger.debug(f"[SIO] No handler for event '{event}' from {user_id}")
