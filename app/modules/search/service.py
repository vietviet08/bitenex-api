# =============================================================================
# Semantic Smart Search - Service Layer (LLM-Powered)
# =============================================================================
# Architecture:
#   1. Parse user's natural language query with LLM (aws/claude-haiku-4-5)
#      → extract English food keywords, food_types, food_attributes
#   2. Run multi-term ILIKE search across menu_items and merchants in PostgreSQL
#   3. Score results by number of keyword matches (relevance ranking)
#   4. Gracefully fall back to simple ILIKE if LLM is unavailable
#
# Why LLM + ILIKE instead of pgvector embedding:
#   - The proxy (vertex-key.com) has no embedding models available
#   - LLM query parsing gives true semantic understanding (Vietnamese → English)
#   - Works with existing PostgreSQL, no vector extension required for search
# =============================================================================

import json
import logging
import re
from typing import List, Optional, Tuple

import httpx
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
# OpenAI / Proxy LLM client
# ---------------------------------------------------------------------------

_openai_client: Optional[AsyncOpenAI] = None

_LLM_TIMEOUT = 25  # seconds

_QUERY_PARSER_SYSTEM = """You are a food search assistant for a Vietnamese food delivery app.
Given a Vietnamese or English natural language query, extract relevant search terms.
Return ONLY valid JSON (no markdown, no backticks) with these fields:
- keywords: list of 5-10 English search keywords that describe the food/restaurant
- food_types: list of specific food names in English related to the query
- food_attributes: list of attributes (light, hot, spicy, healthy, breakfast, late-night, etc.)

Rules:
- Always include transliterated Vietnamese food names (banh mi, pho, bun bo, etc.)
- Think about what Vietnamese foods match the intent
- Include both specific and general terms"""


def _get_llm_client() -> Optional[AsyncOpenAI]:
    """Return a lazily-initialized AsyncOpenAI client configured for the proxy."""
    global _openai_client
    if _openai_client is None:
        if not settings.openai_api_key:
            logger.warning("[SemanticSearch] OPENAI_API_KEY not configured — will use keyword fallback")
            return None
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            http_client=httpx.AsyncClient(timeout=_LLM_TIMEOUT),
        )
    return _openai_client


# ---------------------------------------------------------------------------
# LLM Query Parser
# ---------------------------------------------------------------------------


