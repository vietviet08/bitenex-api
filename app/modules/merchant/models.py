# =============================================================================
# Merchant Module - ORM Models
# =============================================================================

from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.base import BaseModel
from app.shared.enums import MerchantStatus


class Merchant(BaseModel):
    """
    Merchant/Restaurant profile.
    Contains business information and settings.
    """

    __tablename__ = "merchants"

    # Owner link
    user_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
    )

    # Business info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    logo_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    cover_image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=MerchantStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Location
    address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Business settings
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    min_order_amount: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    delivery_fee: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    estimated_prep_time: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )  # minutes

    # Stats
    average_rating: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    total_orders: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Semantic search embedding (pgvector, 1536 dims for text-embedding-3-small)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536),
        nullable=True,
    )


class MerchantCategory(BaseModel):
    """
    Categories for merchants (cuisine types).
    """

    __tablename__ = "merchant_categories"

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    icon_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class MenuItem(BaseModel):
    """
    Menu items for a merchant.
    """

    __tablename__ = "menu_items"

    merchant_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Semantic search embedding (pgvector, 1536 dims for text-embedding-3-small)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536),
        nullable=True,
    )


class MenuItemOptionGroup(BaseModel):
    """
    Option group for a menu item (e.g., "Size", "Add-ons").
    Each group contains multiple options.
    """

    __tablename__ = "menu_item_option_groups"

    menu_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # 'single' = radio (pick one), 'multiple' = checkbox (pick many)
    selection_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="single",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


class MenuItemOption(BaseModel):
    """
    Individual option within an option group (e.g., "Large", "Extra Cheese").
    """

    __tablename__ = "menu_item_options"

    option_group_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("menu_item_option_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    price_delta: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )


class MerchantReview(BaseModel):
    """
    Customer review for a merchant, submitted after order delivery.
    Drives the AI Review Summarizer feature.
    """

    __tablename__ = "merchant_reviews"

    merchant_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    order_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # Rating 1-5
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Free-text review
    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Merchant reply to the review
    reply: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Reviewer display name (snapshot at review time)
    reviewer_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    reviewer_avatar: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class MerchantReviewSummaryCache(BaseModel):
    """
    Stores LLM-generated AI summary for a merchant's reviews.
    Acts as a 24-hour cache to avoid repeated LLM calls.
    """

    __tablename__ = "merchant_review_summary_cache"

    merchant_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
    )

    # Serialized JSON list: ["Nước dùng ngon", "Phục vụ nhanh"]
    pros_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    cons_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    overall_sentiment: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )  # positive | neutral | negative

    # Full one-sentence summary in Vietnamese
    summary_vi: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Snapshot stats at time of generation
    total_reviews_analyzed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    average_rating_snapshot: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Cache validity — invalidated when new review arrives
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
