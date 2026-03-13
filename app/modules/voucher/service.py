# =============================================================================
# Voucher Module - Service Layer
# =============================================================================

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateError, NotFoundError, ValidationError
from app.modules.order.models import Order
from app.modules.voucher.models import Voucher
from app.modules.voucher.schemas import (
    VoucherCreate,
    VoucherListResponse,
    VoucherResponse,
    VoucherUpdate,
    VoucherValidationRequest,
    VoucherValidationResponse,
)
from app.shared.enums import OrderStatus, VoucherDiscountType


class VoucherService:
    """Manage vouchers and voucher validation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _to_utc_aware(dt: datetime | None) -> datetime | None:
        """
        Ensure a datetime is timezone-aware in UTC.

        SQLite (used in tests) can return naive datetimes even when `timezone=True`
        is set on the SQLAlchemy column, which then breaks comparisons against
        timezone-aware `datetime.now(timezone.utc)`.
        """
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _normalize_code(code: str) -> str:
        return code.strip().upper()

    async def _get_voucher_model(self, voucher_id: str) -> Voucher:
        voucher = (
            await self.db.execute(
                select(Voucher).where(
                    Voucher.id == voucher_id,
                    Voucher.is_deleted == False,
                )
            )
        ).scalar_one_or_none()
        if not voucher:
            raise NotFoundError(message="Voucher not found")
        return voucher

    async def _get_voucher_by_code(self, code: str) -> Voucher | None:
        return (
            await self.db.execute(
                select(Voucher).where(
                    Voucher.code == self._normalize_code(code),
                    Voucher.is_deleted == False,
                )
            )
        ).scalar_one_or_none()

    async def _count_active_usages(
        self,
        voucher_id: str,
        *,
        user_id: str | None = None,
    ) -> int:
        filters = [
            Order.voucher_id == voucher_id,
            Order.is_deleted == False,
            Order.status.notin_([OrderStatus.CANCELLED.value, OrderStatus.REFUNDED.value]),
        ]
        if user_id:
            filters.append(Order.user_id == user_id)

        return (
            await self.db.execute(
                select(func.count(Order.id)).where(*filters)
            )
        ).scalar_one()

    def _calculate_discount(self, voucher: Voucher, subtotal: float) -> float:
        if voucher.discount_type == VoucherDiscountType.PERCENTAGE.value:
            discount = subtotal * (float(voucher.discount_value) / 100.0)
        else:
            discount = float(voucher.discount_value)

        if voucher.max_discount_amount is not None:
            discount = min(discount, float(voucher.max_discount_amount))

        return min(discount, subtotal)

    async def create_voucher(self, data: VoucherCreate) -> VoucherResponse:
        existing = await self._get_voucher_by_code(data.code)
        if existing:
            raise DuplicateError(message="Voucher code already exists")

        # `BaseDTO` is configured with `use_enum_values=True`, so `discount_type`
        # may already be a plain string instead of a `VoucherDiscountType` enum.
        # Normalise to the enum *value* while supporting both representations.
        discount_type_value = (
            data.discount_type.value
            if hasattr(data.discount_type, "value")
            else data.discount_type
        )

        voucher = Voucher(
            code=self._normalize_code(data.code),
            description=data.description,
            merchant_id=data.merchant_id,
            discount_type=discount_type_value,
            discount_value=data.discount_value,
            max_discount_amount=data.max_discount_amount,
            min_order_amount=data.min_order_amount,
            usage_limit=data.usage_limit,
            per_user_limit=data.per_user_limit,
            starts_at=data.starts_at,
            expires_at=data.expires_at,
            is_active=data.is_active,
        )
        self.db.add(voucher)
        await self.db.flush()
        await self.db.refresh(voucher)
        return VoucherResponse.model_validate(voucher)

    async def update_voucher(self, voucher_id: str, data: VoucherUpdate) -> VoucherResponse:
        voucher = await self._get_voucher_model(voucher_id)
        payload = data.model_dump(exclude_unset=True)
        if "discount_type" in payload and payload["discount_type"] is not None:
            discount_type = payload["discount_type"]
            payload["discount_type"] = (
                discount_type.value if hasattr(discount_type, "value") else discount_type
            )

        for field, value in payload.items():
            setattr(voucher, field, value)

        await self.db.flush()
        await self.db.refresh(voucher)
        return VoucherResponse.model_validate(voucher)

    async def list_vouchers(
        self,
        *,
        merchant_id: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> VoucherListResponse:
        filters = [Voucher.is_deleted == False]
        if merchant_id:
            filters.append(Voucher.merchant_id == merchant_id)
        if is_active is not None:
            filters.append(Voucher.is_active.is_(is_active))

        items = (
            await self.db.execute(
                select(Voucher)
                .where(*filters)
                .order_by(Voucher.created_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).scalars().all()
        total = (
            await self.db.execute(select(func.count(Voucher.id)).where(*filters))
        ).scalar_one()

        return VoucherListResponse(
            items=[VoucherResponse.model_validate(item) for item in items],
            total=total,
        )

    async def validate_voucher(
        self,
        user_id: str,
        data: VoucherValidationRequest,
    ) -> VoucherValidationResponse:
        voucher = await self._get_voucher_by_code(data.code)
        if not voucher:
            return VoucherValidationResponse(
                code=self._normalize_code(data.code),
                discount_amount=0.0,
                subtotal=data.subtotal,
                total_after_discount=data.subtotal,
                is_valid=False,
                message="Voucher not found",
            )

        now = datetime.now(timezone.utc)
        starts_at = self._to_utc_aware(voucher.starts_at)
        expires_at = self._to_utc_aware(voucher.expires_at)
        if not voucher.is_active:
            raise ValidationError(message="Voucher is inactive")
        if starts_at and starts_at > now:
            raise ValidationError(message="Voucher is not active yet")
        if expires_at and expires_at < now:
            raise ValidationError(message="Voucher has expired")
        if voucher.merchant_id and voucher.merchant_id != data.merchant_id:
            raise ValidationError(message="Voucher is not applicable for this merchant")
        if data.subtotal < float(voucher.min_order_amount):
            raise ValidationError(
                message=f"Voucher requires minimum order value of {float(voucher.min_order_amount):.2f}"
            )

        total_usage = await self._count_active_usages(voucher.id)
        if voucher.usage_limit is not None and total_usage >= voucher.usage_limit:
            raise ValidationError(message="Voucher usage limit reached")

        user_usage = await self._count_active_usages(voucher.id, user_id=user_id)
        if voucher.per_user_limit is not None and user_usage >= voucher.per_user_limit:
            raise ValidationError(message="Voucher usage limit reached for this user")

        discount = self._calculate_discount(voucher, data.subtotal)
        return VoucherValidationResponse(
            code=voucher.code,
            discount_amount=discount,
            subtotal=data.subtotal,
            total_after_discount=max(data.subtotal - discount, 0.0),
            is_valid=True,
            message="Voucher is valid",
        )
