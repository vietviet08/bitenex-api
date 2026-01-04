from typing import Any


class BitenexException(Exception):
    """
    Base exception for all application-specific errors.
    All custom exceptions should inherit from this class.
    
    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error error_code
        status_code: HTTP status error_code for API response
        details: Additional error details
    """
    
    message: str = "An unexpected error occurred"
    error_code: str = "INTERNAL_ERROR"
    status_code: int = 500
    
    def __init__(
        self,
        message: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message or self.__class__.message
        self.error_code = error_code or self.__class__.error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": {
                "error_code": self.error_code,
                "message": self.message,
                "details": self.details,
            }
        }


class AuthenticationError(BitenexException):
    """Raised when authentication fails."""
    message = "Authentication failed"
    error_code = "AUTHENTICATION_ERROR"
    status_code = 401


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired."""
    message = "Token has expired"
    error_code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid."""
    message = "Invalid token"
    error_code = "INVALID_TOKEN"


class AuthorizationError(BitenexException):
    """Raised when user lacks required permissions."""
    message = "You don't have permission to perform this action"
    error_code = "AUTHORIZATION_ERROR"
    status_code = 403


class InsufficientRoleError(AuthorizationError):
    """Raised when user's role is insufficient for the operation."""
    message = "Insufficient role for this operation"
    error_code = "INSUFFICIENT_ROLE"


class NotFoundError(BitenexException):
    """Raised when a requested resource is not found."""
    message = "Resource not found"
    error_code = "NOT_FOUND"
    status_code = 404


class ConflictError(BitenexException):
    """Raised when there's a conflict with existing resource."""
    message = "Resource conflict"
    error_code = "CONFLICT"
    status_code = 409


class DuplicateError(ConflictError):
    """Raised when attempting to create a duplicate resource."""
    message = "Resource already exists"
    error_code = "DUPLICATE"


class ValidationError(BitenexException):
    """Raised when input validation fails."""
    message = "Validation error"
    error_code = "VALIDATION_ERROR"
    status_code = 400


class BadRequestError(BitenexException):
    """Raised for general bad request errors."""
    message = "Bad request"
    error_code = "BAD_REQUEST"
    status_code = 400


class BusinessError(BitenexException):
    """Base exception for business logic errors."""
    message = "Business rule violation"
    error_code = "BUSINESS_ERROR"
    status_code = 400


class OrderError(BusinessError):
    """Raised for order-related business errors."""
    error_code = "ORDER_ERROR"


class PaymentError(BusinessError):
    """Raised for payment-related errors."""
    error_code = "PAYMENT_ERROR"


class DispatchError(BusinessError):
    """Raised for dispatch/delivery-related errors."""
    error_code = "DISPATCH_ERROR"


class ExternalServiceError(BitenexException):
    """Raised when an external service fails."""
    message = "External service error"
    error_code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502


class ServiceUnavailableError(BitenexException):
    """Raised when a service is temporarily unavailable."""
    message = "Service temporarily unavailable"
    error_code = "SERVICE_UNAVAILABLE"
    status_code = 503
