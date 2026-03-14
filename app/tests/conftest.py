# =============================================================================
# Test Configuration and Fixtures
# =============================================================================

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Provide default VNPAY settings for test runs before app imports trigger Settings().
os.environ.setdefault("VNP_TMN_CODE", "TESTTMN")
os.environ.setdefault("VNP_HASH_SECRET", "TESTHASHSECRET")
os.environ.setdefault("VNP_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
os.environ.setdefault("VNP_RETURN_URL", "bitenexuser://payment/result")
os.environ.setdefault("VNP_IPN_URL", "https://example.com/api/v1/payments/vnpay/ipn")
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "true"
os.environ.setdefault("INTERNAL_API_TOKEN", "TEST_INTERNAL_TOKEN")
os.environ.setdefault("ABANDONED_CART_N8N_WEBHOOK_URL", "https://example.com/webhook/cart-abandoned")

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with dependency overrides."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sync_client() -> Generator[TestClient, None, None]:
    """Synchronous test client for simple tests."""
    with TestClient(app) as c:
        yield c


def create_test_token(user_id: str, role: str = "USER") -> str:
    """Create a JWT token for testing."""
    return create_access_token(user_id=user_id, role=role)


def auth_header(token: str) -> dict[str, str]:
    """Create authorization header."""
    return {"Authorization": f"Bearer {token}"}
