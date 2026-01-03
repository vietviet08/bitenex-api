# =============================================================================
# Bitenex API - Main Application Entry Point
# =============================================================================
# FastAPI application with router mounting, lifespan events, and middleware.
# Run with: uvicorn app.main:app --reload
# =============================================================================

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import BitenexException

# Import routers
from app.modules.auth import router as auth_router
from app.modules.user import router as user_router
from app.modules.driver import router as driver_router
from app.modules.merchant import router as merchant_router
from app.modules.order import router as order_router
from app.modules.dispatch import router as dispatch_router
from app.modules.payment import router as payment_router
from app.modules.notification import router as notification_router
from app.modules.admin import router as admin_router


# =============================================================================
# Logging Configuration
# =============================================================================
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# =============================================================================
# Lifespan Events
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan event handler."""
    # Startup
    logger.info("Starting Bitenex API...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # TODO: Initialize Redis connection
    # TODO: Start background workers
    # TODO: Run any startup checks
    
    yield
    
    # Shutdown
    logger.info("Shutting down Bitenex API...")
    
    # Close database connections
    await engine.dispose()
    
    # TODO: Close Redis connection
    # TODO: Stop background workers
    
    logger.info("Shutdown complete")


# =============================================================================
# FastAPI Application
# =============================================================================
app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    description="Bitenex Food Delivery Platform API",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)


# =============================================================================
# Middleware
# =============================================================================
# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming requests."""
    logger.debug(f"{request.method} {request.url.path}")
    response = await call_next(request)
    return response


# =============================================================================
# Exception Handlers
# =============================================================================
@app.exception_handler(BitenexException)
async def bitenex_exception_handler(
    request: Request,
    exc: BitenexException,
) -> JSONResponse:
    """Handle custom application exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception("Unexpected error occurred")
    
    # Don't expose internal errors in production
    message = str(exc) if settings.debug else "An unexpected error occurred"
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": message,
        },
    )


# =============================================================================
# Router Registration
# =============================================================================
API_V1_PREFIX = "/api/v1"

# Core routers
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(user_router, prefix=API_V1_PREFIX)
app.include_router(driver_router, prefix=API_V1_PREFIX)
app.include_router(merchant_router, prefix=API_V1_PREFIX)
app.include_router(order_router, prefix=API_V1_PREFIX)
app.include_router(dispatch_router, prefix=API_V1_PREFIX)
app.include_router(payment_router, prefix=API_V1_PREFIX)
app.include_router(notification_router, prefix=API_V1_PREFIX)
app.include_router(admin_router, prefix=API_V1_PREFIX)


# =============================================================================
# Health Check Endpoints
# =============================================================================
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "name": settings.project_name,
        "version": settings.version,
        "status": "running",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.version,
    }


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness check endpoint.
    Verifies that the application is ready to accept traffic.
    """
    # TODO: Add database connectivity check
    # TODO: Add Redis connectivity check
    return {
        "status": "ready",
        "checks": {
            "database": "ok",
            "redis": "ok",
        },
    }


@app.get("/health/live", tags=["Health"])
async def liveness_check():
    """
    Liveness check endpoint.
    Indicates that the application is running.
    """
    return {"status": "alive"}
