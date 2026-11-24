"""Async SQLAlchemy database configuration using aiomysql.

Provides AsyncSession factory, engine, DeclarativeBase, and FastAPI get_db dependency.
"""

from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(AsyncAttrs, DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""

    pass


# Create asynchronous engine with connection pooling and health checks
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an active async database session.

    Commits on successful completion or rolls back if an exception occurs.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all database tables on application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Sync engine and session factory for background workers and sync operations
_sync_engine = None
_SyncSessionLocal = None


def get_sync_engine():
    """Create or return the sync SQLAlchemy database engine."""
    global _sync_engine
    if _sync_engine is None:
        sync_url = settings.DATABASE_URL_SYNC
        if not sync_url or "aiomysql" in sync_url:
            sync_url = settings.DATABASE_URL.replace("mysql+aiomysql://", "mysql+pymysql://")
        if "sqlite+aiosqlite:" in sync_url:
            sync_url = sync_url.replace("sqlite+aiosqlite:", "sqlite:")

        _sync_engine = create_engine(
            sync_url,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _sync_engine


def get_sync_sessionmaker() -> sessionmaker[Session]:
    """Return the sessionmaker bound to the sync engine."""
    global _SyncSessionLocal
    if _SyncSessionLocal is None:
        engine = get_sync_engine()
        _SyncSessionLocal = sessionmaker(
            bind=engine,
            class_=Session,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _SyncSessionLocal


@contextmanager
def get_sync_db() -> Generator[Session, None, None]:
    """Context manager yielding a synchronous database session with auto commit/rollback."""
    session_factory = get_sync_sessionmaker()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def SyncSessionLocal() -> Session:
    """Convenience callable returning a new sync database session."""
    return get_sync_sessionmaker()()


async def close_db() -> None:
    """Dispose of the database engines on application shutdown."""
    global _sync_engine
    await engine.dispose()
    if _sync_engine is not None:
        _sync_engine.dispose()
