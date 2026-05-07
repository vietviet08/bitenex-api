# =============================================================================
# Semantic Smart Search - API Router
# =============================================================================

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.search.schemas import (
    IndexAllRequest,
    IndexingResponse,
    SearchType,
    SemanticSearchResponse,
)
from app.modules.search.service import (
    index_menu_items,
    index_merchants,
    semantic_search,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/search", tags=["Smart Search"])

# ---------------------------------------------------------------------------
# Internal API key guard (reused from other internal routers)
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-Internal-Token", auto_error=False)


async def _require_internal_token(
    api_key: str | None = Security(_api_key_header),
) -> None:
    """Validate the internal service token for protected endpoints."""
    if api_key != settings.internal_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API token",
        )


# ---------------------------------------------------------------------------
# Public endpoint — no auth required
# ---------------------------------------------------------------------------


@router.get(
    "/semantic",
    response_model=SemanticSearchResponse,
    summary="Semantic Smart Search",
    description=(
        "Search for food or restaurants using natural language (Vietnamese or English). "
        "Powered by OpenAI embeddings + pgvector cosine similarity. "
        "Automatically falls back to keyword (ILIKE) search when AI is unavailable. "
        "\n\n**Example queries:**\n"
        "- *Tôi đang ốm, muốn ăn món gì đó nóng, dễ tiêu và có vị gừng*\n"
        "- *Tìm quán mở khuya bán đồ ăn vặt quanh đây*\n"
        "- *Đồ ăn ít calo, phù hợp cho người ăn kiêng*"
    ),
)
async def search_semantic(
    q: str = Query(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language query",
        example="Tôi đang ốm muốn ăn gì đó nóng và dễ tiêu",
    ),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    search_type: SearchType = Query(
        default=SearchType.ALL,
        description="Filter by type: food, restaurant, or all",
    ),
    db: AsyncSession = Depends(get_db),
) -> SemanticSearchResponse:
    """
    Semantic Smart Search endpoint.

    Understands natural language intent — not just keywords.
    """
    logger.info("[SearchRouter] Semantic search: q=%r type=%s limit=%d", q, search_type, limit)

    results, used_fallback = await semantic_search(
        db=db,
        query=q,
        limit=limit,
        search_type=search_type,
    )

    return SemanticSearchResponse(
        query=q,
        search_type=search_type,
        results=results,
        total=len(results),
        used_fallback=used_fallback,
    )


# ---------------------------------------------------------------------------
# Internal endpoints — require X-Internal-Token header
# ---------------------------------------------------------------------------


@router.post(
    "/index/all",
    response_model=IndexingResponse,
    summary="[Internal] Bulk index all unindexed items",
    dependencies=[Depends(_require_internal_token)],
)
async def index_all(
    body: IndexAllRequest = IndexAllRequest(),
    db: AsyncSession = Depends(get_db),
) -> IndexingResponse:
    """
    Generate OpenAI embeddings for all menu items and merchants that don't yet have one.
    Call this once after running the migration, and again after bulk data imports.

    Requires `X-Internal-Token` header.
    """
    logger.info("[SearchRouter] Bulk indexing triggered (batch_size=%d)", body.batch_size)

    food_result = await index_menu_items(db, batch_size=body.batch_size)
    restaurant_result = await index_merchants(db, batch_size=body.batch_size)

    return IndexingResponse(
        indexed_menu_items=food_result.indexed_menu_items,
        indexed_merchants=restaurant_result.indexed_merchants,
        failed=food_result.failed + restaurant_result.failed,
        message=(
            f"Indexed {food_result.indexed_menu_items} food items "
            f"and {restaurant_result.indexed_merchants} restaurants. "
            f"Failed: {food_result.failed + restaurant_result.failed}"
        ),
    )
