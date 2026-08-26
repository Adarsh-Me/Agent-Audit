"""Response cache — identical trials are never re-billed (FR-16).

Key: (prompt_hash, model_version). A re-run against an UNCHANGED catalog is ~100%
cache-served (< 60 s, $0 marginal). A remediated re-run changes every listing line,
so it is a full fresh full-matrix run (SCHEMA SC-3) — budgeted and timed as such.
"""
from __future__ import annotations

import json

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ResponseCache


async def cache_get(session: AsyncSession, prompt_hash: str, model_version: str) -> dict | None:
    row = await session.get(ResponseCache, {"prompt_hash": prompt_hash, "model_version": model_version})
    return row.response if row else None


async def cache_put(session: AsyncSession, prompt_hash: str, model_version: str,
                    response: dict) -> None:
    stmt = sqlite_insert(ResponseCache).values(
        prompt_hash=prompt_hash, model_version=model_version, response=response
    )
    stmt = stmt.on_conflict_do_nothing()
    await session.execute(stmt)


def encode_response(choice: str | None, reason: str | None, raw: str) -> str:
    return json.dumps({"product_id": choice, "reason": reason, "raw": raw})
