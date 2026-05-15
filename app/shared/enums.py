from enum import Enum


class Role(str, Enum):
    """
    User roles for authorization.
    Inherits from str for easy JSON serialization.
    """

    USER = "USER"
    DRIVER = "DRIVER"
    MERCHANT = "MERCHANT"
    ADMIN = "ADMIN"


class OrderStatus(str, Enum):
    """
    Order lifecycle status.
    Represents all possible states of an order.
    """

    PENDING = "PENDING"  # Order created, awaiting payment
    CONFIRMED = "CONFIRMED"  # Payment confirmed, awaiting merchant
    PREPARING = "PREPARING"  # Merchant is preparing the order
    READY = "READY"  # Order ready for pickup
    PICKING_UP = "PICKING_UP"  # Driver is picking up
    DELIVERING = "DELIVERING"  # Driver is delivering
    DELIVERED = "DELIVERED"  # Successfully delivered
    CANCELLED = "CANCELLED"  # Order cancelled
    REFUNDED = "REFUNDED"  # Order refunded
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    FAILED_DELIVERY = "FAILED_DELIVERY"

class PaymentStatus(str, Enum):
    """
    Payment transaction status.
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, Enum):
    """
    Supported payment methods.
    """

    VNPAY = "VNPAY"
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    DIGITAL_WALLET = "DIGITAL_WALLET"
    CASH_ON_DELIVERY = "CASH_ON_DELIVERY"
    BANK_TRANSFER = "BANK_TRANSFER"


class DriverStatus(str, Enum):
    """
    Driver availability status.
    """

    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    BUSY = "BUSY"  # Currently on a delivery
    RETURNING = "RETURNING"  # Returning after delivery


class MerchantStatus(str, Enum):
    """
    Merchant operational status.
    """

    PENDING = "PENDING"  # Awaiting approval
    ACTIVE = "ACTIVE"  # Open for business
    INACTIVE = "INACTIVE"  # Temporarily closed
    SUSPENDED = "SUSPENDED"  # Suspended by admin
    CLOSED = "CLOSED"  # Permanently closed


class NotificationType(str, Enum):
    """
    Types of notifications.
    """

    ORDER_UPDATE = "ORDER_UPDATE"
    PROMOTION = "PROMOTION"
    SYSTEM = "SYSTEM"
    PAYMENT = "PAYMENT"
    CHAT = "CHAT"


class NotificationChannel(str, Enum):
    """
    Notification delivery channels.
    """

    PUSH = "PUSH"
    SMS = "SMS"
    EMAIL = "EMAIL"
    IN_APP = "IN_APP"


class DispatchStrategy(str, Enum):
    """
    Driver dispatch strategies.
    """

    NEAREST = "NEAREST"  # Nearest available driver
    LEAST_BUSY = "LEAST_BUSY"  # Driver with fewest orders
    ROUND_ROBIN = "ROUND_ROBIN"  # Fair distribution
    MANUAL = "MANUAL"  # Manual assignment


class WebhookEvent(str, Enum):
    """
    N8n Workflow Webhook trigger paths.
    """

    USER_REGISTERED = "/webhook/bitenex/user-registered"
    CHECKOUT_ABANDONED = "/webhook/bitenex/checkout-abandoned"
    ORDER_STATUS_CHANGED = "/webhook/bitenex/order-status-changed"
    ORDER_DELIVERED = "/webhook/bitenex/order-delivered"
    PAYMENT_FAILED = "/webhook/bitenex/payment-failed"
