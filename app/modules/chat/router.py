# =============================================================================
# Chat Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.modules.chat.schemas import ChatMessageListResponse
from app.modules.chat.service import ChatService

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)


@router.get(
    "/orders/{order_id}/messages",
    response_model=ChatMessageListResponse,
    summary="Get order chat history",
)
async def get_order_chat_messages(
    order_id: str,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    service: ChatService = Depends(get_chat_service),
) -> ChatMessageListResponse:
    """Get persisted chat history for an order if the user is authorized."""
    items, total = await service.get_order_messages(
        order_id=order_id,
        actor_user_id=user.user_id,
        actor_role=user.role,
        page=page,
        per_page=per_page,
    )
    return ChatMessageListResponse(items=items, total=total)
