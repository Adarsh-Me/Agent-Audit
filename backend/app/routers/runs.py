"""Runs dashboard — GET /api/runs.

One row per recent run: outcome, why it failed/partial (persisted abort_reason),
per-model health, fixes needed, and — for runs with parse_ok trials — a
point-estimate mid-data summary (score, F_task, invisible count) computed from
recorded trials. No bootstrap here: the full CI payload lives on the report page.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Catalog, Merchant, Product, Run, Trial
from app.db.session import get_session
from app.stats.legibility import mean_completeness
from app.stats.metrics import compute_all

router = APIRouter()


def _human_abort_reason(run: Run) -> str | None:
    """Translate persisted machine reasons into what a merchant actually reads."""
    raw = getattr(run, "abort_reason", None)
    if not raw:
        return None
    if raw.startswith("engine_lost"):
        return ("The server restarted while this audit was running. Recorded trials are "
                "preserved — everything measured before the restart is shown below.")
    if raw.startswith("cost_cap"):
        return ("The $30 spend guard stopped this run to protect your budget. Recorded "
                "trials are preserved; re-run when you're ready.")
    if raw.startswith("circuit_breaker"):
        detail = raw.split(":", 1)[-1].strip()
        return (f"Model providers began failing repeatedly ({detail}). The engine stopped "
                "instead of burning budget — recorded trials are shown below.")
    if raw.startswith("engine_error"):
        return f"An internal engine error stopped this run: {raw.split(':', 1)[-1].strip()}"
    return raw


def _outcome_summary(point: dict, trials: list[dict]) -> dict:
    ok = [t for t in trials if t["parse_ok"]]
    models: dict[str, dict] = {}
    for t in trials:
        m = models.setdefault(t["model"], {"attempts": 0, "parse_ok": 0})
        m["attempts"] += 1
        if t["parse_ok"]:
            m["parse_ok"] += 1
    return {
        "score": round(point["score"], 1),
        "f_task": round(point["coverage"]["f_task"], 4),
        "top3_capture": round(point["position"]["top3_capture"], 4),
        "models": models,
        "parse_ok": len(ok),
        "note": ("point estimates over recorded trials — full confidence intervals "
                 "on the results page"),
    }


@router.get("/api/runs")
async def list_runs(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    runs = (
        (await session.execute(select(Run).order_by(Run.started_at.desc()).limit(limit)))
        .scalars()
        .all()
    )

    out: list[dict] = []
    for run in runs:
        catalog = await session.get(Catalog, run.catalog_id)
        merchant = (
            await session.get(Merchant, catalog.merchant_id) if catalog else None
        )
        product_count = catalog and (await session.execute(
            select(func.count()).select_from(Product).where(Product.catalog_id == catalog.id)
        )).scalar()

        # fixes needed = remediation-eligible listings (mirrors remediate/fixes.py flagging)
        fixes_needed = (await session.execute(
            select(func.count()).select_from(Product).where(
                Product.catalog_id == run.catalog_id,
                (Product.tier == "starved") | (Product.legibility_composite < 0.30),
            )
        )).scalar() or 0

        trials_rows = (
            (await session.execute(select(Trial).where(Trial.run_id == run.id)))
            .scalars()
            .all()
        )
        trials = [
            {
                "model": t.model, "model_version": t.model_version, "tier": t.tier,
                "persona_id": t.persona_id, "condition": t.condition,
                "presented_order": t.presented_order, "choice": t.choice,
                "null_allowed": t.null_allowed, "parse_ok": t.parse_ok,
                "from_cache": t.from_cache,
            }
            for t in trials_rows
        ]

        summary: dict | None = None
        if any(t["parse_ok"] for t in trials):
            try:
                # 2026-08-29: the dashboard score must MATCH the results page.
                # Previously compute_all ran with perms=0 and NO completeness, so
                # position_indep (from permutation) and data_completeness were
                # skipped → the dashboard showed a different score than the
                # results page. Use the same authoritative inputs now.
                completeness = await mean_completeness(session, run.catalog_id)
                point = compute_all(trials, product_count or 40,
                                    completeness=completeness, perms=10000)
                summary = _outcome_summary(point, trials)
            except Exception:  # noqa: BLE001 — dashboard never 500s on odd partials
                summary = None

        out.append({
            "run_id": run.id,
            "type": run.type,
            "status": run.status,
            "abort_reason": _human_abort_reason(run),
            "cost_usd": run.cost_usd,
            "trials_total": run.trials_total,
            "trials_recorded": len(trials),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "parent_run_id": run.parent_run_id,
            "catalog": {
                "id": run.catalog_id,
                "source": catalog.source if catalog else None,
                "merchant": merchant.name if merchant else None,
                "products": product_count,
            },
            "fixes_needed": fixes_needed,
            "summary": summary,
        })

    return {"runs": out}
