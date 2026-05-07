# =============================================================================
# Semantic Smart Search - Service Layer
# =============================================================================
# Architecture:
#   1. Embed the user's query using OpenAI text-embedding-3-small (via proxy)
#   2. Run cosine-similarity search against pgvector index on menu_items / merchants
#   3. Gracefully fall back to ILIKE keyword search if OpenAI is unavailable
# =============================================================================

import logging
from typing import List, Optional

from openai import AsyncOpenAI, OpenAIError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.merchant.models import MenuItem, Merchant
from app.modules.search.schemas import (
    IndexingResponse,
    SearchType,
    SemanticSearchResult,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# OpenAI client (singleton, reused across requests)
# ---------------------------------------------------------------------------

_openai_client: Optional[AsyncOpenAI] = None


def _get_openai_client() -> Optional[AsyncOpenAI]:
    """Return a lazily-initialized AsyncOpenAI client configured for the proxy."""
    global _openai_client
    if _openai_client is None:
        if not settings.openai_api_key:
            logger.warning("[SemanticSearch] OPENAI_API_KEY not configured — will use keyword fallback")
            return None
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    return _openai_client


# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------


async def embed_text(text_input: str) -> Optional[List[float]]:
    """
    Generate an embedding vector for the given text using OpenAI API (or proxy).
    Returns None when the API is unavailable so the caller can fall back gracefully.
    """
    client = _get_openai_client()
    if client is None:
        return None

    try:
        response = await client.embeddings.create(
            input=text_input,
            model=settings.openai_embedding_model,
        )
        return response.data[0].embedding
    except OpenAIError as exc:
        logger.error("[SemanticSearch] OpenAI embedding error: %s", exc)
        return None
    except Exception as exc:
        logger.error("[SemanticSearch] Unexpected embedding error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Vector similarity search
# ---------------------------------------------------------------------------


async def _search_foods_by_vector(
    db: AsyncSession,
    query_vector: List[float],
    limit: int,
) -> List[SemanticSearchResult]:
    """
    Use pgvector cosine distance to find menu items semantically similar to the query.
    Joins with merchants table to include restaurant name.
    """
    vector_literal = f"[{','.join(str(v) for v in query_vector)}]"
    sql = text(
        """
        SELECT
            mi.id,
            mi.name,
            mi.description,
            mi.price,
            mi.image_url,
            mi.merchant_id,
            m.name AS merchant_name,
            1 - (mi.embedding <=> :query_vec ::vector) AS similarity
        FROM menu_items mi
        JOIN merchants m ON mi.merchant_id = m.id
        WHERE mi.embedding IS NOT NULL
          AND mi.is_available = true
          AND mi.is_deleted = false
        ORDER BY mi.embedding <=> :query_vec ::vector
        LIMIT :limit
        """
    )
    result = await db.execute(sql, {"query_vec": vector_literal, "limit": limit})
    rows = result.fetchall()

    return [
        SemanticSearchResult(
            id=row.id,
            type=SearchType.FOOD,
            name=row.name,
            description=row.description,
            match_score=round(max(0.0, float(row.similarity)), 4),
            price=row.price,
            image_url=row.image_url,
            merchant_id=row.merchant_id,
            merchant_name=row.merchant_name,
        )
        for row in rows
    ]


async def _search_restaurants_by_vector(
    db: AsyncSession,
    query_vector: List[float],
    limit: int,
) -> List[SemanticSearchResult]:
    """
    Use pgvector cosine distance to find restaurants semantically similar to the query.
    """
    vector_literal = f"[{','.join(str(v) for v in query_vector)}]"
    sql = text(
        """
        SELECT
            m.id,
            m.name,
            m.description,
            m.address,
            m.average_rating,
            m.delivery_fee,
            m.estimated_prep_time,
            1 - (m.embedding <=> :query_vec ::vector) AS similarity
        FROM merchants m
        WHERE m.embedding IS NOT NULL
          AND m.status = 'ACTIVE'
          AND m.is_deleted = false
        ORDER BY m.embedding <=> :query_vec ::vector
        LIMIT :limit
        """
    )
    result = await db.execute(sql, {"query_vec": vector_literal, "limit": limit})
    rows = result.fetchall()

    return [
        SemanticSearchResult(
            id=row.id,
            type=SearchType.RESTAURANT,
            name=row.name,
            description=row.description,
            match_score=round(max(0.0, float(row.similarity)), 4),
            address=row.address,
            average_rating=row.average_rating,
            delivery_fee=row.delivery_fee,
            estimated_prep_time=row.estimated_prep_time,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# ILIKE keyword fallback (when OpenAI is unavailable)
# ---------------------------------------------------------------------------


async def _search_foods_by_keyword(
    db: AsyncSession,
    query: str,
    limit: int,
) -> List[SemanticSearchResult]:
    """Keyword fallback using PostgreSQL ILIKE — no vector needed."""
    pattern = f"%{query}%"
    stmt = (
        select(MenuItem, Merchant.name.label("merchant_name"))
        .join(Merchant, MenuItem.merchant_id == Merchant.id)
        .where(
            MenuItem.is_deleted == False,  # noqa: E712
            MenuItem.is_available == True,  # noqa: E712
            (MenuItem.name.ilike(pattern) | MenuItem.description.ilike(pattern)),
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.fetchall()

    return [
        SemanticSearchResult(
            id=row.MenuItem.id,
            type=SearchType.FOOD,
            name=row.MenuItem.name,
            description=row.MenuItem.description,
            match_score=0.5,  # static score for keyword fallback
            price=row.MenuItem.price,
            image_url=row.MenuItem.image_url,
            merchant_id=row.MenuItem.merchant_id,
            merchant_name=row.merchant_name,
        )
        for row in rows
    ]


async def _search_restaurants_by_keyword(
    db: AsyncSession,
    query: str,
    limit: int,
) -> List[SemanticSearchResult]:
    """Keyword fallback for restaurants."""
    pattern = f"%{query}%"
    stmt = (
        select(Merchant)
        .where(
            Merchant.is_deleted == False,  # noqa: E712
            Merchant.status == "ACTIVE",
            (Merchant.name.ilike(pattern) | Merchant.description.ilike(pattern)),
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    merchants = result.scalars().all()

    return [
        SemanticSearchResult(
            id=m.id,
            type=SearchType.RESTAURANT,
            name=m.name,
            description=m.description,
            match_score=0.5,
            address=m.address,
            average_rating=m.average_rating,
            delivery_fee=m.delivery_fee,
            estimated_prep_time=m.estimated_prep_time,
        )
        for m in merchants
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def semantic_search(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    search_type: SearchType = SearchType.ALL,
) -> tuple[List[SemanticSearchResult], bool]:
    """
    Perform semantic search using vector embeddings with ILIKE fallback.

    Returns:
        (results, used_fallback)
        used_fallback=True when OpenAI was unavailable and ILIKE was used instead.
    """
    query_vector = await embed_text(query)
    used_fallback = query_vector is None

    if used_fallback:
        logger.info("[SemanticSearch] Using keyword fallback for query: %r", query)
        food_results: List[SemanticSearchResult] = []
        restaurant_results: List[SemanticSearchResult] = []

        if search_type in (SearchType.ALL, SearchType.FOOD):
            food_results = await _search_foods_by_keyword(db, query, limit)
        if search_type in (SearchType.ALL, SearchType.RESTAURANT):
            restaurant_results = await _search_restaurants_by_keyword(db, query, limit)
    else:
        logger.info("[SemanticSearch] Vector search for query: %r", query)
        food_results = []
        restaurant_results = []

        if search_type in (SearchType.ALL, SearchType.FOOD):
            food_results = await _search_foods_by_vector(db, query_vector, limit)
        if search_type in (SearchType.ALL, SearchType.RESTAURANT):
            restaurant_results = await _search_restaurants_by_vector(db, query_vector, limit)

    # Merge and sort by match_score descending
    all_results = food_results + restaurant_results
    all_results.sort(key=lambda r: r.match_score, reverse=True)

    return all_results[:limit], used_fallback


# ---------------------------------------------------------------------------
# Indexing: build embeddings for existing data
# ---------------------------------------------------------------------------


async def index_menu_items(
    db: AsyncSession,
    batch_size: int = 50,
) -> IndexingResponse:
    """
    Generate and store embeddings for all menu items that don't yet have one.
    Should be called once after migration and then on every new item upsert.
    """
    client = _get_openai_client()
    if client is None:
        return IndexingResponse(
            message="OpenAI not configured — indexing skipped",
            failed=0,
        )

    # Fetch items without embedding
    stmt = (
        select(MenuItem)
        .where(
            MenuItem.embedding == None,  # noqa: E711
            MenuItem.is_deleted == False,  # noqa: E712
        )
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    items: List[MenuItem] = list(result.scalars().all())

    indexed = 0
    failed = 0

    for item in items:
        text_for_embedding = _build_menu_item_text(item)
        vector = await embed_text(text_for_embedding)
        if vector:
            item.embedding = vector
            indexed += 1
        else:
            failed += 1

    await db.flush()
    logger.info("[SemanticSearch] Indexed %d menu items (%d failed)", indexed, failed)
    return IndexingResponse(indexed_menu_items=indexed, failed=failed)


async def index_merchants(
    db: AsyncSession,
    batch_size: int = 50,
) -> IndexingResponse:
    """Generate and store embeddings for merchants without one."""
    client = _get_openai_client()
    if client is None:
        return IndexingResponse(
            message="OpenAI not configured — indexing skipped",
            failed=0,
        )

    stmt = (
        select(Merchant)
        .where(
            Merchant.embedding == None,  # noqa: E711
            Merchant.is_deleted == False,  # noqa: E712
            Merchant.status == "ACTIVE",
        )
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    merchants: List[Merchant] = list(result.scalars().all())

    indexed = 0
    failed = 0

    for m in merchants:
        text_for_embedding = _build_merchant_text(m)
        vector = await embed_text(text_for_embedding)
        if vector:
            m.embedding = vector
            indexed += 1
        else:
            failed += 1

    await db.flush()
    logger.info("[SemanticSearch] Indexed %d merchants (%d failed)", indexed, failed)
    return IndexingResponse(indexed_merchants=indexed, failed=failed)


# ---------------------------------------------------------------------------
# Text builders: create rich text representation for embedding
# ---------------------------------------------------------------------------


def _build_menu_item_text(item: MenuItem) -> str:
    """
    Construct a rich text string for embedding a menu item.
    More descriptive text → better semantic matches.
    """
    parts = [f"Món ăn: {item.name}"]
    if item.description:
        parts.append(f"Mô tả: {item.description}")
    if item.category:
        parts.append(f"Danh mục: {item.category}")
    if item.price:
        parts.append(f"Giá: {item.price:,.0f} VND")
    return " | ".join(parts)


def _build_merchant_text(merchant: Merchant) -> str:
    """Construct a rich text string for embedding a merchant/restaurant."""
    parts = [f"Nhà hàng: {merchant.name}"]
    if merchant.description:
        parts.append(f"Mô tả: {merchant.description}")
    if merchant.address:
        parts.append(f"Địa chỉ: {merchant.address}")
    if merchant.city:
        parts.append(f"Thành phố: {merchant.city}")
    return " | ".join(parts)
