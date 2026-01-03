# =============================================================================
# Async Database Configuration (SQLAlchemy 2.0)
# =============================================================================
# This module provides async database connectivity using SQLAlchemy 2.0
# with the asyncpg driver for PostgreSQL.
#
# Architectural Intent:
# - Async-first database operations for high concurrency
# - Session dependency injection pattern
# - Clean separation of engine and session management
# =============================================================================

from typing import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# =============================================================================
# Naming Convention for Constraints
# =============================================================================
# Consistent naming makes migrations and debugging easier
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# =============================================================================
# Async Engine Configuration
# =============================================================================
# Create async engine with connection pooling
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,  # Check connection health before use
    pool_size=10,
    max_overflow=20,
)


# =============================================================================
# Session Factory
# =============================================================================
# Creates new async sessions for each request
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# =============================================================================
# Declarative Base for ORM Models
# =============================================================================
class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    All models should inherit from this class.
    """
    
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# =============================================================================
# Database Session Dependency
# =============================================================================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    Automatically handles commit/rollback and session cleanup.
    
    Usage in routes:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# =============================================================================
# Database Lifecycle Functions
# =============================================================================
async def init_db() -> None:
    """
    Initialize database - create tables if they don't exist.
    In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close database connections gracefully.
    Called during application shutdown.
    """
    await engine.dispose()
