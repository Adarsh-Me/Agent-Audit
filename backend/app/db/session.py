"""Async engine/session management with SQLite fallback for local dev."""
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


@lru_cache
def get_engine():
    engine = create_async_engine(get_settings().database_url, echo=False)
    if engine.url.drivername.startswith("sqlite"):
        # WAL + a generous busy timeout: the DB lives under OneDrive-synced
        # Desktop where sync-agent file locks cause transient SQLITE_BUSY on
        # writes (ba545a33 post-mortem). Default rollback journal + 0s handler
        # turns any concurrent reader/sync touch into a failed commit.
        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=15000")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()
    return engine


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
