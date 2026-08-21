"""Test bootstrap — isolate env before app modules import settings."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_agentaudit.db")
os.environ.setdefault("COST_CAP_USD", "30")

import pytest  # noqa: E402


@pytest.fixture()
async def db():
    """Fresh SQLite database per test (in-memory, shared across connections)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.db.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture()
async def db_env():
    """Session factory + engine for multi-session code paths (runner)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.db.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest.fixture()
def demo_catalog_path(tmp_path):
    """Path hook for tests that need a catalog fixture."""
    return tmp_path / "catalog.json"
