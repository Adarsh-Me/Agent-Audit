"""Audit endpoints — POST /api/audit · GET /api/audit/{id} · GET …/metrics.

The frontend never computes a headline number: every figure here carries its CI
(persona-cluster bootstrap B=2000; Wilson for F_task).
"""
from __future__ import annotations

import uuid as uuidlib
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import GMV_MIN_INR, TRIALS_PER_FULL_RUN
from app.db.models import Catalog, Metric, Product, Run, Trial
from app.db.session import get_session, get_sessionmaker
from app.engine.runner import RunnerDeps
from app.errors import AppError

router = APIRouter()


class AuditRequest(BaseModel):
    catalog_source: str = Field(pattern="^(demo|upload|mirror)$")
    catalog_id: str | None = None
    gmv_inr: int | None = None
    parent_run_id: str | None = None  # present → this is a verified re-run


async def _resolve_catalog_id(session: AsyncSession, req: AuditRequest) -> str:
    if req.catalog_id:
        return req.catalog_id
    # default: latest demo catalog
    cid = await session.scalar(
        select(Catalog.id).where(Catalog.source == "demo").order_by(Catalog.created_at.desc())
    )
    if cid is None:
        raise AppError("E601", "no catalog available — run make seed-demo", status_code=404)
    return cid


