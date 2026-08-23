"""Async engine/session management with SQLite fallback for local dev."""
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


@lru_cache
def get_engine():
    return create_async_engine(get_settings().database_url, echo=False)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    async with get_sessionmaker()() as session:
        yield session


async def init_db() -> None:
    """Dev convenience: create tables on SQLite. Postgres uses backend/db/init.sql."""
    engine = get_engine()
    if engine.url.drivername.startswith("sqlite"):
        from app.db.models import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # create_all cannot ALTER pre-existing tables — bring older DBs up to
        # date column-by-column (duplicate-column errors are expected no-ops)
        from sqlalchemy import text

        async with engine.begin() as conn:
            try:
                await conn.execute(text("ALTER TABLE runs ADD COLUMN abort_reason TEXT"))
            except Exception:  # noqa: BLE001 — column already exists
                pass
