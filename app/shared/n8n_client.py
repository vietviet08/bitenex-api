# =============================================================================
# N8n Outbound Webhook Client
# =============================================================================
"""
Fire-and-forget client that triggers n8n workflows by posting to n8n webhook
endpoints (e.g., POST http://n8n:5678/webhook/bitenex/user-registered).

Design principles:
- Non-blocking: uses asyncio.create_task so the calling business logic
  is never delayed or failed by n8n being unavailable.
- Silent failure: logs errors but never raises, ensuring n8n downtime cannot
  break the primary API flows.
- Configurable: base URL and enabled flag come from app settings.
"""

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class N8nClient:
    """
    Outbound client for triggering n8n workflows via webhook endpoints.

    Usage (inside any async service method):
        N8nClient.trigger("/webhook/bitenex/user-registered", {
            "userId": user.id,
            "email": user.email,
        })
    """

    # Shared async HTTP client — created once, reused across requests
    _client: httpx.AsyncClient | None = None

    @classmethod
    def _get_client(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                base_url=settings.n8n_base_url,
                timeout=httpx.Timeout(10.0),
                headers={"Content-Type": "application/json"},
            )
        return cls._client

    @classmethod
    def trigger(cls, webhook_path: str, payload: dict[str, Any]) -> None:
        """
        Schedule a non-blocking POST to an n8n webhook endpoint.

        Args:
            webhook_path: Path relative to n8n base URL,
                          e.g. "/webhook/bitenex/user-registered"
            payload:      JSON-serializable dict sent as request body

        This method is intentionally synchronous so it can be called from
        any service without needing `await`. The actual HTTP call runs in
        the background via asyncio.create_task.
        """
        if not settings.n8n_webhook_enabled:
            logger.debug("n8n triggers disabled — skipping %s", webhook_path)
            return

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cls._post(webhook_path, payload))
            else:
                logger.warning(
                    "n8n_client: no running event loop, skipping trigger %s",
                    webhook_path,
                )
        except RuntimeError:
            logger.warning(
                "n8n_client: could not schedule task for %s", webhook_path
            )

    @classmethod
    async def _post(cls, webhook_path: str, payload: dict[str, Any]) -> None:
        """Internal coroutine that performs the actual HTTP POST."""
        try:
            client = cls._get_client()
            response = await client.post(webhook_path, json=payload)
            if response.status_code >= 400:
                logger.warning(
                    "n8n_trigger: %s returned HTTP %s — %s",
                    webhook_path,
                    response.status_code,
                    response.text[:200],
                )
            else:
                logger.info(
                    "n8n_trigger: %s OK (%s)",
                    webhook_path,
                    response.status_code,
                )
        except httpx.RequestError as exc:
            logger.error(
                "n8n_trigger: failed to reach n8n at %s — %s",
                webhook_path,
                exc,
            )
        except Exception as exc:
            logger.error(
                "n8n_trigger: unexpected error for %s — %s",
                webhook_path,
                exc,
            )

    @classmethod
    async def close(cls) -> None:
        """Gracefully close the shared HTTP client (call on app shutdown)."""
        if cls._client and not cls._client.is_closed:
            await cls._client.aclose()
            cls._client = None
