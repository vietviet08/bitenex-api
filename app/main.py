import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Awaitable, Callable

import colorama
import pyfiglet
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine
from app.core.exception_handlers import register_exception_handlers
from app.modules.admin import router as admin_router

# Import routers
from app.modules.auth import router as auth_router
from app.modules.dispatch import router as dispatch_router
from app.modules.driver import router as driver_router
from app.modules.events import router as events_router
from app.modules.journey import public_router as journey_public_router
from app.modules.journey import router as journey_router
from app.modules.marketing import router as marketing_router
from app.modules.merchant import router as merchant_router
from app.modules.merchant.internal_router import internal_router as merchant_internal_router
from app.modules.notification import router as notification_router
from app.modules.notification.internal_router import internal_router as notification_internal_router
from app.modules.order import router as order_router
from app.modules.order.internal_router import internal_router as order_internal_router
from app.modules.payment import router as payment_router
from app.modules.system import router as system_router
from app.modules.user import router as user_router
from app.modules.user.internal_router import internal_router as user_internal_router
from app.modules.webhook import router as webhook_router
from app.workers import abandoned_cart_worker

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan event handler."""
    # Startup
    logger.info("Starting Bitenex API...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug mode: {settings.debug}")

    ascii_banner = pyfiglet.figlet_format(settings.app_name, font="doh", width=200)
    print(colorama.Fore.MAGENTA + ascii_banner)

    # TODO: Initialize Redis connection
    if settings.app_env != "test":
        await abandoned_cart_worker.start()
    # TODO: Run any startup checks

    yield

    # Shutdown
    logger.info("Shutting down Bitenex API...")

    # Close database connections
    if settings.app_env != "test":
        await abandoned_cart_worker.stop()
    await engine.dispose()

    # TODO: Close Redis connection

    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    description="Bitenex Food Delivery Platform API",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log incoming requests."""
    logger.debug(f"{request.method} {request.url.path}")
    response = await call_next(request)
    return response


register_exception_handlers(app, logger, settings)


API_V1_PREFIX = "/api/v1"

# System router
app.include_router(system_router)

# Core routers
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(user_router, prefix=API_V1_PREFIX)
app.include_router(driver_router, prefix=API_V1_PREFIX)
app.include_router(merchant_router, prefix=API_V1_PREFIX)
app.include_router(order_router, prefix=API_V1_PREFIX)
app.include_router(dispatch_router, prefix=API_V1_PREFIX)
app.include_router(payment_router, prefix=API_V1_PREFIX)
app.include_router(notification_router, prefix=API_V1_PREFIX)
app.include_router(journey_public_router, prefix=API_V1_PREFIX)
app.include_router(journey_router, prefix=API_V1_PREFIX)
app.include_router(admin_router, prefix=API_V1_PREFIX)

# n8n — Internal service routers
app.include_router(order_internal_router, prefix=API_V1_PREFIX)
app.include_router(notification_internal_router, prefix=API_V1_PREFIX)
app.include_router(user_internal_router, prefix=API_V1_PREFIX)
app.include_router(merchant_internal_router, prefix=API_V1_PREFIX)
app.include_router(marketing_router, prefix=API_V1_PREFIX)
app.include_router(events_router, prefix=API_V1_PREFIX)

# n8n — Inbound webhook router (HMAC-protected, no API_V1_PREFIX)
app.include_router(webhook_router, prefix=API_V1_PREFIX)

