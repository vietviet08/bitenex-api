# =============================================================================
# Chat Module - Service Layer
# =============================================================================

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.modules.chat.models import ChatMessage
from app.modules.chat.schemas import ChatMessageResponse
from app.modules.merchant.models import Merchant
from app.modules.order.models import Order
from app.shared.enums import OrderStatus, Role

CHAT_ACTIVE_STATUSES = {
    OrderStatus.PREPARING.value,
    OrderStatus.READY.value,
    OrderStatus.PICKING_UP.value,
    OrderStatus.DELIVERING.value,
}


class ChatService:
    """
    Chat service for order-scoped user/merchant conversations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _normalize_role(actor_role: Role | str | None) -> Role | None:
        if actor_role is None:
            return None
        if isinstance(actor_role, Role):
            return actor_role
        return Role(actor_role)

    @staticmethod
    def _to_message_response(message: ChatMessage) -> ChatMessageResponse:
        return ChatMessageResponse(
            message_id=message.id,
            order_id=message.order_id,
            sender_id=message.sender_id,
            receiver_id=message.receiver_id,
            content=message.content,
            message_type=message.message_type,
            timestamp=message.created_at.isoformat(),
        )

    async def _get_order(self, order_id: str) -> Order:
        result = await self.db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.is_deleted.is_(False),
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError(message="Order not found")
        return order

    async def _get_merchant_owner_user_id(self, merchant_id: str) -> str:
        result = await self.db.execute(
            select(Merchant.user_id).where(
                Merchant.id == merchant_id,
                Merchant.is_deleted.is_(False),
            )
        )
        owner_user_id = result.scalar_one_or_none()
        if not owner_user_id:
            raise NotFoundError(message="Merchant owner not found for this order")
        return owner_user_id

    async def resolve_receiver_for_realtime(
        self,
        *,
        order_id: str,
        sender_id: str,
        require_active_status: bool = True,
    ) -> str:
        """
        Resolve receiver for a sender in an order chat context with permission checks.
        """
        order = await self._get_order(order_id)
        merchant_owner_user_id = await self._get_merchant_owner_user_id(order.merchant_id)

        if sender_id not in {order.user_id, merchant_owner_user_id}:
            raise AuthorizationError(message="You are not allowed to chat on this order")

        if require_active_status and order.status not in CHAT_ACTIVE_STATUSES:
            raise ValidationError(message="Chat is available only after merchant accepts the order")

        return merchant_owner_user_id if sender_id == order.user_id else order.user_id

    async def create_message(
        self,
        *,
        order_id: str,
        sender_id: str,
        content: str,
        message_type: str = "text",
    ) -> ChatMessageResponse:
        """
        Persist an order chat message and return canonical payload for socket clients.
        """
        message_text = content.strip()
        if not message_text:
            raise ValidationError(message="Message content is required")

        receiver_id = await self.resolve_receiver_for_realtime(
            order_id=order_id,
            sender_id=sender_id,
            require_active_status=True,
        )

        message = ChatMessage(
            order_id=order_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=message_text,
            message_type=message_type,
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return self._to_message_response(message)

    async def get_order_messages(
        self,
        *,
        order_id: str,
        actor_user_id: str,
        actor_role: Role | str | None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[ChatMessageResponse], int]:
        """
        Return order chat history for authorized participants.
        """
        order = await self._get_order(order_id)
        merchant_owner_user_id = await self._get_merchant_owner_user_id(order.merchant_id)
        normalized_role = self._normalize_role(actor_role)

        if normalized_role != Role.ADMIN and actor_user_id not in {
            order.user_id,
            merchant_owner_user_id,
        }:
            raise AuthorizationError(message="You are not allowed to access this order chat")

        filters = [
            ChatMessage.order_id == order_id,
            ChatMessage.is_deleted.is_(False),
        ]
        query = (
            select(ChatMessage)
            .where(*filters)
            .order_by(ChatMessage.created_at.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        count_query = select(func.count(ChatMessage.id)).where(*filters)

        rows = (await self.db.execute(query)).scalars().all()
        total = int((await self.db.execute(count_query)).scalar_one())
        return [self._to_message_response(item) for item in rows], total
