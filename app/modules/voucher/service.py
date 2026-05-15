# =============================================================================
# Voucher Module - Service Layer
# =============================================================================

from datetime import datetime, timedelta, timezone

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
from app.shared.enums import VoucherStatus


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
