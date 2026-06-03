# =============================================================================
# AI Review Summarizer — Service Layer
# =============================================================================
# Feature: Summarize merchant reviews using LLM (aws/claude-haiku-4-5)
# Output : Vietnamese pros/cons + one-sentence summary
# Cache  : Stored in merchant_review_summary_cache (invalidated on new review)
# =============================================================================

from __future__ import annotations

import json
import logging
import re
import statistics
from typing import Optional

from openai import OpenAIError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.ai_settings import (
    create_ai_client,
    create_chat_completion_with_retry,
    get_ai_runtime_settings,
)
from app.modules.merchant.models import Merchant, MerchantReview, MerchantReviewSummaryCache
from app.modules.merchant.schemas import (
    ReviewListResponse,
    ReviewResponse,
    ReviewSummaryResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------------

_LLM_TIMEOUT = 30  # seconds — haiku is fast but we give generous margin
_MAX_REVIEWS_FOR_SUMMARY = 30  # cap to keep prompt size manageable

_SYSTEM_PROMPT = """Bạn là AI chuyên phân tích đánh giá của khách hàng cho ứng dụng giao đồ ăn.

Nhiệm vụ: Đọc các review và trả về JSON với các trường sau:
- "pros": danh sách tối đa 4 ưu điểm nổi bật nhất (tiếng Việt, ngắn gọn 5-15 từ mỗi điểm)
- "cons": danh sách tối đa 3 khuyết điểm phổ biến nhất (tiếng Việt, ngắn gọn 5-15 từ mỗi điểm)  
- "overall_sentiment": "positive" hoặc "neutral" hoặc "negative"
- "summary_vi": 1-2 câu tóm tắt tiếng Việt theo format:
  "✨ Ưu điểm: [tóm tắt ưu]. ⚠️ Khuyết điểm: [tóm tắt nhược]."
  Nếu không có khuyết điểm đáng kể: "✨ [nhà hàng] được đánh giá rất tích cực về [điểm mạnh chính]."

Quy tắc quan trọng:
- Chỉ trả về JSON hợp lệ, KHÔNG có markdown, KHÔNG có backtick
- Ưu/nhược điểm phải dựa trên nội dung thực tế trong review, không bịa đặt
- Nếu ít hơn 3 review: đặt pros=[], cons=[], sentiment="neutral", summary_vi="Chưa đủ đánh giá để tổng hợp."
- Sử dụng ngôn ngữ tự nhiên, thân thiện như đang tư vấn cho bạn bè"""


def _format_reviews_for_llm(reviews: list[MerchantReview], merchant_name: str) -> str:
    """Format reviews into a compact text block for the LLM prompt."""
    lines = [f"Nhà hàng: {merchant_name}"]
    lines.append(f"Tổng số review: {len(reviews)}")
    lines.append("")

    for i, r in enumerate(reviews, 1):
        stars = "★" * r.rating + "☆" * (5 - r.rating)
        reviewer = r.reviewer_name or "Khách hàng"
        comment = r.comment or "(Không có nhận xét)"
        lines.append(f"{i}. [{stars}] {reviewer}: {comment}")

    return "\n".join(lines)


async def _call_llm_summarize(
    db: AsyncSession,
    reviews: list[MerchantReview],
    merchant_name: str,
) -> Optional[dict]:
    """Call the LLM and parse the JSON response. Returns None on failure."""
    runtime_settings = await get_ai_runtime_settings(db)
    if runtime_settings is None:
        logger.warning("[ReviewSummarizer] No LLM client configured")
        return None
    client = create_ai_client(runtime_settings, _LLM_TIMEOUT)

    review_text = _format_reviews_for_llm(reviews[:_MAX_REVIEWS_FOR_SUMMARY], merchant_name)
    avg = statistics.mean(r.rating for r in reviews) if reviews else 0

    user_prompt = (
        f"{review_text}\n\nRating trung bình: {avg:.1f}/5 ({len(reviews)} đánh giá)"
    )

    try:
        response = await create_chat_completion_with_retry(
            client,
            model=runtime_settings.chat_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=600,
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        # Strip possible markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)

        parsed = json.loads(raw)
        logger.info(
            "[ReviewSummarizer] LLM summary for %r: sentiment=%s pros=%d cons=%d",
            merchant_name,
            parsed.get("overall_sentiment"),
            len(parsed.get("pros", [])),
            len(parsed.get("cons", [])),
        )
        return parsed

    except (OpenAIError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("[ReviewSummarizer] LLM call failed: %s", exc)
        return None
    except Exception as exc:
        logger.error("[ReviewSummarizer] Unexpected error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Review CRUD helpers
# ---------------------------------------------------------------------------


async def _get_merchant(db: AsyncSession, merchant_id: str) -> Optional[Merchant]:
    stmt = select(Merchant).where(
        Merchant.id == merchant_id,
        Merchant.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _load_reviews(
    db: AsyncSession,
    merchant_id: str,
) -> list[MerchantReview]:
    stmt = (
        select(MerchantReview)
        .where(
            MerchantReview.merchant_id == merchant_id,
            MerchantReview.is_deleted == False,  # noqa: E712
        )
        .order_by(MerchantReview.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Public Service Functions
# ---------------------------------------------------------------------------


async def list_reviews(
    db: AsyncSession,
    merchant_id: str,
    page: int = 1,
    per_page: int = 10,
) -> ReviewListResponse:
    """List paginated reviews for a merchant with aggregate stats."""
    # Validate merchant exists
    merchant = await _get_merchant(db, merchant_id)
    if merchant is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found",
        )

    # Total count + average
    count_stmt = select(func.count()).where(
        MerchantReview.merchant_id == merchant_id,
        MerchantReview.is_deleted == False,  # noqa: E712
    )
    total = (await db.execute(count_stmt)).scalar_one()

    avg_stmt = select(func.avg(MerchantReview.rating)).where(
        MerchantReview.merchant_id == merchant_id,
        MerchantReview.is_deleted == False,  # noqa: E712
    )
    avg_rating = (await db.execute(avg_stmt)).scalar_one() or 0.0

    # Rating distribution
    dist_stmt = (
        select(MerchantReview.rating, func.count())
        .where(
            MerchantReview.merchant_id == merchant_id,
            MerchantReview.is_deleted == False,  # noqa: E712
        )
        .group_by(MerchantReview.rating)
    )
    dist_rows = (await db.execute(dist_stmt)).fetchall()
    rating_distribution = {str(r): 0 for r in range(1, 6)}
    for rating, cnt in dist_rows:
        rating_distribution[str(rating)] = cnt

    # Paginated items
    offset = (page - 1) * per_page
    items_stmt = (
        select(MerchantReview)
        .where(
            MerchantReview.merchant_id == merchant_id,
            MerchantReview.is_deleted == False,  # noqa: E712
        )
        .order_by(MerchantReview.created_at.desc())
        .limit(per_page)
        .offset(offset)
    )
    items = list((await db.execute(items_stmt)).scalars().all())

    return ReviewListResponse(
        items=[ReviewResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        per_page=per_page,
        average_rating=round(avg_rating, 2),
        rating_distribution=rating_distribution,
    )


async def get_ai_summary(
    db: AsyncSession,
    merchant_id: str,
    force_refresh: bool = False,
) -> ReviewSummaryResponse:
    """
    Get AI-generated summary of reviews for a merchant.

    Flow:
    1. Check cache in merchant_review_summary_cache (is_valid=True)
    2. If valid cache exists → return immediately (no LLM call)
    3. If no/invalid cache → load reviews → call LLM → store in DB → return
    4. If LLM fails → return rule-based fallback summary
    """
    merchant = await _get_merchant(db, merchant_id)
    if merchant is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found",
        )

    # Snapshot merchant fields immediately (avoid lazy-load after session expires)
    merchant_name = str(merchant.name)

    # --- Step 1: Check valid cache ---
    if not force_refresh:
        cache_stmt = select(MerchantReviewSummaryCache).where(
            MerchantReviewSummaryCache.merchant_id == merchant_id,
            MerchantReviewSummaryCache.is_valid == True,  # noqa: E712
            MerchantReviewSummaryCache.is_deleted == False,  # noqa: E712
        )
        cached = (await db.execute(cache_stmt)).scalar_one_or_none()

        if cached:
            logger.info("[ReviewSummarizer] Cache HIT for merchant %s", merchant_id)
            return ReviewSummaryResponse(
                merchant_id=merchant_id,
                merchant_name=merchant_name,
                total_reviews_analyzed=cached.total_reviews_analyzed,
                average_rating=cached.average_rating_snapshot or 0.0,
                overall_sentiment=cached.overall_sentiment or "neutral",
                pros=json.loads(cached.pros_json or "[]"),
                cons=json.loads(cached.cons_json or "[]"),
                summary_vi=cached.summary_vi or "",
                is_cached=True,
                cached_at=cached.updated_at,
            )

    # --- Step 2: Load reviews ---
    reviews = await _load_reviews(db, merchant_id)
    avg_rating = (
        round(statistics.mean(r.rating for r in reviews), 2) if reviews else 0.0
    )

    # --- Step 3: Call LLM ---
    llm_result = None
    if len(reviews) >= 3:
        llm_result = await _call_llm_summarize(db, reviews, merchant_name)

    # --- Step 4: Fallback if LLM unavailable or too few reviews ---
    if llm_result is None:
        llm_result = _generate_fallback_summary(reviews, avg_rating)

    pros = llm_result.get("pros", [])
    cons = llm_result.get("cons", [])
    sentiment = llm_result.get("overall_sentiment", "neutral")
    summary_vi = llm_result.get("summary_vi", "")

    # --- Step 5: Upsert cache ---
    await _upsert_summary_cache(
        db, merchant_id, pros, cons, sentiment, summary_vi,
        total=len(reviews), avg=avg_rating,
    )

    return ReviewSummaryResponse(
        merchant_id=merchant_id,
        merchant_name=merchant_name,
        total_reviews_analyzed=len(reviews),
        average_rating=avg_rating,
        overall_sentiment=sentiment,
        pros=pros,
        cons=cons,
        summary_vi=summary_vi,
        is_cached=False,
        cached_at=None,
    )


async def _upsert_summary_cache(
    db: AsyncSession,
    merchant_id: str,
    pros: list[str],
    cons: list[str],
    sentiment: str,
    summary_vi: str,
    total: int,
    avg: float,
) -> None:
    """Insert or update the summary cache row for a merchant."""
    from datetime import datetime, timezone

    stmt = select(MerchantReviewSummaryCache).where(
        MerchantReviewSummaryCache.merchant_id == merchant_id,
        MerchantReviewSummaryCache.is_deleted == False,  # noqa: E712
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if existing:
        existing.pros_json = json.dumps(pros, ensure_ascii=False)
        existing.cons_json = json.dumps(cons, ensure_ascii=False)
        existing.overall_sentiment = sentiment
        existing.summary_vi = summary_vi
        existing.total_reviews_analyzed = total
        existing.average_rating_snapshot = avg
        existing.is_valid = True
        existing.updated_at = now
    else:
        import uuid

        new_cache = MerchantReviewSummaryCache(
            id=str(uuid.uuid4()),
            merchant_id=merchant_id,
            pros_json=json.dumps(pros, ensure_ascii=False),
            cons_json=json.dumps(cons, ensure_ascii=False),
            overall_sentiment=sentiment,
            summary_vi=summary_vi,
            total_reviews_analyzed=total,
            average_rating_snapshot=avg,
            is_valid=True,
            created_at=now,
            updated_at=now,
            is_deleted=False,
        )
        db.add(new_cache)

    await db.commit()
    logger.info("[ReviewSummarizer] Cache STORED for merchant %s", merchant_id)


async def invalidate_summary_cache(db: AsyncSession, merchant_id: str) -> None:
    """Mark cache as invalid — called when a new review is submitted."""
    stmt = select(MerchantReviewSummaryCache).where(
        MerchantReviewSummaryCache.merchant_id == merchant_id,
        MerchantReviewSummaryCache.is_deleted == False,  # noqa: E712
    )
    cached = (await db.execute(stmt)).scalar_one_or_none()
    if cached:
        cached.is_valid = False
        await db.commit()


def _generate_fallback_summary(reviews: list[MerchantReview], avg: float) -> dict:
    """
    Rule-based fallback when LLM is unavailable or there are < 3 reviews.
    Provides a decent summary without AI.
    """
    if not reviews:
        return {
            "pros": [],
            "cons": [],
            "overall_sentiment": "neutral",
            "summary_vi": "Chưa có đánh giá nào cho nhà hàng này.",
        }

    if len(reviews) < 3:
        return {
            "pros": [],
            "cons": [],
            "overall_sentiment": "neutral",
            "summary_vi": f"Nhà hàng có {len(reviews)} đánh giá. Chưa đủ dữ liệu để tổng hợp AI.",
        }

    five_star = sum(1 for r in reviews if r.rating == 5)
    low_star = sum(1 for r in reviews if r.rating <= 2)
    pct_positive = round(five_star / len(reviews) * 100)
    pct_negative = round(low_star / len(reviews) * 100)

    sentiment = "positive" if avg >= 4.0 else ("negative" if avg < 3.0 else "neutral")

    summary = (
        f"✨ {pct_positive}% khách hàng cho 5 sao. "
        f"Rating trung bình: {avg:.1f}/5."
    )
    if pct_negative > 10:
        summary += f" ⚠️ Khoảng {pct_negative}% đánh giá thấp."

    return {
        "pros": [f"{pct_positive}% khách hàng đánh giá 5 sao"],
        "cons": ([f"Khoảng {pct_negative}% khách hàng chưa hài lòng"] if pct_negative > 10 else []),
        "overall_sentiment": sentiment,
        "summary_vi": summary,
    }
