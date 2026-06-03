import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TypeVar

import httpx
from openai import APIStatusError, APITimeoutError, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import SystemConfig

logger = logging.getLogger(__name__)

_AI_RETRY_ATTEMPTS = 4
_AI_RETRY_BASE_DELAY_SECONDS = 1.0
_AI_RETRY_MAX_DELAY_SECONDS = 8.0
_T = TypeVar("_T")


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
        max_retries=0,
    )


def _retry_after_seconds(exc: APIStatusError) -> float | None:
    retry_after = exc.response.headers.get("Retry-After")
    if not retry_after:
        return None

    try:
        return max(0.0, float(retry_after))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(retry_after)
    except (TypeError, ValueError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def _retry_delay_seconds(exc: APIStatusError | None, attempt: int) -> float:
    if exc is None:
        backoff = _AI_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
        return min(backoff, _AI_RETRY_MAX_DELAY_SECONDS)

    provider_delay = _retry_after_seconds(exc)
    if provider_delay is not None:
        return min(provider_delay, _AI_RETRY_MAX_DELAY_SECONDS)

    backoff = _AI_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
    return min(backoff, _AI_RETRY_MAX_DELAY_SECONDS)


async def run_ai_request_with_retry(
    operation: Callable[[], Awaitable[_T]],
    *,
    operation_name: str,
    retry_attempts: int = _AI_RETRY_ATTEMPTS,
) -> _T:
    """Run an AI provider request with explicit retries for 429 and timeout responses."""
    for attempt in range(1, retry_attempts + 1):
        try:
            return await operation()
        except APIStatusError as exc:
            if exc.status_code != 429 or attempt >= retry_attempts:
                raise

            delay = _retry_delay_seconds(exc, attempt)
            logger.warning(
                "[AI] Provider returned 429 for %s; retrying in %.1fs (attempt %d/%d)",
                operation_name,
                delay,
                attempt + 1,
                retry_attempts,
            )
            await asyncio.sleep(delay)
        except APITimeoutError:
            if attempt >= retry_attempts:
                raise

            delay = _retry_delay_seconds(None, attempt)
            logger.warning(
                "[AI] Provider timed out for %s; retrying in %.1fs (attempt %d/%d)",
                operation_name,
                delay,
                attempt + 1,
                retry_attempts,
            )
            await asyncio.sleep(delay)

    raise RuntimeError("AI retry loop exited unexpectedly")


async def create_chat_completion_with_retry(
    client: AsyncOpenAI,
    *,
    model: str,
    messages: list[ChatCompletionMessageParam],
    max_tokens: int,
    temperature: float,
    retry_attempts: int = _AI_RETRY_ATTEMPTS,
) -> ChatCompletion:
    """Create a chat completion with explicit retries for 429 and timeout responses."""

    async def create_completion() -> ChatCompletion:
        return await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    return await run_ai_request_with_retry(
        create_completion,
        operation_name="chat completion",
        retry_attempts=retry_attempts,
    )
