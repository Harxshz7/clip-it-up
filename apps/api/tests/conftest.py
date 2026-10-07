import os
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Set test environment
os.environ["ENVIRONMENT"] = "development"
os.environ["DEV_AUTH_BYPASS"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_SYNC_URL"] = "sqlite:///:memory:"

import clip_shared.db.session as db_session_module
from api.main import app
from clip_shared.db.base import Base
from clip_shared.db.models import User
from clip_shared.db.session import get_db

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
db_session_module.AsyncSessionLocal = TestingSessionLocal
db_session_module.async_engine = test_engine


@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    with patch("worker.celery_app.celery_app.send_task") as _:
        yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        clerk_user_id="user_dev_bypass",
        email="dev@clipitup.local",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        clerk_user_id="user_other_dev",
        email="other@clipitup.local",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