@router.post("/api/audit", status_code=202)
async def create_audit(req: AuditRequest, background: BackgroundTasks,
                       session: AsyncSession = Depends(get_session)) -> dict:
    if req.gmv_inr is not None and req.gmv_inr < GMV_MIN_INR:
        raise AppError("E110", f"enter a GMV above ₹{GMV_MIN_INR:,}")

    run_type = "audit"
    if req.parent_run_id:
        # Verified re-run gate (E401): every remediation row must be reviewed first.
        parent = await session.get(Run, req.parent_run_id)
        if parent is None:
            raise AppError("E601", "parent run not found", status_code=404)
        from sqlalchemy import select as _sel

        from app.db.models import Remediation
        pending_n = (await session.execute(
            select(func.count()).select_from(Remediation)
            .where(Remediation.run_id == req.parent_run_id,
                   Remediation.status == "pending")
        )).scalar()
        if pending_n:
            raise AppError("E401", f"{pending_n} remediation(s) pending — review before "
                                   "re-running", status_code=409)
        run_type = "rerun"
        catalog_id = req.catalog_id
        if not catalog_id:
            # latest mirror of the parent run's catalog
            catalog_id = await session.scalar(
                _sel(Catalog.id)
                .where(Catalog.source == "mirror",
                       Catalog.parent_catalog_id == parent.catalog_id)
                .order_by(Catalog.version.desc())
            )
        if not catalog_id:
            raise AppError("E401", "no mirror catalog found — approve fixes and build the "
                                   "mirror before re-running", status_code=409)
    else:
        catalog_id = await _resolve_catalog_id(session, req)

    run = Run(
        id=str(uuidlib.uuid4()),
        catalog_id=catalog_id,
        parent_run_id=req.parent_run_id,
        type=run_type,
        status="queued",
        models={}, seeds={},
        trials_total=TRIALS_PER_FULL_RUN,
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.commit()

    async def job() -> None:
        from app.engine.runner import execute_run
        from app.events import bus

        async def cb(event: dict) -> None:
            await bus.publish(run.id, event)

        # adopt the row created above so the returned audit_id IS the live run
        await execute_run(get_sessionmaker(), RunnerDeps(), catalog_id,
                          progress=cb, run_id=run.id)

    background.add_task(job)
    return {"audit_id": run.id, "status": "queued",
            "trials_total": TRIALS_PER_FULL_RUN}


@router.get("/api/audit/{run_id}")
async def get_audit(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    run = await session.get(Run, run_id)
    if run is None:
        raise AppError("E601", "run not found", status_code=404)
    done = (await session.execute(
        select(func.count()).select_from(Trial).where(Trial.run_id == run_id)
    )).scalar()

    catalog = await session.get(Catalog, run.catalog_id) if run.catalog_id else None
    merchant_name = None
    if catalog is not None and catalog.merchant_id:
        from app.db.models import Merchant

        merchant = await session.get(Merchant, catalog.merchant_id)
        merchant_name = merchant.name if merchant else None

    from app.routers.runs import _human_abort_reason

    # ETA from elapsed-average throughput (cache fast-forwards make the early
    # rate optimistic, but it converges) — the old fixed 0.35 s/trial claimed
    # "168s left" while ~75 minutes of live calls remained (ba545a33).
    eta_s = None
    if run.status == "running" and done and run.started_at is not None:
        # SQLite round-trips naive datetimes; normalize before mixing with aware now(),
        # else ETA math raises TypeError → 500 on every mid-run poll.
        started = run.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        if elapsed > 30:
            eta_s = max(0, int((run.trials_total or TRIALS_PER_FULL_RUN)
                               * (elapsed / done) - elapsed))
    return {
        "run_id": run.id,
        "status": run.status,
        "trials_done": int(done),
        "trials_total": run.trials_total,
        "cost_usd": round(run.cost_usd or 0.0, 4),
        "eta_s": eta_s,
        "parent_run_id": run.parent_run_id,
        "type": run.type,
        "merchant": merchant_name,
        "catalog_source": catalog.source if catalog else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "abort_reason": getattr(run, "abort_reason", None),
        "reason": _human_abort_reason(run),
    }


def _ci(v):  # {"value","ci_low","ci_high"} helper
    return {"value": v[0], "ci_low": v[1], "ci_high": v[2]} if isinstance(v, tuple) else v


async def compute_and_store_metrics(session: AsyncSession, run_id: str) -> dict:
    """Compute all metrics for a completed run; persist to `metrics`; return §3.5 payload."""
    run = await session.get(Run, run_id)
    if run is None:
        raise AppError("E601", "run not found", status_code=404)

    n_catalog = (await session.execute(
        select(func.count()).select_from(Product).where(Product.catalog_id == run.catalog_id)
    )).scalar()
    rows = (
        (await session.execute(select(Trial).where(Trial.run_id == run_id)))
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
        for t in rows
    ]
    from app.stats.metrics import compute_all
    from app.stats.bootstrap import cluster_bootstrap
    from app.stats.legibility import mean_completeness

    completeness = await mean_completeness(session, run.catalog_id)
    point = compute_all(trials, n_catalog or 40, completeness=completeness, perms=10000)
    boot = cluster_bootstrap(trials, n_catalog or 40, completeness=completeness)

    payload = {
        "run_id": run_id,
        "status": run.status,
        "partial": run.status == "partial",
        "trials": {
            "total": len(trials),
            "parse_ok": sum(1 for t in trials if t["parse_ok"]),
            "null_allowed": sum(1 for t in trials if t["null_allowed"]),
            "forced": sum(1 for t in trials if not t["null_allowed"]),
        },
        "hhi_norm": {**_ci((point["hhi_norm"], *boot.get("hhi_norm", (point["hhi_norm"],) * 2))),
                     "per_model": point["hhi_norm_per_model"]},
        "position": {
            "top3_capture": _ci((point["position"]["top3_capture"],
                                 *boot.get("position.top3_capture",
                                           (point["position"]["top3_capture"],) * 2))),
            "lift": point["position"]["lift"],
            "p_value": point["position"]["p_value"],
            "per_slot": point["position"]["per_slot"],
        },
        "framing": {
            "mean_delta": _ci((point["framing"]["mean_delta"],
                               *boot.get("framing.mean_delta",
                                         (point["framing"]["mean_delta"],) * 2))),
            "per_product": point["framing"]["per_product"],
        },
        "coverage": {
            "f_task": {"value": point["coverage"]["f_task"],
                       "ci_low": point["coverage"]["ci_low"],
                       "ci_high": point["coverage"]["ci_high"]},
            "nulls_by_persona": point["coverage"]["nulls_by_persona"],
        },
        "stability": {
            "matrix": point["stability"]["matrix"],
            "mean": _ci((point["stability"]["mean"], *boot.get("stability.mean",
                       (point["stability"]["mean"],) * 2))),
            "band": point["stability"]["band"],
        },
        "invisible_skus": [
            {"sku": sku.replace("share:", ""),
             "share": _ci((point["shares"].get(sku.replace("share:", ""), 0.0),
                           *boot[sku]))}
            for sku in sorted(k for k in boot if k.startswith("share:"))
            if boot[sku][1] < 1.0 / (n_catalog or 40)
        ],
        "score": {**_ci((point["score"], *boot.get("score", (point["score"],) * 2))),
                  "components": point["components"]},
        "models_meta": [
            {"id": m, "version": None, "parse_failure_rate": r}
            for m, r in sorted(point["parse_rate"].items())
        ],
        "cost_usd": round(run.cost_usd or 0.0, 4),
        "manifest_ref": None,
    }

    # persist headline rows (SCHEMA §2.4 namespace)
    headlines = {
        "hhi_norm": (payload["hhi_norm"]["value"], payload["hhi_norm"]["ci_low"], payload["hhi_norm"]["ci_high"]),
        "position.top3_capture": (payload["position"]["top3_capture"]["value"],
                                  payload["position"]["top3_capture"]["ci_low"],
                                  payload["position"]["top3_capture"]["ci_high"]),
        "position.lift": (payload["position"]["lift"], None, None),
        "position.p_value": (payload["position"]["p_value"], None, None),
        "framing.mean_delta": (payload["framing"]["mean_delta"]["value"],
                               payload["framing"]["mean_delta"]["ci_low"],
                               payload["framing"]["mean_delta"]["ci_high"]),
        "coverage.f_task": (payload["coverage"]["f_task"]["value"],
                            payload["coverage"]["f_task"]["ci_low"],
                            payload["coverage"]["f_task"]["ci_high"]),
        "stability.mean": (payload["stability"]["mean"]["value"],
                           payload["stability"]["mean"]["ci_low"],
                           payload["stability"]["mean"]["ci_high"]),
        "score": (payload["score"]["value"], payload["score"]["ci_low"], payload["score"]["ci_high"]),
    }
    for key, (v, lo, hi) in headlines.items():
        existing = await session.scalar(
            select(Metric).where(Metric.run_id == run_id, Metric.key == key)
        )
        if existing is None:
            session.add(Metric(run_id=run_id, key=key, value=v, ci_low=lo, ci_high=hi))
        else:
            existing.value, existing.ci_low, existing.ci_high = v, lo, hi
    await session.commit()
    return payload


@router.get("/api/audit/{run_id}/metrics")
async def get_metrics(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    status = (await session.get(Run, run_id))
    if status is None:
        raise AppError("E601", "run not found", status_code=404)
    if status.status in ("queued",):
        return {"run_id": run_id, "status": status.status, "partial": False}
    return await compute_and_store_metrics(session, run_id)
