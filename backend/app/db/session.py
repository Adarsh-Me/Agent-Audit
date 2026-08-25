"""Async engine/session management — SQLite locally, managed Postgres in deploys.

Platform-managed Postgres (e.g. antideploy) injects a libpq-style DATABASE_URL
(``postgres://…``, often with ``?sslmode=require``) into the container. Two
incompatibilities with our stack are handled here:

1. SQLAlchemy 2.x has no ``postgres``/plain-``postgresql`` async dialect — the
   URL must be rewritten to ``postgresql+asyncpg://`` or engine creation dies.
2. libpq's ``sslmode`` query parameter is meaningless to asyncpg, which takes
   an ``ssl`` connect argument instead.

The platform also runs no migration step for us (its migrate probe finds none),
so ``init_db`` runs ``create_all`` on *every* backend, not just SQLite. And
because a public demo must never fail to boot over database plumbing, any
primary-database failure falls back to an ephemeral local SQLite file — loudly,
so the degraded mode is visible in container logs rather than silent. The
primary gets bounded retries first (release-window races: the platform swaps
containers while its managed Postgres is briefly unreachable — a single failed
connect used to strand the new container on data-loss-by-design SQLite,
wiping the imported catalogs on the 2026-08-26 deploy).
"""
import asyncio
from collections.abc import AsyncIterator
from typing import Final

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_SQLITE_FALLBACK_URL = "sqlite+aiosqlite:///./agentaudit.db"

# Bounded patience before degrading to ephemeral SQLite (see module docstring).
_PRIMARY_CONNECT_ATTEMPTS: Final = 4
_PRIMARY_RETRY_BACKOFF_S: Final = (2.0, 5.0, 10.0)


class _DbState:
    """Process-wide engine/sessionmaker holder, swappable for fallback."""

    engine: AsyncEngine | None = None
    maker: async_sessionmaker[AsyncSession] | None = None
    on_primary: bool = True


def db_status() -> dict[str, object]:
    """Ops probe — which database did this container actually land on?
    Deliberately coarse (no credentials, no hosts): enough to detect the
    ephemeral-SQLite degraded mode from the outside."""
    engine = get_engine()
    return {
        "on_primary": _DbState.on_primary,
        "driver": engine.url.drivername,
        "database": "managed-postgres"
        if engine.url.drivername.startswith("postgresql")
        else "local-sqlite",
    }


def _build_engine(url: str) -> AsyncEngine:
    u = make_url(url)
    # Force the whole Postgres family onto our one shipped async driver.
    # Platforms inject arbitrary flavors — postgres://, postgresql://,
    # postgresql+psycopg2:// (antideploy does) — and any non-asyncpg flavor
    # makes SQLAlchemy reach for a sync DBAPI we do not install, killing boot.
    if u.drivername == "postgres":
        u = u.set(drivername="postgresql")
    if u.drivername.startswith("postgresql") and u.drivername != "postgresql+asyncpg":
        u = u.set(drivername="postgresql+asyncpg")
    connect_args: dict[str, object] = {}
    if u.drivername.startswith("postgresql+asyncpg"):
        query = dict(u.query)
        sslmode = query.pop("sslmode", None)
        if sslmode is not None and str(sslmode).lower() != "disable" and "ssl" not in query:
            connect_args["ssl"] = "require"
        u = u.set(query=query)
    engine = create_async_engine(u, echo=False, connect_args=connect_args)
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


def _use(url: str) -> None:
    engine = _build_engine(url)
    _DbState.engine = engine
    _DbState.maker = async_sessionmaker(engine, expire_on_commit=False)


def get_engine() -> AsyncEngine:
    if _DbState.engine is None:
        _use(get_settings().database_url)
    return _DbState.engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _DbState.maker is None:
        get_engine()
    return _DbState.maker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    async with get_sessionmaker()() as session:
        yield session


async def init_db() -> bool:
    """Create tables on whichever database we ended up on.

    Returns True when running on the configured primary, False after falling
    back to ephemeral SQLite (caller should surface the degraded mode).
    """
    from app.db.models import Base

    last_exc: Exception | None = None
    for attempt in range(1, _PRIMARY_CONNECT_ATTEMPTS + 1):
        try:
            engine = get_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await _sqlite_column_migrations(engine)
            _DbState.on_primary = True
            if attempt > 1:
                print(f"[db] primary database recovered on attempt {attempt}")
            return True
        except Exception as exc:  # noqa: BLE001 — any primary failure → retry/fallback
            last_exc = exc
            if attempt < _PRIMARY_CONNECT_ATTEMPTS:
                delay = _PRIMARY_RETRY_BACKOFF_S[min(attempt - 1, len(_PRIMARY_RETRY_BACKOFF_S) - 1)]
                print(
                    f"[db] primary database not ready "
                    f"(attempt {attempt}/{_PRIMARY_CONNECT_ATTEMPTS}: {type(exc).__name__})"
                    f" — retrying in {delay:.0f}s"
                )
                await asyncio.sleep(delay)
    print(
        f"[db] WARNING: primary database unusable after "
        f"{_PRIMARY_CONNECT_ATTEMPTS} attempts ({type(last_exc).__name__}: {last_exc})"
        " — falling back to ephemeral SQLite"
    )
    _use(_SQLITE_FALLBACK_URL)
    _DbState.on_primary = False
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _sqlite_column_migrations(get_engine())
    return False


async def _sqlite_column_migrations(engine: AsyncEngine) -> None:
    """create_all cannot ALTER pre-existing tables — bring older DBs up to
    date column-by-column (duplicate-column errors are expected no-ops).
    Postgres databases are always freshly provisioned here, so no-op there."""
    if not engine.url.drivername.startswith("sqlite"):
        return
    from sqlalchemy import text

    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE runs ADD COLUMN abort_reason TEXT"))
        except Exception:  # noqa: BLE001 — column already exists
            pass
