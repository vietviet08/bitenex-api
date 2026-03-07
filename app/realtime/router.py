import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.database import async_session_maker
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.core.security import verify_access_token
from app.modules.chat.service import ChatService
from app.realtime.events import RealtimeEventType
from app.realtime.socket_manager import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["Realtime"])


def _extract_token(websocket: WebSocket) -> str | None:
    token = websocket.query_params.get("token") or websocket.query_params.get("access_token")
    if token:
        return token

    authorization = websocket.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


async def _send_error(websocket: WebSocket, code: str, message: str) -> None:
    await websocket.send_json(
        {
            "event": "error",
            "data": {
                "code": code,
                "message": message,
            },
        }
    )


async def _handle_chat_send(
    websocket: WebSocket,
    *,
    sender_id: str,
    data: dict[str, Any],
) -> None:
    order_id = str(data.get("order_id") or "").strip()
    content = str(data.get("content") or "").strip()

    if not order_id:
        await _send_error(websocket, "MISSING_ORDER_ID", "order_id is required")
        return
    if not content:
        await _send_error(websocket, "MISSING_CONTENT", "content is required")
        return

    try:
        async with async_session_maker() as db:
            chat_service = ChatService(db)
            message = await chat_service.create_message(
                order_id=order_id,
                sender_id=sender_id,
                content=content,
            )
            await db.commit()
            payload = message.model_dump(mode="json")
    except (ValidationError, AuthorizationError, NotFoundError) as exc:
        await _send_error(websocket, "CHAT_NOT_ALLOWED", exc.message)
        return
    except Exception as exc:
        logger.warning(
            "realtime.chat.send_failed sender_id=%s order_id=%s error=%s",
            sender_id,
            order_id,
            str(exc),
        )
        await _send_error(websocket, "CHAT_SEND_FAILED", "Unable to send message")
        return

    envelope = {
        "event": RealtimeEventType.CHAT_MESSAGE.value,
        "data": payload,
    }

    await connection_manager.send_personal(sender_id, envelope)
    await connection_manager.send_personal(payload["receiver_id"], envelope)


async def _handle_chat_typing(
    websocket: WebSocket,
    *,
    sender_id: str,
    data: dict[str, Any],
) -> None:
    order_id = str(data.get("order_id") or "").strip()
    if not order_id:
        await _send_error(websocket, "MISSING_ORDER_ID", "order_id is required")
        return

    try:
        async with async_session_maker() as db:
            chat_service = ChatService(db)
            receiver_id = await chat_service.resolve_receiver_for_realtime(
                order_id=order_id,
                sender_id=sender_id,
                require_active_status=True,
            )
    except (ValidationError, AuthorizationError, NotFoundError) as exc:
        await _send_error(websocket, "CHAT_NOT_ALLOWED", exc.message)
        return

    envelope = {
        "event": RealtimeEventType.CHAT_TYPING.value,
        "data": {
            "order_id": order_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "is_typing": bool(data.get("is_typing", True)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    await connection_manager.send_personal(receiver_id, envelope)


@router.websocket("")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = _extract_token(websocket)
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing access token")
        return

    try:
        payload = verify_access_token(token)
    except Exception:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid or expired access token",
        )
        return

    user_id = str(payload.get("sub") or "").strip()
    role = str(payload.get("role") or "").strip()

    if not user_id or not role:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token payload",
        )
        return

    await connection_manager.connect(websocket, user_id)
    await websocket.send_json(
        {
            "event": RealtimeEventType.CONNECTED.value,
            "data": {
                "user_id": user_id,
                "role": role,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )

    try:
        while True:
            packet = await websocket.receive_json()
            if not isinstance(packet, dict):
                await _send_error(websocket, "INVALID_MESSAGE", "Payload must be an object")
                continue

            event = str(packet.get("event") or "").strip()
            data = packet.get("data") or {}
            if not isinstance(data, dict):
                data = {}

            if event in {"ping", "heartbeat"}:
                await websocket.send_json(
                    {
                        "event": "pong",
                        "data": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    }
                )
                continue

            if event == "join":
                room = str(data.get("room") or "").strip()
                if room:
                    connection_manager.join_room(user_id, room)
                continue

            if event == "leave":
                room = str(data.get("room") or "").strip()
                if room:
                    connection_manager.leave_room(user_id, room)
                continue

            if event == "chat.send":
                await _handle_chat_send(
                    websocket,
                    sender_id=user_id,
                    data=data,
                )
                continue

            if event == "chat.typing":
                await _handle_chat_typing(
                    websocket,
                    sender_id=user_id,
                    data=data,
                )
                continue

            await _send_error(websocket, "UNKNOWN_EVENT", f"Unsupported event: {event}")
    except WebSocketDisconnect:
        logger.info("realtime.websocket.disconnected user_id=%s", user_id)
    except Exception as exc:
        logger.warning(
            "realtime.websocket.error user_id=%s error=%s",
            user_id,
            str(exc),
        )
    finally:
        connection_manager.disconnect(websocket, user_id)
