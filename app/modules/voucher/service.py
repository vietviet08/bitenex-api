# =============================================================================
# Voucher Module - Service Layer
# =============================================================================

from datetime import datetime, timedelta, timezone

from polars import Decimal
from requests import RequestException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.journey.models import JourneyOffer
from app.modules.voucher.schemas import (
    IssueVoucherResponse,
    VoucherCreateRequest,
    VoucherResponse,
    VoucherUpdateRequest,
    VoucherValidateResponse,
)
from app.shared.enums import VoucherStatus, VoucherType


class VoucherService:
    """Service for voucher operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_user_vouchers(
        self,
        user_id: str,
        status_filter: VoucherStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[VoucherResponse], int]:
        """List vouchers for a user."""
        query = select(JourneyOffer).where(
            JourneyOffer.user_id == user_id,
            JourneyOffer.is_deleted.is_(False),
        )

        if status_filter:
            query = query.where(JourneyOffer.status == status_filter.value)

        result = await self.db.execute(
            query.order_by(desc(JourneyOffer.created_at)).limit(per_page).offset((page - 1) * per_page)
        )
        vouchers = result.scalars().all()

        count_result = await self.db.execute(
            select(func.count(JourneyOffer.id)).where(
                JourneyOffer.user_id == user_id,
                JourneyOffer.is_deleted.is_(False),
            )
        )
        total = count_result.scalar() or 0

        return [self._to_response(v) for v in vouchers], total

    async def get_voucher(self, voucher_id: str, user_id: str | None = None) -> VoucherResponse:
        """Get single voucher by ID."""
        result = await self.db.execute(
            select(JourneyOffer).where(
                JourneyOffer.id == voucher_id,
                JourneyOffer.is_deleted.is_(False),
            )
        )
        voucher = result.scalar_one_or_none()

        if not voucher:
            raise NotFoundError(message="Voucher not found", error_code="VOUCHER_NOT_FOUND")

        if user_id and voucher.user_id != user_id:
            raise ValidationError(
                message="Unauthorized access to voucher",
                error_code="UNAUTHORIZED",
            )

        return self._to_response(voucher)

    async def validate_voucher(
        self,
        code: str,
        user_id: str,
        cart_value: float,
    ) -> VoucherValidateResponse:
        """Validate voucher code for cart."""
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(JourneyOffer).where(
                JourneyOffer.code == code,
                JourneyOffer.user_id == user_id,
                JourneyOffer.is_deleted.is_(False),
            )
        )
        voucher = result.scalar_one_or_none()

        if not voucher:
            return VoucherValidateResponse(
                is_valid=False,
                error_message="Voucher not found",
            )

        if voucher.status != VoucherStatus.ACTIVE.value:
            return VoucherValidateResponse(
                is_valid=False,
                error_message=f"Voucher is {voucher.status.lower()}",
            )

        if voucher.expires_at < now:
            return VoucherValidateResponse(
                is_valid=False,
                error_message="Voucher has expired",
            )

        if voucher.consumed_at is not None:
            return VoucherValidateResponse(
                is_valid=False,
                error_message="Voucher has already been redeemed",
            )

        if cart_value < voucher.min_cart_value:
            return VoucherValidateResponse(
                is_valid=False,
                error_message=f"Minimum cart value is {voucher.min_cart_value}",
            )

        return VoucherValidateResponse(
            is_valid=True,
            code=code,
            discount_amount=float(voucher.max_discount),
        )

    async def create_voucher(
        self,
        admin_user_id: str,
        req: VoucherCreateRequest,
    ) -> VoucherResponse:
        """Admin: Create a manual voucher."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=req.expires_in_days)

        existing = await self.db.execute(
            select(JourneyOffer).where(
                JourneyOffer.code == req.code,
                JourneyOffer.is_deleted.is_(False),
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError(
                message="Voucher code already exists",
                error_code="VOUCHER_EXISTS",
            )

        voucher = JourneyOffer(
            user_id=req.user_id,
            journey_type="voucher",
            source_cart_id=f"manual:{admin_user_id}",
            offer_type="discount",
            code=req.code,
            max_discount=req.max_discount,
            min_cart_value=req.min_cart_value,
            status=VoucherStatus.ACTIVE.value,
            expires_at=expires_at,
        )
        self.db.add(voucher)
        await self.db.flush()
        await self.db.refresh(voucher)

        return self._to_response(voucher)

    async def update_voucher(
        self,
        voucher_id: str,
        admin_user_id: str,
        req: VoucherUpdateRequest,
    ) -> VoucherResponse:
        """Admin: Update a voucher."""
        result = await self.db.execute(
            select(JourneyOffer).where(
                JourneyOffer.id == voucher_id,
                JourneyOffer.is_deleted.is_(False),
            )
        )
        voucher = result.scalar_one_or_none()

        if not voucher:
            raise NotFoundError(message="Voucher not found", error_code="VOUCHER_NOT_FOUND")

        if req.max_discount is not None:
            voucher.max_discount = req.max_discount
        if req.expires_at is not None:
            voucher.expires_at = req.expires_at
        if req.status is not None:
            voucher.status = req.status.value

        await self.db.flush()
        await self.db.refresh(voucher)

        return self._to_response(voucher)

    async def deactivate_voucher(self, voucher_id: str, admin_user_id: str) -> VoucherResponse:
        """Admin: Deactivate a voucher."""
        result = await self.db.execute(
            select(JourneyOffer).where(
                JourneyOffer.id == voucher_id,
                JourneyOffer.is_deleted.is_(False),
            )
        )
        voucher = result.scalar_one_or_none()

        if not voucher:
            raise NotFoundError(message="Voucher not found", error_code="VOUCHER_NOT_FOUND")

        voucher.status = VoucherStatus.CANCELLED.value
        await self.db.flush()
        await self.db.refresh(voucher)

        return self._to_response(voucher)

    async def list_all_vouchers(
        self,
        status_filter: VoucherStatus | None = None,
        user_id_filter: str | None = None,
        code_filter: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[VoucherResponse], int]:
        """Admin: List all vouchers with filters."""
        query = select(JourneyOffer).where(JourneyOffer.is_deleted.is_(False))

        if status_filter:
            query = query.where(JourneyOffer.status == status_filter.value)
        if user_id_filter:
            query = query.where(JourneyOffer.user_id == user_id_filter)
        if code_filter:
            query = query.where(JourneyOffer.code.ilike(f"%{code_filter}%"))

        result = await self.db.execute(
            query.order_by(desc(JourneyOffer.created_at)).limit(per_page).offset((page - 1) * per_page)
        )
        vouchers = result.scalars().all()

        count_result = await self.db.execute(
            select(func.count(JourneyOffer.id)).where(JourneyOffer.is_deleted.is_(False))
        )
        total = count_result.scalar() or 0

        return [self._to_response(v) for v in vouchers], total

    async def issue_voucher(self, user_id: str, code: str, discount_amount: float, expires_in_days: int = 7, reason: str | None = None) -> IssueVoucherResponse:
        """Internal: Issue a voucher (for n8n workflow)."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=expires_in_days)
        source_key = f"marketing:{user_id}:{code}"

        existing_result = await self.db.execute(
            select(JourneyOffer).where(
                JourneyOffer.user_id == user_id,
                JourneyOffer.code == code,
                JourneyOffer.status == VoucherStatus.ACTIVE.value,
                JourneyOffer.expires_at >= now,
                JourneyOffer.is_deleted.is_(False),
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            return IssueVoucherResponse(
                voucherCode=existing.code,
                discountAmount=float(existing.max_discount),
                expiresAt=existing.expires_at,
                isExisting=True,
            )

        voucher = JourneyOffer(
            user_id=user_id,
            journey_type="n8n_marketing",
            source_cart_id=source_key,
            offer_type="discount",
            code=code,
            max_discount=discount_amount,
            min_cart_value=0.0,
            status=VoucherStatus.ACTIVE.value,
            expires_at=expires_at,
            metadata_json=str({"reason": reason or "n8n_workflow"}),
        )
        self.db.add(voucher)
        await self.db.flush()
        await self.db.refresh(voucher)

        return IssueVoucherResponse(
            voucherCode=voucher.code,
            discountAmount=float(voucher.max_discount),
            expiresAt=voucher.expires_at,
            isExisting=False,
        )

    def _to_response(self, voucher: JourneyOffer) -> VoucherResponse:
        """Convert JourneyOffer to VoucherResponse."""
        return VoucherResponse(
            id=voucher.id,
            user_id=voucher.user_id,
            code=voucher.code,
            max_discount=float(voucher.max_discount),
            min_cart_value=float(voucher.min_cart_value),
            status=VoucherStatus(voucher.status),
            expires_at=voucher.expires_at,
            consumed_at=voucher.consumed_at,
            created_at=voucher.created_at,
            updated_at=voucher.updated_at,
        )
    async def apply_voucher(self, code: str, order_subtotal: Decimal, user_id: int) -> dict:
        
        voucher = await self.repository.get_by_code(code)
        
        if not voucher or not voucher.is_active:
            raise BadRequestException("Voucher không tồn tại hoặc không khả dụng") # type: ignore
        
        if voucher.status != VoucherStatus.ACTIVE.value:
            raise BadRequestException("Voucher không còn hiệu lực") # pyright: ignore[reportUndefinedVariable]
        
        
        now = datetime.utcnow()
        if voucher.start_date > now or voucher.end_date < now:
            raise RequestException("Voucher đã hết hạn")

        
        if order_subtotal < voucher.min_order_value:
            raise RequestException(f"Đơn hàng tối thiểu {voucher.min_order_value} để dùng voucher")

        
        if voucher.type == VoucherType.FIXED_AMOUNT.value:
            discount = min(voucher.value, order_subtotal)
        elif voucher.type == VoucherType.PERCENTAGE.value:
            discount = order_subtotal * (voucher.value / 100)
            if voucher.max_discount:
                discount = min(discount, voucher.max_discount)
        else:
            discount = Decimal("0")

        return {
            "voucher_code": voucher.code,
            "discount_amount": round(discount, 2),
            "final_amount": round(order_subtotal - discount, 2),
            "message": "applied successfully",
        }
    async def validate_and_use_voucher(self, code: str, order_subtotal: Decimal, user_id: int):
        """Test + Use voucher - for checkout flow."""
        voucher = await self.repository.get_by_code(code)
        if not voucher:
            raise RequestException("Voucher not found")

        
        if not voucher.is_active or voucher.status != VoucherStatus.ACTIVE.value:
            raise RequestException("Voucher not available")

        
        now = datetime.utcnow()
        if voucher.start_date > now or voucher.end_date < now:
            raise RequestException("Voucher has expired")

        
        if order_subtotal < voucher.min_order_value:
            raise RequestException(f"Order total must be at least {voucher.min_order_value}đ")

        
        if voucher.used_count >= voucher.total_usage_limit:
            raise RequestException("Voucher has reached its usage limit")

        
        user_voucher = await self.repository.get_user_voucher(user_id, voucher.id)
        if user_voucher and user_voucher.times_used >= voucher.per_user_limit:
            raise RequestException("You have used this voucher too many times")

        
        discount = self._calculate_discount(voucher, order_subtotal)

        return {
            "success": True,
            "voucher_code": voucher.code,
            "discount_amount": discount,
            "final_amount": order_subtotal - discount,
            "voucher_id": voucher.id
        }


    def _calculate_discount(self, voucher, order_subtotal: Decimal) -> Decimal:
        if voucher.type == VoucherType.FIXED_AMOUNT.value:
            return min(voucher.value, order_subtotal)
        elif voucher.type == VoucherType.PERCENTAGE.value:
            discount = order_subtotal * (voucher.value / Decimal("100"))
            if voucher.max_discount:
                discount = min(discount, voucher.max_discount)
            return discount
        return Decimal("0")
    async def use_voucher_after_order(self, voucher_id: int, user_id: int):
        await self.repository.increase_usage(voucher_id, user_id)