async def parse_query_with_llm(query: str) -> Optional[dict]:
    """
    Use LLM to parse a natural language food query into structured search terms.

    Returns dict with keys: keywords, food_types, food_attributes
    Returns None on failure (caller should fall back to simple ILIKE).
    """
    client = _get_llm_client()
    if client is None:
        return None

    try:
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": _QUERY_PARSER_SYSTEM},
                {"role": "user", "content": f'Query: "{query}"'},
            ],
            max_tokens=400,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if LLM wraps in ```json
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        parsed = json.loads(raw)
        logger.info("[SemanticSearch] LLM parsed query %r → %s", query, parsed)
        return parsed

    except (OpenAIError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("[SemanticSearch] LLM parse failed: %s", exc)
        return None
    except Exception as exc:
        logger.error("[SemanticSearch] Unexpected LLM error: %s", exc)
        return None


def _build_search_terms(query: str, parsed: Optional[dict]) -> List[str]:
    """
    Combine original query words + LLM-parsed terms into a flat list of search terms.
    Deduplicates and normalises to lowercase.
    """
    terms: List[str] = []

    # Always include original query words (handles direct matches like "Bánh mì")
    terms.extend(query.lower().split())

    if parsed:
        for key in ("keywords", "food_types", "food_attributes"):
            items = parsed.get(key, [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, str):
                        # Split multi-word terms as well
                        terms.extend(item.lower().split())

    # Deduplicate preserving order
    seen = set()
    unique: List[str] = []
    for t in terms:
        t = t.strip().strip(",.;:")
        if t and t not in seen and len(t) > 1:
            seen.add(t)
            unique.append(t)

    return unique


# ---------------------------------------------------------------------------
# Multi-term ILIKE search
# ---------------------------------------------------------------------------


def _score_row(name: str, description: Optional[str], terms: List[str]) -> float:
    """
    Calculate a relevance score (0-1) based on how many search terms match
    the item's name and description.
    """
    text_blob = f"{name} {description or ''}".lower()
    matches = sum(1 for t in terms if t in text_blob)
    # Normalise: max score at 5+ matches → 1.0
    return min(1.0, matches / max(1, min(5, len(terms))))


async def _search_foods_llm(
    db: AsyncSession,
    terms: List[str],
    limit: int,
) -> List[SemanticSearchResult]:
    """
    Search menu_items using multi-term OR ILIKE, then score and rank by match count.
    """
    if not terms:
        return []

    # Build dynamic OR conditions for each term across name + description
    conditions = []
    params: dict = {}
    for i, term in enumerate(terms[:20]):  # cap at 20 terms
        params[f"t{i}"] = f"%{term}%"
        conditions.append(f"(LOWER(mi.name) LIKE :t{i} OR LOWER(mi.description) LIKE :t{i})")

    where_clause = " OR ".join(conditions)

    sql = text(
        f"""
        SELECT
            mi.id,
            mi.name,
            mi.description,
            mi.price,
            mi.image_url,
            mi.merchant_id,
            m.name AS merchant_name
        FROM menu_items mi
        JOIN merchants m ON mi.merchant_id = m.id
        WHERE mi.is_available = true
          AND mi.is_deleted = false
          AND ({where_clause})
        LIMIT :limit
        """
    )
    params["limit"] = limit * 3  # fetch more to re-rank

    result = await db.execute(sql, params)
    rows = result.fetchall()

    results = []
    for row in rows:
        score = _score_row(row.name, row.description, terms)
        results.append(
            SemanticSearchResult(
                id=row.id,
                type=SearchType.FOOD,
                name=row.name,
                description=row.description,
                match_score=round(score, 4),
                price=row.price,
                image_url=row.image_url,
                merchant_id=row.merchant_id,
                merchant_name=row.merchant_name,
            )
        )

    # Sort by match score descending
    results.sort(key=lambda r: r.match_score, reverse=True)
    return results[:limit]


async def _search_restaurants_llm(
    db: AsyncSession,
    terms: List[str],
    limit: int,
) -> List[SemanticSearchResult]:
    """Search merchants using multi-term OR ILIKE."""
    if not terms:
        return []

    conditions = []
    params: dict = {}
    for i, term in enumerate(terms[:20]):
        params[f"t{i}"] = f"%{term}%"
        conditions.append(
            f"(LOWER(m.name) LIKE :t{i} OR LOWER(m.description) LIKE :t{i} OR LOWER(m.address) LIKE :t{i})"
        )

    where_clause = " OR ".join(conditions)

    sql = text(
        f"""
        SELECT
            m.id,
            m.name,
            m.description,
            m.address,
            m.average_rating,
            m.delivery_fee,
            m.estimated_prep_time
        FROM merchants m
        WHERE m.status = 'ACTIVE'
          AND m.is_deleted = false
          AND ({where_clause})
        LIMIT :limit
        """
    )
    params["limit"] = limit * 3

    result = await db.execute(sql, params)
    rows = result.fetchall()

    results = []
    for row in rows:
        score = _score_row(row.name, row.description, terms)
        results.append(
            SemanticSearchResult(
                id=row.id,
                type=SearchType.RESTAURANT,
                name=row.name,
                description=row.description,
                match_score=round(score, 4),
                address=row.address,
                average_rating=row.average_rating,
                delivery_fee=row.delivery_fee,
                estimated_prep_time=row.estimated_prep_time,
            )
        )

    results.sort(key=lambda r: r.match_score, reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# Simple fallback: pure ILIKE on original query
# ---------------------------------------------------------------------------


async def _search_foods_simple(
    db: AsyncSession,
    query: str,
    limit: int,
) -> List[SemanticSearchResult]:
    """Dead-simple fallback: single ILIKE on the raw query string."""
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
            match_score=0.5,
            price=row.MenuItem.price,
            image_url=row.MenuItem.image_url,
            merchant_id=row.MenuItem.merchant_id,
            merchant_name=row.merchant_name,
        )
        for row in rows
    ]


async def _search_restaurants_simple(
    db: AsyncSession,
    query: str,
    limit: int,
) -> List[SemanticSearchResult]:
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
) -> Tuple[List[SemanticSearchResult], bool]:
    """
    Perform LLM-powered semantic search with ILIKE fallback.

    Flow:
      1. Send query to LLM → get structured keywords
      2. Build multi-term search against menu_items / merchants
      3. Score results by match count, return ranked list
      4. If LLM fails → fall back to simple ILIKE on raw query

    Returns:
        (results, used_fallback)
    """
    # Step 1: Try LLM parsing
    parsed = await parse_query_with_llm(query)
    used_fallback = parsed is None

    food_results: List[SemanticSearchResult] = []
    restaurant_results: List[SemanticSearchResult] = []

    if used_fallback:
        # Simple ILIKE fallback on raw query
        logger.info("[SemanticSearch] LLM unavailable — simple ILIKE fallback for: %r", query)
        if search_type in (SearchType.ALL, SearchType.FOOD):
            food_results = await _search_foods_simple(db, query, limit)
        if search_type in (SearchType.ALL, SearchType.RESTAURANT):
            restaurant_results = await _search_restaurants_simple(db, query, limit)
    else:
        # LLM-powered multi-term search
        terms = _build_search_terms(query, parsed)
        logger.info("[SemanticSearch] Terms for %r: %s", query, terms[:10])

        if search_type in (SearchType.ALL, SearchType.FOOD):
            food_results = await _search_foods_llm(db, terms, limit)
        if search_type in (SearchType.ALL, SearchType.RESTAURANT):
            restaurant_results = await _search_restaurants_llm(db, terms, limit)

    # Merge and sort
    all_results = food_results + restaurant_results
    all_results.sort(key=lambda r: r.match_score, reverse=True)
    return all_results[:limit], used_fallback


# ---------------------------------------------------------------------------
# Indexing (kept for future pgvector use, no-op for now)
# ---------------------------------------------------------------------------


async def index_menu_items(
    db: AsyncSession,
    batch_size: int = 50,
) -> IndexingResponse:
    """
    Placeholder: embedding indexing is not used with the current LLM-based approach.
    Will be activated when an embedding model becomes available on the proxy.
    """
    return IndexingResponse(
        message=(
            "LLM-based semantic search is active — embedding indexing not required. "
            "Embeddings will be used when an embedding model is available on the proxy."
        ),
        indexed_menu_items=0,
        indexed_merchants=0,
        failed=0,
    )


async def index_merchants(
    db: AsyncSession,
    batch_size: int = 50,
) -> IndexingResponse:
    return IndexingResponse(
        message="LLM-based search active — embedding indexing not required.",
        indexed_menu_items=0,
        indexed_merchants=0,
        failed=0,
    )


# ---------------------------------------------------------------------------
# Text builders (kept for future embedding use)
# ---------------------------------------------------------------------------


def _build_menu_item_text(item: MenuItem) -> str:
    parts = [f"Món ăn: {item.name}"]
    if item.description:
        parts.append(f"Mô tả: {item.description}")
    if item.category:
        parts.append(f"Danh mục: {item.category}")
    if item.price:
        parts.append(f"Giá: {item.price:,.0f} VND")
    return " | ".join(parts)


def _build_merchant_text(merchant: Merchant) -> str:
    parts = [f"Nhà hàng: {merchant.name}"]
    if merchant.description:
        parts.append(f"Mô tả: {merchant.description}")
    if merchant.address:
        parts.append(f"Địa chỉ: {merchant.address}")
    return " | ".join(parts)
