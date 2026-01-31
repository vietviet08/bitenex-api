# =============================================================================
# Payment Module - Service Layer
# =============================================================================

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payment.schemas import (
    AddPaymentMethodRequest,
    PaymentCreate,
    PaymentResponse,
    RefundCreate,
    RefundResponse,
    SavedPaymentMethodResponse,
)


class PaymentService:
    """
    Payment processing service.
    Handles payments, refunds, and saved payment methods.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payment(
        self,
        user_id: str,
        data: PaymentCreate,
    ) -> PaymentResponse:
        """
        Create a payment for an order.

        Steps:
        1. Validate order
        2. Generate transaction ID
        3. Process with payment gateway
        4. Store payment record
        5. Emit PaymentCompletedEvent on success
        """
        # TODO: Implement
        raise NotImplementedError()

    async def get_payment(self, payment_id: str) -> PaymentResponse | None:
        """Get payment by ID."""
        # TODO: Implement
        raise NotImplementedError()

    async def get_payment_by_transaction(
        self,
        transaction_id: str,
    ) -> PaymentResponse | None:
        """Get payment by transaction ID."""
        # TODO: Implement
        raise NotImplementedError()

    async def get_order_payments(self, order_id: str) -> list[PaymentResponse]:
        """Get all payments for an order."""
        # TODO: Implement
        raise NotImplementedError()

    async def process_refund(
        self,
        data: RefundCreate,
        refunded_by: str,
    ) -> RefundResponse:
        """
        Process a refund.

        Steps:
        1. Validate payment exists and is completed
        2. Validate refund amount
        3. Process with payment gateway
        4. Store refund record
        5. Update order status
        """
        # TODO: Implement
        raise NotImplementedError()

    async def handle_webhook(
        self,
        gateway: str,
        payload: dict,
    ) -> None:
        """
        Handle payment gateway webhook.

        Updates payment status based on gateway events.
        """
        # TODO: Implement
        pass

    # Saved payment methods
    async def add_payment_method(
        self,
        user_id: str,
        data: AddPaymentMethodRequest,
    ) -> SavedPaymentMethodResponse:
        """Add a saved payment method."""
        # TODO: Implement
        raise NotImplementedError()

    async def get_payment_methods(
        self,
        user_id: str,
    ) -> list[SavedPaymentMethodResponse]:
        """Get user's saved payment methods."""
        # TODO: Implement
        raise NotImplementedError()

    async def delete_payment_method(
        self,
        user_id: str,
        method_id: str,
    ) -> None:
        """Delete a saved payment method."""
        # TODO: Implement
        pass

    async def set_default_payment_method(
        self,
        user_id: str,
        method_id: str,
    ) -> None:
        """Set a payment method as default."""
        # TODO: Implement
        pass
