"""Agent Evidence — verbatim LLM reasoning surfaced per product (impl plan §3.4).

Trial.reason stores each model's raw explanation for its choice or decline.
This endpoint groups those quotes by chosen SKU so the UI can show merchants
WHY agents pick (or skip) their products — real model output, not mock copy.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, Trial
from app.db.session import get_session
from app.errors import AppError

router = APIRouter()

QUOTE_MAX_CHARS = 320
QUOTES_PER_SKU = 3
DECLINE_QUOTES = 6


def _clip(text: object) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return None
    t = " ".join(text.split())
    return t[:QUOTE_MAX_CHARS] + "…" if len(t) > QUOTE_MAX_CHARS else t


@router.get("/api/evidence/{run_id}")
async def get_evidence(run_id: str,
                       session: AsyncSession = Depends(get_session)) -> dict:
    run = await session.get(Run, run_id)
    if run is None:
        raise AppError("E601", "run not found", status_code=404)

    rows = (await session.execute(
        select(Trial).where(Trial.run_id == run_id, Trial.parse_ok.is_(True))
    )).scalars().all()

    by_sku: dict[str, dict] = {}
    declines: list[dict] = []
    for t in rows:
        quote = _clip(t.reason)
        if t.choice is not None:
            entry = by_sku.setdefault(t.choice,
                                      {"sku": t.choice, "picks": 0, "quotes": []})
            entry["picks"] += 1
            if quote and len(entry["quotes"]) < QUOTES_PER_SKU:
                entry["quotes"].append({"model": t.model, "persona_id": t.persona_id,
                                        "condition": t.condition, "text": quote})
        elif quote and len(declines) < DECLINE_QUOTES:
            declines.append({"model": t.model, "persona_id": t.persona_id,
                             "condition": t.condition, "text": quote})

    products = sorted(by_sku.values(), key=lambda e: (-e["picks"], e["sku"]))
    return {"run_id": run_id, "status": run.status,
            "products": products, "declines": declines}
