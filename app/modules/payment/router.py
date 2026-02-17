# =============================================================================
# Payment Module - API Router
# =============================================================================

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdmin
from app.core.exceptions import ValidationError
from app.modules.payment.schemas import (
    AddPaymentMethodRequest,
    AdminPaymentListResponse,
    PaymentCreate,
    PaymentResponse,
    RefundCreate,
    RefundResponse,
    SavedPaymentMethodResponse,
)
from app.modules.payment.service import PaymentService
from app.shared.dto import MessageResponse
from app.shared.enums import PaymentMethod, PaymentStatus

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


def get_payment_service(
    db: AsyncSession = Depends(get_db),
) -> PaymentService:
    return PaymentService(db)


# =============================================================================
# Payment Endpoints
# =============================================================================
@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create payment",
)
async def create_payment(
    data: PaymentCreate,
    request: Request,
    user: CurrentUser,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    """Process payment for an order."""
    if not idempotency_key:
        raise ValidationError(
            message="Idempotency-Key header is required",
            error_code="IDEMPOTENCY_KEY_REQUIRED",
        )
    client_ip = request.client.host if request.client else "127.0.0.1"
    return await service.create_payment(
        user.user_id,
        data,
        idempotency_key=idempotency_key,
        endpoint=str(request.url.path),
        client_ip=client_ip,
    )


@router.get(
    "/admin/list",
    response_model=AdminPaymentListResponse,
    summary="Admin list payments",
    dependencies=[RequireAdmin],
)
async def admin_list_payments(
    search: str | None = Query(
        default=None, description="Search by payment/order/transaction/user"
    ),
    status_filter: PaymentStatus | None = Query(default=None, alias="status"),
    method: PaymentMethod | None = Query(default=None),
    order_id: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: PaymentService = Depends(get_payment_service),
) -> AdminPaymentListResponse:
    """List payments for admin dashboards."""
    items, total = await service.get_admin_payments(
        search=search,
        status=status_filter,
        method=method,
        order_id=order_id,
        page=page,
        per_page=per_page,
    )
    return AdminPaymentListResponse(items=items, total=total)


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment",
)
async def get_payment(
    payment_id: UUID,
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    """Get payment by ID."""
    return await service.get_payment(
        str(payment_id),
        actor_user_id=user.user_id,
        actor_role=user.role,
    )


@router.get(
    "/transaction/{transaction_id}",
    response_model=PaymentResponse,
    summary="Get payment by transaction ID",
)
async def get_payment_by_transaction(
    transaction_id: str,
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    """Get payment by transaction reference."""
    return await service.get_payment_by_transaction(
        transaction_id,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )


@router.get(
    "/order/{order_id}",
    response_model=list[PaymentResponse],
    summary="Get order payments",
)
async def get_order_payments(
    order_id: str,
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> list[PaymentResponse]:
    """Get all payments for an order."""
    return await service.get_order_payments(
        order_id,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )


# =============================================================================
# Refund Endpoints
# =============================================================================
@router.post(
    "/refund",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process refund",
    dependencies=[RequireAdmin],
)
async def process_refund(
    data: RefundCreate,
    request: Request,
    user: CurrentUser,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    service: PaymentService = Depends(get_payment_service),
) -> RefundResponse:
    """Process a refund. Admin only."""
    if not idempotency_key:
        raise ValidationError(
            message="Idempotency-Key header is required",
            error_code="IDEMPOTENCY_KEY_REQUIRED",
        )
    return await service.process_refund(
        data,
        user.user_id,
        idempotency_key=idempotency_key,
        endpoint=str(request.url.path),
    )


# =============================================================================
# Saved Payment Methods
# =============================================================================
@router.get(
    "/methods",
    response_model=list[SavedPaymentMethodResponse],
    summary="Get saved payment methods",
)
async def get_payment_methods(
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> list[SavedPaymentMethodResponse]:
    """Get user's saved payment methods."""
    return await service.get_payment_methods(user.user_id)


@router.post(
    "/methods",
    response_model=SavedPaymentMethodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add payment method",
)
async def add_payment_method(
    data: AddPaymentMethodRequest,
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> SavedPaymentMethodResponse:
    """Add a new payment method."""
    return await service.add_payment_method(user.user_id, data)


@router.delete(
    "/methods/{method_id}",
    response_model=MessageResponse,
    summary="Delete payment method",
)
async def delete_payment_method(
    method_id: str,
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> MessageResponse:
    """Delete a saved payment method."""
    await service.delete_payment_method(user.user_id, method_id)
    return MessageResponse(message="Payment method deleted")


@router.post(
    "/methods/{method_id}/default",
    response_model=MessageResponse,
    summary="Set default payment method",
)
async def set_default_payment_method(
    method_id: str,
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> MessageResponse:
    """Set a payment method as default."""
    await service.set_default_payment_method(user.user_id, method_id)
    return MessageResponse(message="Default payment method updated")


# =============================================================================
# Webhook Endpoint
# =============================================================================
async def _read_webhook_payload(request: Request) -> dict:
    if request.query_params:
        return dict(request.query_params)
    try:
        body = await request.json()
        if isinstance(body, dict):
            return body
    except Exception:
        pass
    return {}


@router.api_route(
    "/webhook/{gateway}",
    methods=["GET", "POST"],
    status_code=status.HTTP_200_OK,
    summary="Payment gateway webhook",
    include_in_schema=False,
)
async def payment_webhook(
    gateway: str,
    request: Request,
    service: PaymentService = Depends(get_payment_service),
) -> dict[str, str]:
    """Handle payment gateway webhooks."""
    payload = await _read_webhook_payload(request)
    result = await service.handle_webhook(gateway, payload)
    return result
