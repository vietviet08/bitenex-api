# =============================================================================
# Payment Module - Service Layer
# =============================================================================

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AuthorizationError,
    IdempotencyConflictError,
    InvalidPaymentSignatureError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from app.modules.merchant.models import Merchant
from app.modules.notification.schemas import NotificationCreate
from app.modules.notification.service import NotificationService
from app.modules.order.models import Order, OrderStatusHistory
from app.modules.payment.models import IdempotencyKey, Payment
from app.modules.payment.models import PaymentMethod as PaymentMethodModel
from app.modules.payment.models import Refund, WebhookEvent
from app.modules.payment.repository import PaymentRepository
from app.modules.payment.schemas import (
    AddPaymentMethodRequest,
    AdminPaymentListItem,
    PaymentCreate,
    PaymentResponse,
    RefundCreate,
    RefundResponse,
    SavedPaymentMethodResponse,
)
from app.modules.payment.vnpay import build_vnpay_payment_url, verify_vnpay_signature
from app.shared.enums import (
    NotificationChannel,
    NotificationType,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    Role,
)

logger = logging.getLogger(__name__)
settings = get_settings()
VNPAY_TIMEZONE = timezone(timedelta(hours=7))


class PaymentService:
    """
    Payment processing service.
    Handles payments, refunds, webhooks, and saved payment methods.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PaymentRepository(db)

    @staticmethod
    def _generate_transaction_id() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"PAY-{ts}-{uuid4().hex[:8].upper()}"

    @staticmethod
    def _fingerprint(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_scope(actor_id: str, endpoint: str) -> str:
        return f"{actor_id}:{endpoint}"

    @staticmethod
    def _parse_response_payload(record: IdempotencyKey) -> dict:
        try:
            return json.loads(record.response_payload)
        except json.JSONDecodeError:
            return {}

    async def _get_idempotent_replay(
        self,
        *,
        scope: str,
        key: str,
        request_fingerprint: str,
    ) -> dict | None:
        record = await self.repo.get_idempotency_record(scope, key)
        if not record:
            return None
        if record.request_fingerprint != request_fingerprint:
            raise IdempotencyConflictError(
                message="Idempotency key reused with different payload",
                details={
                    "scope": scope,
                    "key": key,
                },
            )
        return self._parse_response_payload(record)

    async def _persist_idempotent_response(
        self,
        *,
        scope: str,
        key: str,
        request_fingerprint: str,
        status_code: int,
        payload: dict,
    ) -> dict:
        record = IdempotencyKey(
            key=key,
            scope=scope,
            request_fingerprint=request_fingerprint,
            response_status=status_code,
            response_payload=json.dumps(payload, sort_keys=True),
        )
        self.db.add(record)
        try:
            await self.db.flush()
            return payload
        except IntegrityError:
            # Another concurrent request already committed this key.
            await self.db.rollback()
            replay = await self._get_idempotent_replay(
                scope=scope,
                key=key,
                request_fingerprint=request_fingerprint,
            )
            if replay is None:
                raise IdempotencyConflictError(message="Unable to replay idempotent response")
            return replay

    @staticmethod
    def _to_payment_response(
        payment: Payment,
        *,
        payment_url: str | None = None,
    ) -> PaymentResponse:
        response = PaymentResponse.model_validate(payment)
        response.payment_url = payment_url
        return response

    @staticmethod
    def _to_admin_payment_item(
        payment: Payment,
        *,
        order_status: str | None,
        refunded_amount: float,
    ) -> AdminPaymentListItem:
        return AdminPaymentListItem(
            **PaymentResponse.model_validate(payment).model_dump(mode="python"),
            order_status=order_status,
            refunded_amount=round(refunded_amount, 2),
            refundable_amount=round(max(float(payment.amount) - refunded_amount, 0.0), 2),
        )

    @staticmethod
    def _to_refund_response(refund: Refund) -> RefundResponse:
        return RefundResponse.model_validate(refund)

    async def _get_order_for_payment(
        self,
        *,
        user_id: str,
        order_id: str,
    ) -> Order:
        result = await self.db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.is_deleted == False,
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError(message="Order not found")
        if order.user_id != user_id:
            raise AuthorizationError(message="You can only pay your own orders")
        return order

    @staticmethod
    def _normalize_role(actor_role: Role | str | None) -> Role | None:
        if actor_role is None:
            return None
        if isinstance(actor_role, Role):
            return actor_role
        return Role(actor_role)

    async def _enforce_payment_access(
        self,
        payment: Payment,
        *,
        actor_user_id: str | None,
        actor_role: Role | str | None,
    ) -> None:
        role = self._normalize_role(actor_role)
        if role == Role.ADMIN:
            return
        if actor_user_id and payment.user_id != actor_user_id:
            raise AuthorizationError(message="You can only access your own payments")

    def _build_vnpay_url(
        self,
        *,
        payment: Payment,
        ip_addr: str,
    ) -> str:
        amount_minor = int(round(float(payment.amount) * 100))
        # VNPAY expects GMT+7 timestamps for create/expire fields.
        created = datetime.now(VNPAY_TIMEZONE)
        expires = created + timedelta(minutes=15)

        params = {
            "vnp_Version": "2.1.0",
            "vnp_Command": "pay",
            "vnp_TmnCode": settings.vnp_tmn_code,
            "vnp_Amount": str(amount_minor),
            "vnp_CurrCode": payment.currency,
            "vnp_TxnRef": payment.transaction_id,
            "vnp_OrderInfo": f"Payment for order {payment.order_id}",
            "vnp_OrderType": "billpayment",
            "vnp_Locale": "vn",
            "vnp_ReturnUrl": settings.vnp_return_url,
            "vnp_IpAddr": ip_addr,
            "vnp_CreateDate": created.strftime("%Y%m%d%H%M%S"),
            "vnp_ExpireDate": expires.strftime("%Y%m%d%H%M%S"),
        }

        return build_vnpay_payment_url(
            base_url=settings.vnp_url,
            hash_secret=settings.vnp_hash_secret,
            params=params,
        )

    async def create_payment(
        self,
        user_id: str,
        data: PaymentCreate,
        *,
        idempotency_key: str,
        endpoint: str = "/payments",
        client_ip: str = "127.0.0.1",
    ) -> PaymentResponse:
        """
        Create a payment for an order.
        """
        trace_id = uuid4().hex
        logger.info(
            "payment.create.start trace_id=%s user_id=%s order_id=%s",
            trace_id,
            user_id,
            data.order_id,
        )

        payment_method = (
            data.method if isinstance(data.method, PaymentMethod) else PaymentMethod(data.method)
        )

        payload_for_fingerprint = {
            "order_id": data.order_id,
            "amount": data.amount,
            "currency": data.currency.upper(),
            "method": payment_method.value,
        }
        request_fingerprint = self._fingerprint(payload_for_fingerprint)
        scope = self._build_scope(user_id, endpoint)

        replay = await self._get_idempotent_replay(
            scope=scope,
            key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        if replay is not None:
            logger.info("payment.create.replay trace_id=%s key=%s", trace_id, idempotency_key)
            return PaymentResponse.model_validate(replay)

        if data.amount <= 0:
            raise ValidationError(message="Payment amount must be greater than zero")
        if payment_method == PaymentMethod.CASH_ON_DELIVERY:
            raise ValidationError(message="Online payment endpoint does not accept cash method")

        order = await self._get_order_for_payment(user_id=user_id, order_id=data.order_id)

        if OrderStatus(order.status) in {
            OrderStatus.CANCELLED,
            OrderStatus.DELIVERED,
            OrderStatus.REFUNDED,
        }:
            raise ValidationError(message=f"Order is not payable in status {order.status}")

        if round(float(order.total), 2) != round(float(data.amount), 2):
            raise ValidationError(
                message="Payment amount must match order total",
                details={
                    "order_total": float(order.total),
                    "requested_amount": float(data.amount),
                },
            )

        completed_payment_result = await self.db.execute(
            select(Payment).where(
                Payment.order_id == data.order_id,
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.is_deleted == False,
            )
        )
        completed_payment = completed_payment_result.scalar_one_or_none()
        if completed_payment:
            raise ValidationError(message="Order already has a completed payment")

        payment = Payment(
            transaction_id=self._generate_transaction_id(),
            order_id=data.order_id,
            user_id=user_id,
            amount=float(data.amount),
            currency=data.currency.upper(),
            method=payment_method.value,
            status=PaymentStatus.PROCESSING.value,
            gateway="vnpay",
        )
        self.db.add(payment)
        await self.db.flush()

        payment_url = self._build_vnpay_url(payment=payment, ip_addr=client_ip)
        response = self._to_payment_response(payment, payment_url=payment_url)
        payload = response.model_dump(mode="json")
        replay_payload = await self._persist_idempotent_response(
            scope=scope,
            key=idempotency_key,
            request_fingerprint=request_fingerprint,
            status_code=201,
            payload=payload,
        )

        logger.info(
            "payment.create.success trace_id=%s payment_id=%s transaction_id=%s",
            trace_id,
            payment.id,
            payment.transaction_id,
        )
        return PaymentResponse.model_validate(replay_payload)

    async def get_payment(
        self,
        payment_id: str,
        *,
        actor_user_id: str | None = None,
        actor_role: Role | str | None = None,
    ) -> PaymentResponse:
        """Get payment by ID."""
        result = await self.db.execute(
            select(Payment).where(
                Payment.id == payment_id,
                Payment.is_deleted == False,
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise NotFoundError(message="Payment not found")
        await self._enforce_payment_access(
            payment,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return self._to_payment_response(payment)

    async def get_payment_by_transaction(
        self,
        transaction_id: str,
        *,
        actor_user_id: str | None = None,
        actor_role: Role | str | None = None,
    ) -> PaymentResponse:
        """Get payment by transaction ID."""
        result = await self.db.execute(
            select(Payment).where(
                Payment.transaction_id == transaction_id,
                Payment.is_deleted == False,
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise NotFoundError(message="Payment not found")
        await self._enforce_payment_access(
            payment,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return self._to_payment_response(payment)

    async def get_order_payments(
        self,
        order_id: str,
        *,
        actor_user_id: str | None = None,
        actor_role: Role | str | None = None,
    ) -> list[PaymentResponse]:
        """Get all payments for an order."""
        query = (
            select(Payment)
            .where(
                Payment.order_id == order_id,
                Payment.is_deleted == False,
            )
            .order_by(Payment.created_at.desc())
        )
        payments = (await self.db.execute(query)).scalars().all()
        responses: list[PaymentResponse] = []
        for payment in payments:
            await self._enforce_payment_access(
                payment,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            )
            responses.append(self._to_payment_response(payment))
        return responses

    async def get_admin_payments(
        self,
        *,
        search: str | None = None,
        status: PaymentStatus | None = None,
        method: PaymentMethod | None = None,
        order_id: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[AdminPaymentListItem], int]:
        """List payments for admin operations."""
        filters = [Payment.is_deleted.is_(False)]
        if status:
            filters.append(Payment.status == status.value)
        if method:
            filters.append(Payment.method == method.value)
        if order_id:
            filters.append(Payment.order_id == order_id.strip())
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Payment.id.ilike(term),
                    Payment.transaction_id.ilike(term),
                    Payment.order_id.ilike(term),
                    Payment.user_id.ilike(term),
                )
            )

        query = (
            select(Payment)
            .where(*filters)
            .order_by(Payment.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        count_query = select(func.count(Payment.id)).where(*filters)

        payments = (await self.db.execute(query)).scalars().all()
        total = (await self.db.execute(count_query)).scalar_one()
        if not payments:
            return [], total

        payment_ids = [payment.id for payment in payments]
        refund_rows = (
            await self.db.execute(
                select(Refund.payment_id, func.coalesce(func.sum(Refund.amount), 0.0))
                .where(
                    Refund.payment_id.in_(payment_ids),
                    Refund.is_deleted.is_(False),
                    Refund.status.in_(["PENDING", "PROCESSING", "COMPLETED"]),
                )
                .group_by(Refund.payment_id)
            )
        ).all()
        refunded_amount_map = {row[0]: float(row[1]) for row in refund_rows}

        order_ids = list({payment.order_id for payment in payments})
        order_rows = (
            await self.db.execute(
                select(Order.id, Order.status).where(
                    Order.id.in_(order_ids),
                    Order.is_deleted.is_(False),
                )
            )
        ).all()
        order_status_map = {row[0]: row[1] for row in order_rows}

        items = [
            self._to_admin_payment_item(
                payment,
                order_status=order_status_map.get(payment.order_id),
                refunded_amount=refunded_amount_map.get(payment.id, 0.0),
            )
            for payment in payments
        ]
        return items, total

    async def process_refund(
        self,
        data: RefundCreate,
        refunded_by: str,
        *,
        idempotency_key: str,
        endpoint: str = "/payments/refund",
    ) -> RefundResponse:
        """
        Process a refund (sandbox scaffolding).
        """
        trace_id = uuid4().hex
        logger.info(
            "payment.refund.start trace_id=%s payment_id=%s",
            trace_id,
            data.payment_id,
        )

        payload_for_fingerprint = {
            "payment_id": data.payment_id,
            "amount": data.amount,
            "reason": data.reason,
        }
        request_fingerprint = self._fingerprint(payload_for_fingerprint)
        scope = self._build_scope(refunded_by, endpoint)

        replay = await self._get_idempotent_replay(
            scope=scope,
            key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        if replay is not None:
            logger.info("payment.refund.replay trace_id=%s key=%s", trace_id, idempotency_key)
            return RefundResponse.model_validate(replay)

        payment_result = await self.db.execute(
            select(Payment)
            .where(
                Payment.id == data.payment_id,
                Payment.is_deleted == False,
            )
            .with_for_update()
        )
        payment = payment_result.scalar_one_or_none()
        if not payment:
            raise NotFoundError(message="Payment not found")

        if PaymentStatus(payment.status) not in {
            PaymentStatus.COMPLETED,
            PaymentStatus.REFUNDED,
        }:
            raise ValidationError(message="Only completed payments can be refunded")

        total_refunded = (
            await self.db.execute(
                select(func.coalesce(func.sum(Refund.amount), 0.0)).where(
                    Refund.payment_id == payment.id,
                    Refund.is_deleted == False,
                    Refund.status.in_(["PENDING", "PROCESSING", "COMPLETED"]),
                )
            )
        ).scalar_one()

        remaining_amount = float(payment.amount) - float(total_refunded)
        refund_amount = float(data.amount) if data.amount is not None else remaining_amount

        if refund_amount <= 0:
            raise ValidationError(message="Refund amount must be greater than zero")
        if refund_amount > remaining_amount:
            raise ValidationError(
                message="Refund amount exceeds refundable amount",
                details={
                    "remaining_amount": round(remaining_amount, 2),
                    "requested_amount": round(refund_amount, 2),
                },
            )

        refund = Refund(
            payment_id=payment.id,
            order_id=payment.order_id,
            amount=refund_amount,
            reason=data.reason,
            status="COMPLETED",
            refunded_by=refunded_by,
        )
        self.db.add(refund)

        if round(total_refunded + refund_amount, 2) >= round(float(payment.amount), 2):
            payment.status = PaymentStatus.REFUNDED.value

            order_result = await self.db.execute(
                select(Order).where(
                    Order.id == payment.order_id,
                    Order.is_deleted == False,
                )
            )
            order = order_result.scalar_one_or_none()
            if order and OrderStatus(order.status) == OrderStatus.CANCELLED:
                order.status = OrderStatus.REFUNDED.value
                self.db.add(
                    OrderStatusHistory(
                        order_id=order.id,
                        from_status=OrderStatus.CANCELLED.value,
                        to_status=OrderStatus.REFUNDED.value,
                        changed_by=refunded_by,
                        reason="Refund completed",
                    )
                )

        await self.db.flush()
        response = self._to_refund_response(refund)
        payload = response.model_dump(mode="json")
        replay_payload = await self._persist_idempotent_response(
            scope=scope,
            key=idempotency_key,
            request_fingerprint=request_fingerprint,
            status_code=201,
            payload=payload,
        )
        logger.info("payment.refund.success trace_id=%s refund_id=%s", trace_id, refund.id)
        return RefundResponse.model_validate(replay_payload)

    @staticmethod
    def _extract_vnp_event_id(payload: dict) -> str:
        txn_ref = str(payload.get("vnp_TxnRef", ""))
        transaction_no = str(payload.get("vnp_TransactionNo", ""))
        response_code = str(payload.get("vnp_ResponseCode", ""))
        pay_date = str(payload.get("vnp_PayDate", ""))
        return ":".join([txn_ref, transaction_no, response_code, pay_date]).strip(":")

    @staticmethod
    def _is_vnp_success(payload: dict) -> bool:
        return str(payload.get("vnp_ResponseCode", "")) == "00" and str(
            payload.get("vnp_TransactionStatus", "")
        ) in {"00", ""}

    async def _resolve_merchant_owner_user_id(self, merchant_id: str) -> str | None:
        result = await self.db.execute(
            select(Merchant.user_id).where(
                Merchant.id == merchant_id,
                Merchant.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _notify_merchant_paid_order(
        self,
        *,
        order: Order,
        payment: Payment,
    ) -> None:
        merchant_user_id = await self._resolve_merchant_owner_user_id(order.merchant_id)
        if not merchant_user_id:
            logger.warning(
                "payment.webhook.notify_merchant_skipped order_id=%s reason=merchant_owner_missing",
                order.id,
            )
            return

        service = NotificationService(self.db)
        await service.send_notification(
            NotificationCreate(
                user_id=merchant_user_id,
                type=NotificationType.PAYMENT,
                channel=NotificationChannel.IN_APP,
                title="New paid order",
                body=f"Order {order.order_number} has been paid. Please accept or reject it.",
                data={
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "status": order.status,
                    "total": float(order.total),
                    "payment_id": payment.id,
                    "transaction_id": payment.transaction_id,
                },
            )
        )

    async def _notify_user_payment_confirmed(
        self,
        *,
        order: Order,
        payment: Payment,
    ) -> None:
        service = NotificationService(self.db)
        await service.send_notification(
            NotificationCreate(
                user_id=order.user_id,
                type=NotificationType.PAYMENT,
                channel=NotificationChannel.IN_APP,
                title="Payment successful",
                body=f"Payment for order {order.order_number} was successful.",
                data={
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "status": order.status,
                    "total": float(order.total),
                    "payment_id": payment.id,
                    "transaction_id": payment.transaction_id,
                },
            )
        )

    async def handle_webhook(
        self,
        gateway: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle payment gateway webhook.

        Returns a status payload to help webhook endpoint respond deterministically.
        """
        normalized_gateway = gateway.lower().strip()
        trace_id = uuid4().hex
        logger.info(
            "payment.webhook.received trace_id=%s gateway=%s",
            trace_id,
            normalized_gateway,
        )

        if normalized_gateway != "vnpay":
            raise ValidationError(message=f"Unsupported payment gateway: {gateway}")

        event_id = self._extract_vnp_event_id(payload)
        if not event_id:
            raise ValidationError(message="Missing VNPAY event identity")

        webhook_event = WebhookEvent(
            gateway=normalized_gateway,
            event_id=event_id,
            event_type=str(
                payload.get("vnp_ResponseCode") or payload.get("vnp_TransactionStatus") or "UNKNOWN"
            ),
            transaction_id=str(payload.get("vnp_TxnRef") or ""),
            payload=json.dumps(payload, sort_keys=True),
            status="RECEIVED",
        )
        try:
            async with self.db.begin_nested():
                self.db.add(webhook_event)
                await self.db.flush()
        except IntegrityError:
            logger.info(
                "payment.webhook.duplicate trace_id=%s gateway=%s event_id=%s",
                trace_id,
                normalized_gateway,
                event_id,
            )
            return {"status": "duplicate", "event_id": event_id}

        try:
            if not verify_vnpay_signature(payload, settings.vnp_hash_secret):
                raise InvalidPaymentSignatureError()

            transaction_id = str(payload.get("vnp_TxnRef", ""))
            if not transaction_id:
                raise ValidationError(message="Missing vnp_TxnRef in webhook payload")

            payment_result = await self.db.execute(
                select(Payment)
                .where(
                    Payment.transaction_id == transaction_id,
                    Payment.is_deleted == False,
                )
                .with_for_update()
            )
            payment = payment_result.scalar_one_or_none()
            if not payment:
                raise NotFoundError(message="Payment not found for webhook transaction")

            order_result = await self.db.execute(
                select(Order)
                .where(
                    Order.id == payment.order_id,
                    Order.is_deleted == False,
                )
                .with_for_update()
            )
            order = order_result.scalar_one_or_none()
            if not order:
                raise NotFoundError(message="Order not found for payment")

            payment_just_completed = False
            if self._is_vnp_success(payload):
                if PaymentStatus(payment.status) != PaymentStatus.COMPLETED:
                    payment.status = PaymentStatus.COMPLETED.value
                    payment.gateway_transaction_id = str(payload.get("vnp_TransactionNo") or None)
                    payment.gateway_response = json.dumps(payload, sort_keys=True)
                    payment.error_code = None
                    payment.error_message = None
                    payment_just_completed = True

                    current_order_status = OrderStatus(order.status)
                    if current_order_status == OrderStatus.PENDING:
                        order.status = OrderStatus.CONFIRMED.value
                        self.db.add(
                            OrderStatusHistory(
                                order_id=order.id,
                                from_status=OrderStatus.PENDING.value,
                                to_status=OrderStatus.CONFIRMED.value,
                                changed_by=None,
                                reason="Payment confirmed by VNPAY webhook",
                            )
                        )
                    elif current_order_status not in {
                        OrderStatus.CONFIRMED,
                        OrderStatus.PREPARING,
                        OrderStatus.READY,
                        OrderStatus.PICKING_UP,
                        OrderStatus.DELIVERING,
                        OrderStatus.DELIVERED,
                    }:
                        raise InvalidStateTransitionError(
                            message=f"Cannot confirm order from status {order.status}"
                        )
            else:
                if PaymentStatus(payment.status) not in {
                    PaymentStatus.COMPLETED,
                    PaymentStatus.REFUNDED,
                }:
                    payment.status = PaymentStatus.FAILED.value
                    payment.error_code = str(payload.get("vnp_ResponseCode") or "UNKNOWN")
                    payment.error_message = "Payment failed via VNPAY webhook"
                    payment.gateway_response = json.dumps(payload, sort_keys=True)

            if payment_just_completed:
                try:
                    await self._notify_merchant_paid_order(order=order, payment=payment)
                    await self._notify_user_payment_confirmed(order=order, payment=payment)
                except Exception as notify_error:
                    logger.warning(
                        "payment.webhook.notify_failed trace_id=%s event_id=%s error=%s",
                        trace_id,
                        event_id,
                        str(notify_error),
                    )

            await self.repo.mark_webhook_processed(webhook_event)
            logger.info(
                "payment.webhook.processed trace_id=%s event_id=%s payment_id=%s status=%s",
                trace_id,
                event_id,
                payment.id,
                payment.status,
            )
            return {"status": "processed", "event_id": event_id}
        except Exception as exc:
            await self.repo.mark_webhook_error(webhook_event, str(exc))
            # Persist webhook audit trail even for rejected events.
            await self.db.commit()
            logger.warning(
                "payment.webhook.failed trace_id=%s event_id=%s error=%s",
                trace_id,
                event_id,
                str(exc),
            )
            raise

    # Saved payment methods
    async def add_payment_method(
        self,
        user_id: str,
        data: AddPaymentMethodRequest,
    ) -> SavedPaymentMethodResponse:
        """Add a saved payment method."""
        existing_default_result = await self.db.execute(
            select(PaymentMethodModel).where(
                PaymentMethodModel.user_id == user_id,
                PaymentMethodModel.is_default == True,
                PaymentMethodModel.is_deleted == False,
            )
        )
        has_default = existing_default_result.scalar_one_or_none() is not None

        payment_method = PaymentMethodModel(
            user_id=user_id,
            type=data.type if isinstance(data.type, str) else data.type.value,
            token=data.token,
            gateway="vnpay",
            is_default=not has_default,
        )
        self.db.add(payment_method)
        await self.db.flush()
        return SavedPaymentMethodResponse.model_validate(payment_method)

    async def get_payment_methods(
        self,
        user_id: str,
    ) -> list[SavedPaymentMethodResponse]:
        """Get user's saved payment methods."""
        result = await self.db.execute(
            select(PaymentMethodModel)
            .where(
                PaymentMethodModel.user_id == user_id,
                PaymentMethodModel.is_deleted == False,
            )
            .order_by(
                PaymentMethodModel.is_default.desc(),
                PaymentMethodModel.created_at.desc(),
            )
        )
        methods = result.scalars().all()
        return [SavedPaymentMethodResponse.model_validate(item) for item in methods]

    async def delete_payment_method(
        self,
        user_id: str,
        method_id: str,
    ) -> None:
        """Delete a saved payment method."""
        result = await self.db.execute(
            select(PaymentMethodModel).where(
                PaymentMethodModel.id == method_id,
                PaymentMethodModel.user_id == user_id,
                PaymentMethodModel.is_deleted == False,
            )
        )
        method = result.scalar_one_or_none()
        if not method:
            raise NotFoundError(message="Payment method not found")
        method.soft_delete()
        await self.db.flush()

    async def set_default_payment_method(
        self,
        user_id: str,
        method_id: str,
    ) -> None:
        """Set a payment method as default."""
        result = await self.db.execute(
            select(PaymentMethodModel).where(
                PaymentMethodModel.id == method_id,
                PaymentMethodModel.user_id == user_id,
                PaymentMethodModel.is_deleted == False,
            )
        )
        method = result.scalar_one_or_none()
        if not method:
            raise NotFoundError(message="Payment method not found")

        all_methods = (
            (
                await self.db.execute(
                    select(PaymentMethodModel).where(
                        PaymentMethodModel.user_id == user_id,
                        PaymentMethodModel.is_deleted == False,
                    )
                )
            )
            .scalars()
            .all()
        )
        for item in all_methods:
            item.is_default = item.id == method_id
        await self.db.flush()
