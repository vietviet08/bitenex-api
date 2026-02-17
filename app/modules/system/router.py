from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import hash_password

router = APIRouter()


@router.get("/", tags=["Root"])
async def root(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.api_version,
        "status": "running",
    }


@router.get("/pwd/{password}", tags=["Password"])
async def password(password: str) -> dict[str, str]:
    """Password generator endpoint."""
    return {
        "password": hash_password(password),
    }


@router.get("/health", tags=["Health"])
async def health_check(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.api_version,
    }


@router.get("/health/ready", tags=["Health"])
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str | dict[str, str]]:
    """
    Readiness check endpoint.
    Verifies that the application is ready to accept traffic.
    """
    database_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    # TODO: Add Redis connectivity checkRedis
    is_ready = database_status == "ok"
    return {
        "status": "ready" if is_ready else "not_ready",
        "checks": {
            "database": database_status,
            "redis": "ok",
        },
    }


@router.get("/health/live", tags=["Health"])
async def liveness_check() -> dict[str, str]:
    """
    Liveness check endpoint.
    Indicates that the application is running.
    """
    return {"status": "alive"}
