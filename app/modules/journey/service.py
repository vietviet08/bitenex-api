# =============================================================================
# Journey Module - Service Layer
# =============================================================================

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.models import User
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.journey.models import AbandonedCartJourney, JourneyOffer
from app.modules.journey.schemas import (
    AbandonedCartActivityResponse,
    AbandonedCartActivityUpsert,
    AuthenticatedAbandonedCartActivityUpsert,
    AbandonedCartStatusRequest,
    AbandonedCartStatusResponse,
    CreateFreeshipOfferRequest,
    JourneyOfferResponse,
)
from app.modules.merchant.models import MenuItem, Merchant
from app.modules.order.models import Order
from app.shared.enums import MerchantStatus, WebhookEvent

logger = logging.getLogger(__name__)
settings = get_settings()


class JourneyService:
    """Business logic for lifecycle journeys backed by API data."""

    JOURNEY_ABANDONED_CART = "abandoned_cart_recovery"
    OFFER_TYPE_FREESHIP = "freeship"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_ABANDONED = "ABANDONED"
    STATUS_CHECKED_OUT = "CHECKED_OUT"
    STATUS_INACTIVE = "INACTIVE"
    OFFER_STATUS_ACTIVE = "ACTIVE"

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _serialize_payload(payload: dict | None) -> str | None:
        if not payload:
            return None
        return json.dumps(payload, sort_keys=True)

    @staticmethod
    def _deserialize_payload(payload: str | None) -> dict | None:
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _offer_metadata(offer: JourneyOffer) -> dict | None:
        if not offer.metadata_json:
            return None
        try:
            return json.loads(offer.metadata_json)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _to_activity_response(
        journey: AbandonedCartJourney,
    ) -> AbandonedCartActivityResponse:
        return AbandonedCartActivityResponse.model_validate(journey)

    @staticmethod
    def _to_offer_response(
        offer: JourneyOffer,
        *,
        is_existing: bool = False,
    ) -> JourneyOfferResponse:
        response = JourneyOfferResponse.model_validate(offer)
        response.is_existing = is_existing
        return response

    async def _get_cart_journey(
        self,
        *,
        cart_id: str,
        user_id: str | None = None,
    ) -> AbandonedCartJourney | None:
        filters = [
            AbandonedCartJourney.cart_id == cart_id,
            AbandonedCartJourney.is_deleted.is_(False),
        ]
        if user_id:
            filters.append(AbandonedCartJourney.user_id == user_id)
        result = await self.db.execute(select(AbandonedCartJourney).where(*filters))
        return result.scalar_one_or_none()

    async def _latest_matching_order(
        self,
        *,
        user_id: str,
        merchant_id: str | None,
        since: datetime | None,
    ) -> Order | None:
        filters = [
            Order.user_id == user_id,
            Order.is_deleted.is_(False),
        ]
        if merchant_id:
            filters.append(Order.merchant_id == merchant_id)
        if since is not None:
            filters.append(Order.created_at >= since)

        query: Select[tuple[Order]] = (
            select(Order).where(*filters).order_by(Order.created_at.desc()).limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def upsert_abandoned_cart_activity(
        self,
        data: AbandonedCartActivityUpsert,
    ) -> AbandonedCartActivityResponse:
        merchant_name, restaurant_open, items_available = (
            await self._resolve_cart_context(data)
        )
        journey = await self._get_cart_journey(
            cart_id=data.cart_id, user_id=data.user_id
        )
        last_activity_at = data.last_activity_at or self._now()
        normalized_status = (
            self.STATUS_ACTIVE
            if data.is_active and data.item_count > 0
            else self.STATUS_INACTIVE
        )

        if journey is None:
            journey = AbandonedCartJourney(
                cart_id=data.cart_id,
                user_id=data.user_id,
                merchant_id=data.merchant_id,
                merchant_name=merchant_name,
                cart_value=float(data.cart_value),
                currency=data.currency.upper(),
                item_count=data.item_count,
                restaurant_open=restaurant_open,
                items_available=items_available,
                deep_link=data.deep_link,
                payload_snapshot=self._serialize_payload(data.payload_snapshot),
                status=normalized_status,
                last_activity_at=last_activity_at,
            )
            self.db.add(journey)
        else:
            journey.merchant_id = data.merchant_id
            journey.merchant_name = merchant_name
            journey.cart_value = float(data.cart_value)
            journey.currency = data.currency.upper()
            journey.item_count = data.item_count
            journey.restaurant_open = restaurant_open
            journey.items_available = items_available
            journey.deep_link = data.deep_link
            if data.payload_snapshot is not None:
                journey.payload_snapshot = self._serialize_payload(
                    data.payload_snapshot
                )
            journey.last_activity_at = last_activity_at
            journey.status = normalized_status
            if normalized_status == self.STATUS_ACTIVE:
                # A fresh interaction resets the abandonment detection window.
                journey.abandoned_at = None
                journey.webhook_triggered_at = None
                journey.last_webhook_error = None
                journey.recovered_at = None
                journey.recovery_order_id = None

        await self.db.flush()
        await self.db.refresh(journey)
        return self._to_activity_response(journey)

    async def upsert_user_cart_activity(
        self,
        *,
        user_id: str,
        data: AuthenticatedAbandonedCartActivityUpsert,
    ) -> AbandonedCartActivityResponse:
        return await self.upsert_abandoned_cart_activity(
            AbandonedCartActivityUpsert(
                user_id=user_id,
                **data.model_dump(),
            )
        )

    async def get_abandoned_cart_status(
        self,
        data: AbandonedCartStatusRequest,
    ) -> AbandonedCartStatusResponse:
        journey = await self._get_cart_journey(
            cart_id=data.cart_id, user_id=data.user_id
        )
        if journey is None:
            order = await self._latest_matching_order(
                user_id=data.user_id,
                merchant_id=data.properties.merchant_id if data.properties else None,
                since=data.event_time,
            )
            has_converted = order is not None
            return AbandonedCartStatusResponse(
                cart_id=data.cart_id,
                user_id=data.user_id,
                journey=data.journey,
                cart_status="NOT_FOUND",
                has_converted=has_converted,
                recovery_order_id=order.id if order else None,
                cart_value=data.properties.cart_value if data.properties else 0.0,
                offer_eligible=(
                    (data.properties.cart_value if data.properties else 0.0) >= 150000
                    and not has_converted
                ),
            )

        time_anchor = (
            data.event_time or journey.abandoned_at or journey.last_activity_at
        )
        latest_order = await self._latest_matching_order(
            user_id=journey.user_id,
            merchant_id=journey.merchant_id,
            since=time_anchor,
        )

        if latest_order and journey.recovery_order_id != latest_order.id:
            journey.status = self.STATUS_CHECKED_OUT
            journey.recovered_at = latest_order.created_at
            journey.recovery_order_id = latest_order.id
            await self.db.flush()

        has_converted = journey.recovery_order_id is not None
        return AbandonedCartStatusResponse(
            cart_id=journey.cart_id,
            user_id=journey.user_id,
            journey=data.journey,
            cart_status=journey.status,
            has_converted=has_converted,
            recovery_order_id=journey.recovery_order_id,
            abandoned_at=journey.abandoned_at,
            webhook_triggered_at=journey.webhook_triggered_at,
            cart_value=float(journey.cart_value),
            offer_eligible=(float(journey.cart_value) >= 150000 and not has_converted),
        )

    async def create_freeship_offer(
        self,
        data: CreateFreeshipOfferRequest,
    ) -> JourneyOfferResponse:
        if data.cart_value < data.min_cart_value:
            raise ValidationError(
                message="Cart does not meet the minimum value for a freeship offer",
                details={
                    "cart_value": data.cart_value,
                    "min_cart_value": data.min_cart_value,
                },
            )

        journey = await self._get_cart_journey(
            cart_id=data.cart_id, user_id=data.user_id
        )
        if journey and journey.recovery_order_id:
            raise ValidationError(message="Cart has already been checked out")

        now = self._now()
        existing_result = await self.db.execute(
            select(JourneyOffer).where(
                JourneyOffer.user_id == data.user_id,
                JourneyOffer.source_cart_id == data.cart_id,
                JourneyOffer.offer_type == data.coupon_type,
                JourneyOffer.status == self.OFFER_STATUS_ACTIVE,
                JourneyOffer.is_deleted.is_(False),
                JourneyOffer.expires_at >= now,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            return self._to_offer_response(existing, is_existing=True)

        offer = JourneyOffer(
            user_id=data.user_id,
            journey_type=data.journey,
            source_cart_id=data.cart_id,
            offer_type=data.coupon_type,
            code=self._generate_offer_code(prefix="FSHIP"),
            max_discount=float(data.max_discount),
            min_cart_value=float(data.min_cart_value),
            status=self.OFFER_STATUS_ACTIVE,
            expires_at=now + timedelta(hours=data.expires_in_hours),
            metadata_json=json.dumps(
                {
                    "reason": data.reason,
                    "cart_value": data.cart_value,
                },
                sort_keys=True,
            ),
        )
        self.db.add(offer)
        await self.db.flush()
        await self.db.refresh(offer)
        return self._to_offer_response(offer, is_existing=False)

    async def mark_cart_checked_out_for_order(self, order: Order) -> None:
        result = await self.db.execute(
            select(AbandonedCartJourney)
            .where(
                AbandonedCartJourney.user_id == order.user_id,
                AbandonedCartJourney.merchant_id == order.merchant_id,
                AbandonedCartJourney.status.in_(
                    [self.STATUS_ACTIVE, self.STATUS_ABANDONED]
                ),
                AbandonedCartJourney.is_deleted.is_(False),
            )
            .order_by(AbandonedCartJourney.last_activity_at.desc())
            .limit(1)
        )
        journey = result.scalar_one_or_none()
        if journey is None:
            return

        journey.status = self.STATUS_CHECKED_OUT
        journey.recovered_at = order.created_at or self._now()
        journey.recovery_order_id = order.id
        await self.db.flush()

    async def dispatch_due_abandoned_cart_webhooks(self) -> int:
        webhook_path = WebhookEvent.CHECKOUT_ABANDONED.value
        if not webhook_path:
            return 0

        # Hardcoded 30 minutes timeout for abandoned carts
        cutoff = self._now() - timedelta(minutes=1)
        result = await self.db.execute(
            select(AbandonedCartJourney).where(
                AbandonedCartJourney.status == self.STATUS_ACTIVE,
                AbandonedCartJourney.webhook_triggered_at.is_(None),
                AbandonedCartJourney.last_activity_at <= cutoff,
                AbandonedCartJourney.restaurant_open.is_(True),
                AbandonedCartJourney.items_available.is_(True),
                AbandonedCartJourney.is_deleted.is_(False),
            )
        )
        candidates = result.scalars().all()
        if not candidates:
            return 0

        user_ids = [j.user_id for j in candidates]
        users_result = await self.db.execute(select(User).where(User.id.in_(user_ids)))
        user_map = {u.id: u for u in users_result.scalars().all()}

        dispatched = 0
        async with httpx.AsyncClient(
            base_url=settings.n8n_base_url,
            timeout=httpx.Timeout(10.0),
            headers={"Content-Type": "application/json"},
        ) as client:
            for journey in candidates:
                now = self._now()
                if journey.abandoned_at is None:
                    journey.abandoned_at = now

                user = user_map.get(journey.user_id)

                payload = {
                    "journey": self.JOURNEY_ABANDONED_CART,
                    "customerId": journey.user_id,
                    "checkoutSessionId": journey.cart_id,
                    "merchantName": journey.merchant_name or "Unknown Merchant",
                    "cartValue": float(journey.cart_value),
                    "currency": journey.currency,
                    "deepLink": journey.deep_link
                    or f"bitenexuser://checkout/{journey.cart_id}",
                    "email": user.email if user else "",
                    "phone": user.phone if user else "",
                }

                try:
                    response = await client.post(webhook_path, json=payload)
                    response.raise_for_status()
                except Exception as exc:
                    journey.last_webhook_error = str(exc)
                    continue

                journey.status = self.STATUS_ABANDONED
                journey.webhook_triggered_at = now
                journey.last_webhook_error = None
                dispatched += 1

        await self.db.flush()

        return dispatched

    @staticmethod
    def _generate_offer_code(prefix: str) -> str:
        return f"{prefix}{uuid4().hex[:8].upper()}"

    async def _resolve_cart_context(
        self,
        data: AbandonedCartActivityUpsert,
    ) -> tuple[str | None, bool, bool]:
        merchant_name = data.merchant_name
        restaurant_open = data.restaurant_open
        items_available = data.items_available

        if data.merchant_id:
            merchant_result = await self.db.execute(
                select(Merchant).where(
                    Merchant.id == data.merchant_id,
                    Merchant.is_deleted.is_(False),
                )
            )
            merchant = merchant_result.scalar_one_or_none()
            if merchant:
                merchant_name = merchant.name
                restaurant_open = merchant.status == MerchantStatus.ACTIVE.value
            else:
                restaurant_open = False

        payload_items = (data.payload_snapshot or {}).get("items")
        menu_item_ids = [
            str(item.get("menu_item_id") or item.get("food_item_id"))
            for item in payload_items or []
            if item.get("menu_item_id") or item.get("food_item_id")
        ]
        if menu_item_ids:
            unique_ids = sorted(set(menu_item_ids))
            item_result = await self.db.execute(
                select(MenuItem.id, MenuItem.is_available).where(
                    MenuItem.id.in_(unique_ids),
                    MenuItem.is_deleted.is_(False),
                )
            )
            rows = item_result.all()
            available_ids = {
                menu_item_id for menu_item_id, is_available in rows if is_available
            }
            items_available = len(rows) == len(unique_ids) and len(
                available_ids
            ) == len(unique_ids)

        return merchant_name, restaurant_open, items_available
