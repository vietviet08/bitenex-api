from typing import Any


class BitenexException(Exception):
    """
    Base exception for all application-specific errors.
    All custom exceptions should inherit from this class.
    
    Attributes:
        message: Human-readable error message
        code: Machine-readable error code
        status_code: HTTP status code for API response
        details: Additional error details
    """
    
    message: str = "An unexpected error occurred"
    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    
    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message or self.__class__.message
        self.code = code or self.__class__.code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class AuthenticationError(BitenexException):
    """Raised when authentication fails."""
    message = "Authentication failed"
    code = "AUTHENTICATION_ERROR"
    status_code = 401


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired."""
    message = "Token has expired"
    code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid."""
    message = "Invalid token"
    code = "INVALID_TOKEN"


class AuthorizationError(BitenexException):
    """Raised when user lacks required permissions."""
    message = "You don't have permission to perform this action"
    code = "AUTHORIZATION_ERROR"
    status_code = 403


class InsufficientRoleError(AuthorizationError):
    """Raised when user's role is insufficient for the operation."""
    message = "Insufficient role for this operation"
    code = "INSUFFICIENT_ROLE"


class NotFoundError(BitenexException):
    """Raised when a requested resource is not found."""
    message = "Resource not found"
    code = "NOT_FOUND"
    status_code = 404


class ConflictError(BitenexException):
    """Raised when there's a conflict with existing resource."""
    message = "Resource conflict"
    code = "CONFLICT"
    status_code = 409


class DuplicateError(ConflictError):
    """Raised when attempting to create a duplicate resource."""
    message = "Resource already exists"
    code = "DUPLICATE"


class ValidationError(BitenexException):
    """Raised when input validation fails."""
    message = "Validation error"
    code = "VALIDATION_ERROR"
    status_code = 400


class BadRequestError(BitenexException):
    """Raised for general bad request errors."""
    message = "Bad request"
    code = "BAD_REQUEST"
    status_code = 400


class BusinessError(BitenexException):
    """Base exception for business logic errors."""
    message = "Business rule violation"
    code = "BUSINESS_ERROR"
    status_code = 400


class OrderError(BusinessError):
    """Raised for order-related business errors."""
    code = "ORDER_ERROR"


class PaymentError(BusinessError):
    """Raised for payment-related errors."""
    code = "PAYMENT_ERROR"


class DispatchError(BusinessError):
    """Raised for dispatch/delivery-related errors."""
    code = "DISPATCH_ERROR"


class ExternalServiceError(BitenexException):
    """Raised when an external service fails."""
    message = "External service error"
    code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502


class ServiceUnavailableError(BitenexException):
    """Raised when a service is temporarily unavailable."""
    message = "Service temporarily unavailable"
    code = "SERVICE_UNAVAILABLE"
    status_code = 503
