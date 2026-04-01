import asyncio
import logging

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.modules.journey.service import JourneyService
from app.workers.payment_worker import BaseWorker

logger = logging.getLogger(__name__)
settings = get_settings()


class AbandonedCartWorker(BaseWorker):
    """Periodic scheduler for abandoned-cart webhook dispatch."""

    def __init__(self) -> None:
        super().__init__("abandoned_cart_worker")

    async def process(self, data: dict) -> None:
        """This worker is timer-driven and does not process queue items."""
        return None

    async def _run(self) -> None:
        interval = 60
        while self._running:
            try:
                async with async_session_maker() as session:
                    service = JourneyService(session)
                    dispatched = await service.dispatch_due_abandoned_cart_webhooks()
                    await session.commit()
                    if dispatched:
                        logger.info(
                            "abandoned_cart_worker.dispatched count=%s",
                            dispatched,
                        )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("abandoned_cart_worker.failed error=%s", str(exc))

            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break


abandoned_cart_worker = AbandonedCartWorker()
