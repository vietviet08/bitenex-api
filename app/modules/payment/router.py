# =============================================================================
# Payment Module - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, RequireAdmin
from app.modules.payment.schemas import (
    AddPaymentMethodRequest,
    PaymentCreate,
    PaymentResponse,
    RefundCreate,
    RefundResponse,
    SavedPaymentMethodResponse,
)
from app.modules.payment.service import PaymentService
from app.shared.dto import MessageResponse

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


async def get_payment_service(
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
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    """Process payment for an order."""
    return await service.create_payment(user.user_id, data)


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment",
)
async def get_payment(
    payment_id: str,
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    """Get payment by ID."""
    return await service.get_payment(payment_id)


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
    return await service.get_order_payments(order_id)


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
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> RefundResponse:
    """Process a refund. Admin only."""
    return await service.process_refund(data, user.user_id)


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
@router.post(
    "/webhook/{gateway}",
    status_code=status.HTTP_200_OK,
    summary="Payment gateway webhook",
    include_in_schema=False,  # Hide from docs
)
async def payment_webhook(
    gateway: str,
    request: Request,
    service: PaymentService = Depends(get_payment_service),
) -> dict:
    """Handle payment gateway webhooks."""
    payload = await request.json()
    await service.handle_webhook(gateway, payload)
    return {"status": "received"}
