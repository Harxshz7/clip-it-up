from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from clip_shared.config import get_settings

settings = get_settings()

# Async Engine (FastAPI)
async_engine_kwargs = {"echo": False, "future": True}
if "sqlite" not in settings.DATABASE_URL:
    async_engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    async_engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

try:
    async_engine = create_async_engine(
        settings.DATABASE_URL,
        **async_engine_kwargs,
    )
except Exception:
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync Engine (Celery Worker / Alembic)
sync_engine_kwargs = {"echo": False, "pool_pre_ping": True}
if "sqlite" not in settings.DATABASE_SYNC_URL:
    sync_engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    sync_engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

try:
    sync_engine = create_engine(
        settings.DATABASE_SYNC_URL,
        **sync_engine_kwargs,
    )
except Exception:
    sync_engine = create_engine("sqlite:///:memory:")

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@contextmanager
def get_sync_db() -> Generator[Session, None, None]:
    """Context manager for synchronous database sessions (used in Celery tasks)."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
