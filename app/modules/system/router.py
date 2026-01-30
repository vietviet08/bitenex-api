from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

router = APIRouter()


@router.get("/", tags=["Root"])
async def root(settings: Settings = Depends(get_settings)):
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.api_version,
        "status": "running",
    }


@router.get("/health", tags=["Health"])
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.api_version,
    }


@router.get("/health/ready", tags=["Health"])
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


@router.get("/health/live", tags=["Health"])
async def liveness_check():
    """
    Liveness check endpoint.
    Indicates that the application is running.
    """
    return {"status": "alive"}
