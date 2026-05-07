# =============================================================================
# Semantic Smart Search - Schemas (DTOs)
# =============================================================================

from enum import Enum
from typing import List, Optional

from pydantic import Field

from app.shared.dto import BaseDTO


class SearchType(str, Enum):
    """Type of entity to search."""

    ALL = "all"
    FOOD = "food"
    RESTAURANT = "restaurant"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class SemanticSearchRequest(BaseDTO):
    """Query params for the semantic search endpoint."""

    q: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language query, e.g. 'Món gì nóng dễ tiêu, có vị gừng'",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return",
    )
    search_type: SearchType = Field(
        default=SearchType.ALL,
        description="Filter results by type: food, restaurant, or all",
    )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class SemanticSearchResult(BaseDTO):
    """A single semantic search result."""

    id: str
    type: SearchType  # "food" or "restaurant"
    name: str
    description: Optional[str] = None
    match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cosine similarity score (1.0 = perfect match)",
    )

    # Food-specific fields
    price: Optional[float] = None
    image_url: Optional[str] = None
    merchant_id: Optional[str] = None
    merchant_name: Optional[str] = None

    # Restaurant-specific fields
    address: Optional[str] = None
    average_rating: Optional[float] = None
    delivery_fee: Optional[float] = None
    estimated_prep_time: Optional[int] = None


class SemanticSearchResponse(BaseDTO):
    """Full response payload for the semantic search endpoint."""

    query: str
    search_type: SearchType
    results: List[SemanticSearchResult]
    total: int
    used_fallback: bool = Field(
        default=False,
        description="True when ILIKE keyword fallback was used instead of vector search",
    )


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


class IndexMenuItemRequest(BaseDTO):
    """Request body to trigger embedding indexing for a specific menu item."""

    menu_item_id: str


class IndexAllRequest(BaseDTO):
    """Trigger bulk indexing for all unindexed items."""

    batch_size: int = Field(default=50, ge=1, le=200)


class IndexingResponse(BaseDTO):
    """Result of an indexing operation."""

    indexed_menu_items: int = 0
    indexed_merchants: int = 0
    failed: int = 0
    message: str = "Indexing complete"
