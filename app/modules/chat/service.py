from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.modules.chat.models import ChatMessage
from app.modules.chat.schemas import (
    ChatConversationType,
    ChatMessageCreate,
    ChatMessageResponse,
)
from app.modules.driver.models import Driver
from app.modules.merchant.models import Merchant
from app.modules.order.models import Order
from app.modules.user.models import User
from app.realtime import connection_manager
from app.realtime.events import RealtimeEventType
from app.shared.enums import OrderStatus, Role

SENDABLE_STATUSES = {OrderStatus.PICKING_UP.value, OrderStatus.DELIVERING.value}


def _conversation_value(conversation_type: ChatConversationType | str) -> str:
    return (
        conversation_type.value
        if isinstance(conversation_type, ChatConversationType)
        else str(conversation_type)
    )


def _role_value(role: Role | str) -> str:
    return role.value if isinstance(role, Role) else str(role)


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_messages(
        self,
        order_id: str,
        conversation_type: ChatConversationType,
        *,
        actor_user_id: str,
        actor_role: Role,
        page: int,
        per_page: int,
    ) -> tuple[list[ChatMessageResponse], int]:
        order = await self._get_order(order_id)
        await self._enforce_participant(order, conversation_type, actor_user_id, actor_role)

        filters = [
            ChatMessage.order_id == order_id,
            ChatMessage.conversation_type == _conversation_value(conversation_type),
            ChatMessage.is_deleted.is_(False),
        ]
        total = (await self.db.execute(select(func.count(ChatMessage.id)).where(*filters))).scalar_one()
        messages = (
            (
                await self.db.execute(
                    select(ChatMessage)
                    .where(*filters)
                    .order_by(ChatMessage.created_at.asc())
                    .offset((page - 1) * per_page)
                    .limit(per_page)
                )
            )
            .scalars()
            .all()
        )
        return await self._to_responses(messages), total

    async def send_message(
        self,
        order_id: str,
        data: ChatMessageCreate,
        *,
        actor_user_id: str,
        actor_role: Role,
    ) -> ChatMessageResponse:
        order = await self._get_order(order_id)
        await self._enforce_participant(order, data.conversation_type, actor_user_id, actor_role)
        if not order.driver_id:
            raise ValidationError(message="Chat is available after a driver accepts the order")
        if order.status not in SENDABLE_STATUSES:
            raise ValidationError(message="Chat is available while the driver is picking up or delivering")

        message = ChatMessage(
            order_id=order.id,
            conversation_type=_conversation_value(data.conversation_type),
            sender_user_id=actor_user_id,
            sender_role=_role_value(actor_role),
            content=data.content,
            message_type="text",
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)

        response = (await self._to_responses([message]))[0]
        await self._emit_message(order, data.conversation_type, response)
        return response

    async def _get_order(self, order_id: str) -> Order:
        order = (
            await self.db.execute(
                select(Order).where(Order.id == order_id, Order.is_deleted.is_(False))
            )
        ).scalar_one_or_none()
        if order is None:
            raise NotFoundError(message="Order not found")
        return order

    async def _enforce_participant(
        self,
        order: Order,
        conversation_type: ChatConversationType,
        actor_user_id: str,
        actor_role: Role,
    ) -> None:
        conversation_value = _conversation_value(conversation_type)

        if conversation_value == ChatConversationType.USER_DRIVER.value:
            if actor_role == Role.USER and order.user_id == actor_user_id:
                return
            if actor_role == Role.DRIVER and await self._is_assigned_driver(order, actor_user_id):
                return
            raise AuthorizationError(message="You are not a participant in this chat")

        if conversation_value == ChatConversationType.MERCHANT_DRIVER.value:
            if actor_role == Role.MERCHANT and await self._is_order_merchant(order, actor_user_id):
                return
            if actor_role == Role.DRIVER and await self._is_assigned_driver(order, actor_user_id):
                return
            raise AuthorizationError(message="You are not a participant in this chat")

    async def _is_assigned_driver(self, order: Order, user_id: str) -> bool:
        if not order.driver_id:
            return False
        driver_id = (
            await self.db.execute(
                select(Driver.id).where(
                    Driver.user_id == user_id,
                    Driver.id == order.driver_id,
                    Driver.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        return driver_id is not None

    async def _is_order_merchant(self, order: Order, user_id: str) -> bool:
        merchant_id = (
            await self.db.execute(
                select(Merchant.id).where(
                    Merchant.user_id == user_id,
                    Merchant.id == order.merchant_id,
                    Merchant.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        return merchant_id is not None

    async def _participant_user_ids(
        self,
        order: Order,
        conversation_type: ChatConversationType,
    ) -> list[str]:
        users: list[str] = []
        if _conversation_value(conversation_type) == ChatConversationType.USER_DRIVER.value:
            users.append(order.user_id)
        else:
            merchant_user_id = (
                await self.db.execute(
                    select(Merchant.user_id).where(
                        Merchant.id == order.merchant_id,
                        Merchant.is_deleted.is_(False),
                    )
                )
            ).scalar_one_or_none()
            if merchant_user_id:
                users.append(merchant_user_id)

        if order.driver_id:
            driver_user_id = (
                await self.db.execute(
                    select(Driver.user_id).where(
                        Driver.id == order.driver_id,
                        Driver.is_deleted.is_(False),
                    )
                )
            ).scalar_one_or_none()
            if driver_user_id:
                users.append(driver_user_id)

        return list(dict.fromkeys(users))

    async def _to_responses(self, messages: list[ChatMessage]) -> list[ChatMessageResponse]:
        sender_ids = list({message.sender_user_id for message in messages})
        users_by_id: dict[str, User] = {}
        if sender_ids:
            users = (
                (
                    await self.db.execute(
                        select(User).where(
                            User.id.in_(sender_ids),
                            User.is_deleted.is_(False),
                        )
                    )
                )
                .scalars()
                .all()
            )
            users_by_id = {user.id: user for user in users}

        return [
            ChatMessageResponse(
                id=message.id,
                order_id=message.order_id,
                conversation_type=ChatConversationType(message.conversation_type),
                sender_user_id=message.sender_user_id,
                sender_role=Role(message.sender_role),
                sender_name=users_by_id.get(message.sender_user_id).full_name
                if users_by_id.get(message.sender_user_id)
                else None,
                sender_avatar_url=users_by_id.get(message.sender_user_id).avatar_url
                if users_by_id.get(message.sender_user_id)
                else None,
                content=message.content,
                message_type=message.message_type,
                created_at=message.created_at,
            )
            for message in messages
        ]

    async def _emit_message(
        self,
        order: Order,
        conversation_type: ChatConversationType,
        message: ChatMessageResponse,
    ) -> None:
        payload = message.model_dump(mode="json")
        for user_id in await self._participant_user_ids(order, conversation_type):
            await connection_manager.send_personal(
                user_id,
                {"event": RealtimeEventType.CHAT_MESSAGE.value, "data": payload},
            )
