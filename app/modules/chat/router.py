from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.modules.chat.schemas import (
    ChatConversationType,
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
)
from app.modules.chat.service import ChatService

router = APIRouter(prefix="/chats", tags=["Chats"])


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)


@router.get(
    "/orders/{order_id}/messages",
    response_model=ChatMessageListResponse,
    summary="List order chat messages",
)
async def list_order_chat_messages(
    order_id: str,
    user: CurrentUser,
    conversation_type: ChatConversationType = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    service: ChatService = Depends(get_chat_service),
) -> ChatMessageListResponse:
    items, total = await service.list_messages(
        order_id,
        conversation_type,
        actor_user_id=user.user_id,
        actor_role=user.role,
        page=page,
        per_page=per_page,
    )
    return ChatMessageListResponse(items=items, total=total)


@router.post(
    "/orders/{order_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send order chat message",
)
async def send_order_chat_message(
    order_id: str,
    data: ChatMessageCreate,
    user: CurrentUser,
    service: ChatService = Depends(get_chat_service),
) -> ChatMessageResponse:
    return await service.send_message(
        order_id,
        data,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
