"""Response cache — identical trials are never re-billed (FR-16).

Key: (prompt_hash, model_version). A re-run against an UNCHANGED catalog is ~100%
cache-served (< 60 s, $0 marginal). A remediated re-run changes every listing line,
so it is a full fresh full-matrix run (SCHEMA SC-3) — budgeted and timed as such.

2026-08-29 LIVE-FIRE FIX: cache_put used the SQLite-dialect insert on EVERY
backend — on the platform's Postgres the statement fails to compile
('OnConflictDoNothing' has no attribute 'constraint_target'), the exception
escaped into the runner's engine-error hatch, and EVERY successful LLM call
(billed!) was recorded as parse_ok=false with latency 0. That is the root
cause of every 0/N usable-answer run since the Postgres deploys. The upsert
is now dialect-aware; both dialects compile (regression-tested).
"""
from __future__ import annotations

import json

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import ResponseCache
from app.db.session import get_engine


def _on_conflict_insert(prompt_hash: str, model_version: str, response: dict,
                        dialect_name: str | None = None):
    """Dialect-aware INSERT … ON CONFLICT DO NOTHING for the response cache.

    dialect_name defaults to the process engine's dialect; tests inject
    "postgresql"/"sqlite" explicitly to compile-verify both."""
    values = dict(prompt_hash=prompt_hash, model_version=model_version, response=response)
    name = dialect_name or get_engine().dialect.name
    if name == "postgresql":
        stmt = pg_insert(ResponseCache).values(**values)
    else:
        stmt = sqlite_insert(ResponseCache).values(**values)
    return stmt.on_conflict_do_nothing()


async def cache_get(session: AsyncSession, prompt_hash: str, model_version: str) -> dict | None:
    row = await session.get(ResponseCache, {"prompt_hash": prompt_hash, "model_version": model_version})
    return row.response if row else None


async def cache_put(session: AsyncSession, prompt_hash: str, model_version: str,
                    response: dict) -> None:
    stmt = _on_conflict_insert(prompt_hash, model_version, response)
    await session.execute(stmt)


def encode_response(choice: str | None, reason: str | None, raw: str) -> str:
    return json.dumps({"product_id": choice, "reason": reason, "raw": raw})
