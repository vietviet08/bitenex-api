import json
import logging
import re

from openai import OpenAIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.modules.admin.ai_settings import (
    create_ai_client,
    create_chat_completion_with_retry,
    get_ai_runtime_settings,
)
from app.modules.merchant.models import Merchant
from app.modules.merchant.schemas import (
    MenuDescriptionGenerateRequest,
    MenuDescriptionGenerateResponse,
)

logger = logging.getLogger(__name__)

_LLM_TIMEOUT = 30

_SYSTEM_PROMPT = """You are a Vietnamese food delivery menu copywriter.
Write concise, appetizing Vietnamese menu descriptions for merchant menu items.
Return ONLY valid JSON with this shape:
{"description":"..."}

Rules:
- The description must be Vietnamese.
- Keep it one sentence, 25-45 Vietnamese words.
- Mention concrete flavor, ingredients, texture, freshness, or serving context.
- Do not invent medical claims, discounts, ratings, awards, or unavailable ingredients.
- Do not include markdown, emoji, hashtags, quotes, or a price.
"""

_TONE_LABELS = {
    "appetizing": "mouth-watering, clear, suitable for a food delivery app",
    "premium": "polished and premium, but still natural",
    "casual": "friendly, simple, everyday Vietnamese",
    "healthy": "fresh and balanced without making medical claims",
}


async def _get_owner_merchant(db: AsyncSession, owner_user_id: str) -> Merchant:
    result = await db.execute(
        select(Merchant).where(
            Merchant.user_id == owner_user_id,
            Merchant.is_deleted.is_(False),
        )
    )
    merchant = result.scalar_one_or_none()
    if merchant is None:
        raise NotFoundError(message="Merchant not found")
    return merchant


def _build_user_prompt(
    merchant: Merchant,
    data: MenuDescriptionGenerateRequest,
) -> str:
    parts = [
        f"Merchant name: {merchant.name}",
        f"Menu item name: {data.name}",
        f"Tone: {_TONE_LABELS[data.tone]}",
    ]
    if data.category:
        parts.append(f"Category: {data.category}")
    if data.price:
        parts.append(f"Price for context only, do not include it: {data.price:,.0f} VND")
    if data.existing_description:
        parts.append(f"Current draft to improve: {data.existing_description}")
    return "\n".join(parts)


def _extract_description(raw: str) -> str:
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        description = cleaned
    else:
        description = str(parsed.get("description") or "").strip()

    description = description.strip().strip('"').strip("'")
    description = re.sub(r"\s+", " ", description)
    if not description:
        raise ValueError("AI returned an empty description")
    return description[:500]


async def generate_menu_description(
    db: AsyncSession,
    *,
    owner_user_id: str,
    data: MenuDescriptionGenerateRequest,
) -> MenuDescriptionGenerateResponse:
    """Generate an editable menu item description for the current merchant."""
    runtime_settings = await get_ai_runtime_settings(db)
    if runtime_settings is None:
        raise ValidationError(message="AI settings are not configured")

    merchant = await _get_owner_merchant(db, owner_user_id)
    client = create_ai_client(runtime_settings, _LLM_TIMEOUT)

    try:
        response = await create_chat_completion_with_retry(
            client,
            model=runtime_settings.chat_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(merchant, data)},
            ],
            max_tokens=220,
            temperature=0.7,
        )
        raw = response.choices[0].message.content or ""
        description = _extract_description(raw)
    except (OpenAIError, json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("[MenuAI] Description generation failed: %s", exc)
        raise ExternalServiceError(message=f"Unable to generate description: {exc}") from exc
    except Exception as exc:
        logger.error("[MenuAI] Unexpected description generation error: %s", exc)
        raise ExternalServiceError(message="Unable to generate description") from exc

    return MenuDescriptionGenerateResponse(
        description=description,
        model=runtime_settings.chat_model,
    )
