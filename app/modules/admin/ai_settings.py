from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import SystemConfig


@dataclass(frozen=True)
class AIRuntimeSettings:
    api_key: str
    base_url: str
    chat_model: str


async def _get_config_value(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(
        select(SystemConfig.value).where(
            SystemConfig.key == key,
            SystemConfig.is_deleted.is_(False),
        )
    )
    value = result.scalar_one_or_none()
    return value.strip() if value else None


async def get_ai_runtime_settings(db: AsyncSession) -> AIRuntimeSettings | None:
    api_key = await _get_config_value(db, "ai.openai_api_key")
    base_url = await _get_config_value(db, "ai.openai_base_url")
    chat_model = await _get_config_value(db, "ai.openai_chat_model")

    if not api_key or not base_url or not chat_model:
        return None

    return AIRuntimeSettings(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        chat_model=chat_model,
    )


def create_ai_client(settings: AIRuntimeSettings, timeout: int) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        http_client=httpx.AsyncClient(timeout=timeout),
    )
