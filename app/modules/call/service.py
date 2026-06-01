from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.modules.call.agora import generate_rtc_token
from app.modules.call.models import OrderCall
from app.modules.call.schemas import (
    CallActionResponse,
    CallEndReason,
    CallResponse,
    CallStatus,
    CallTokenResponse,
)
from app.modules.driver.models import Driver
from app.modules.notification.service import NotificationService
from app.modules.order.models import Order
from app.modules.user.models import User
from app.realtime import connection_manager
from app.realtime.events import RealtimeEventType
from app.shared.enums import OrderStatus, Role

CALLABLE_STATUSES = {OrderStatus.PICKING_UP.value, OrderStatus.DELIVERING.value}
TERMINAL_STATUSES = {
    CallStatus.REJECTED.value,
    CallStatus.ENDED.value,
    CallStatus.MISSED.value,
}


def _role_value(role: Role | str) -> str:
    return role.value if isinstance(role, Role) else str(role)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class CallService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def start_call(
        self,
        order_id: str,
        *,
        actor_user_id: str,
        actor_role: Role,
    ) -> CallTokenResponse:
        order = await self._get_order(order_id)
        driver_user_id = await self._get_driver_user_id(order)
        caller_role = _role_value(actor_role)

        if caller_role == Role.USER.value and order.user_id == actor_user_id:
            callee_user_id = driver_user_id
            callee_role = Role.DRIVER.value
        elif caller_role == Role.DRIVER.value and driver_user_id == actor_user_id:
            callee_user_id = order.user_id
            callee_role = Role.USER.value
        else:
            raise AuthorizationError(message="You are not allowed to call for this order")

        await self._mark_expired_ringing_calls(order.id)
        now = datetime.now(timezone.utc)
        call = OrderCall(
            order_id=order.id,
            caller_user_id=actor_user_id,
            callee_user_id=callee_user_id,
            caller_role=caller_role,
            callee_role=callee_role,
            channel_name="pending",
            status=CallStatus.RINGING.value,
            started_at=now,
            expires_at=now + timedelta(seconds=self.settings.call_ring_timeout_seconds),
        )
        self.db.add(call)
        await self.db.flush()
        # Agora channel names must stay within 64 bytes. A pair of UUIDs is too long.
        call.channel_name = f"call-{call.id}"
        await self.db.flush()
        await self.db.refresh(call)

        response = await self._token_response(call, caller_role)
        await self._emit_and_push(call, RealtimeEventType.CALL_INVITED, target_user_id=callee_user_id)
        return response

    async def accept_call(self, call_id: str, *, actor_user_id: str) -> CallTokenResponse:
        call = await self._get_call(call_id)
        await self._expire_if_needed(call)
        if call.callee_user_id != actor_user_id:
            raise AuthorizationError(message="Only the callee can accept this call")
        if call.status == CallStatus.ACCEPTED.value:
            return await self._token_response(call, call.callee_role)
        if call.status != CallStatus.RINGING.value:
            raise ValidationError(message="Call is no longer ringing")

        call.status = CallStatus.ACCEPTED.value
        call.accepted_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(call)

        response = await self._token_response(call, call.callee_role)
        await self._emit_and_push(call, RealtimeEventType.CALL_ACCEPTED)
        return response

    async def reject_call(self, call_id: str, *, actor_user_id: str) -> CallActionResponse:
        call = await self._get_call(call_id)
        await self._expire_if_needed(call)
        if call.status in TERMINAL_STATUSES:
            return CallActionResponse(call=self._to_response(call))
        if call.callee_user_id != actor_user_id:
            raise AuthorizationError(message="Only the callee can reject this call")
        if call.status != CallStatus.RINGING.value:
            raise ValidationError(message="Only ringing calls can be rejected")

        await self._finish_call(call, CallStatus.REJECTED, actor_user_id, CallEndReason.REJECTED)
        await self._emit_and_push(call, RealtimeEventType.CALL_REJECTED)
        return CallActionResponse(call=self._to_response(call))

    async def end_call(self, call_id: str, *, actor_user_id: str) -> CallActionResponse:
        call = await self._get_call(call_id)
        await self._expire_if_needed(call)
        if call.status in TERMINAL_STATUSES:
            return CallActionResponse(call=self._to_response(call))
        if actor_user_id not in {call.caller_user_id, call.callee_user_id}:
            raise AuthorizationError(message="You are not a participant in this call")

        reason = (
            CallEndReason.CALLER_CANCELLED
            if call.status == CallStatus.RINGING.value and actor_user_id == call.caller_user_id
            else CallEndReason.COMPLETED
        )
        await self._finish_call(call, CallStatus.ENDED, actor_user_id, reason)
        await self._emit_and_push(call, RealtimeEventType.CALL_ENDED)
        return CallActionResponse(call=self._to_response(call))

    async def get_call(self, call_id: str, *, actor_user_id: str) -> CallActionResponse:
        call = await self._get_call(call_id)
        await self._expire_if_needed(call)
        if actor_user_id not in {call.caller_user_id, call.callee_user_id}:
            raise AuthorizationError(message="You are not a participant in this call")
        return CallActionResponse(call=self._to_response(call))

    async def _get_order(self, order_id: str) -> Order:
        order = (
            await self.db.execute(select(Order).where(Order.id == order_id, Order.is_deleted.is_(False)))
        ).scalar_one_or_none()
        if order is None:
            raise NotFoundError(message="Order not found")
        if not order.driver_id:
            raise ValidationError(message="Calls are available after a driver accepts the order")
        if order.status not in CALLABLE_STATUSES:
            raise ValidationError(message="Calls are available while the driver is picking up or delivering")
        return order

    async def _get_driver_user_id(self, order: Order) -> str:
        if not order.driver_id:
            raise ValidationError(message="Order has no assigned driver")
        driver_user_id = (
            await self.db.execute(
                select(Driver.user_id).where(
                    Driver.id == order.driver_id,
                    Driver.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if not driver_user_id:
            raise NotFoundError(message="Assigned driver not found")
        return driver_user_id

    async def _get_call(self, call_id: str) -> OrderCall:
        call = (
            await self.db.execute(
                select(OrderCall).where(OrderCall.id == call_id, OrderCall.is_deleted.is_(False))
            )
        ).scalar_one_or_none()
        if call is None:
            raise NotFoundError(message="Call not found")
        return call

    async def _mark_expired_ringing_calls(self, order_id: str) -> None:
        now = datetime.now(timezone.utc)
        calls = (
            (
                await self.db.execute(
                    select(OrderCall).where(
                        OrderCall.order_id == order_id,
                        OrderCall.status == CallStatus.RINGING.value,
                        OrderCall.expires_at <= now,
                        OrderCall.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        for call in calls:
            await self._finish_call(call, CallStatus.MISSED, None, CallEndReason.MISSED)
            await self._emit_and_push(call, RealtimeEventType.CALL_MISSED)

    async def _expire_if_needed(self, call: OrderCall) -> None:
        now = datetime.now(timezone.utc)
        if call.status == CallStatus.RINGING.value and _as_utc(call.expires_at) <= now:
            await self._finish_call(call, CallStatus.MISSED, None, CallEndReason.MISSED)
            await self._emit_and_push(call, RealtimeEventType.CALL_MISSED)

    async def _finish_call(
        self,
        call: OrderCall,
        status: CallStatus,
        ended_by: str | None,
        reason: CallEndReason,
    ) -> None:
        call.status = status.value
        call.ended_at = datetime.now(timezone.utc)
        call.ended_by = ended_by
        call.end_reason = reason.value
        await self.db.flush()
        await self.db.refresh(call)

    async def _token_response(self, call: OrderCall, role: str) -> CallTokenResponse:
        token, token_expires_at, uid, app_id = generate_rtc_token(call.channel_name, role)
        return CallTokenResponse(
            call=self._to_response(call),
            agora_app_id=app_id,
            agora_token=token,
            agora_uid=uid,
            token_expires_at=token_expires_at,
        )

    def _to_response(self, call: OrderCall) -> CallResponse:
        return CallResponse(
            id=call.id,
            order_id=call.order_id,
            caller_user_id=call.caller_user_id,
            callee_user_id=call.callee_user_id,
            caller_role=Role(call.caller_role),
            callee_role=Role(call.callee_role),
            channel_name=call.channel_name,
            status=CallStatus(call.status),
            started_at=call.started_at,
            accepted_at=call.accepted_at,
            ended_at=call.ended_at,
            expires_at=call.expires_at,
            ended_by=call.ended_by,
            end_reason=call.end_reason,
        )

    async def _emit_and_push(
        self,
        call: OrderCall,
        event: RealtimeEventType,
        *,
        target_user_id: str | None = None,
    ) -> None:
        payload = self._to_response(call).model_dump(mode="json")
        recipients = [target_user_id] if target_user_id else [call.caller_user_id, call.callee_user_id]
        for user_id in dict.fromkeys([recipient for recipient in recipients if recipient]):
            await connection_manager.send_personal(user_id, {"event": event.value, "data": payload})

        push_target = target_user_id
        if push_target:
            title = "Incoming Bitenex call"
            body = "Tap to answer this delivery call."
            deep_link = (
                f"bitenexdriver://call/{call.id}"
                if call.callee_role == Role.DRIVER.value
                else f"bitenexuser://order/call?callId={call.id}"
            )
            caller = await self._get_user(call.caller_user_id)
            if caller and caller.full_name:
                body = f"{caller.full_name} is calling about your order."
            await NotificationService(self.db).send_push(
                push_target,
                title,
                body,
                {
                    "type": event.value,
                    "callId": call.id,
                    "orderId": call.order_id,
                    "deepLink": deep_link,
                },
            )

    async def _get_user(self, user_id: str) -> User | None:
        return (
            await self.db.execute(select(User).where(User.id == user_id, User.is_deleted.is_(False)))
        ).scalar_one_or_none()
