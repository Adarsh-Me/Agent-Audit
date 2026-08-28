"""Report endpoints — legibility pass · full report · revenue model."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Catalog, Product, Run
from app.db.session import get_session
from app.errors import AppError
from app.revenue.risk_model import RevenueInputs, compute_revenue, validate_slider
from app.routers.audit import compute_and_store_metrics
from app.stats.legibility import score_catalog_and_persist

router = APIRouter()


class LegibilityResponse(BaseModel):
    catalog_id: str
    products: list[dict]


@router.post("/api/legibility/{catalog_id}")
async def run_legibility(catalog_id: str,
                         session: AsyncSession = Depends(get_session)) -> dict:
    cat = await session.get(Catalog, catalog_id)
    if cat is None:
        raise AppError("E601", "catalog not found", status_code=404)
    products = await score_catalog_and_persist(session, catalog_id)
    return {"catalog_id": catalog_id, "products": products}


async def _load_run(session: AsyncSession, run_id: str) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise AppError("E601", "run not found", status_code=404)
    return run


@router.get("/api/report/{run_id}")
async def get_report(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    run = await _load_run(session, run_id)
    if run.status in ("queued",):
        return {"run_id": run_id, "status": run.status}
    metrics = await compute_and_store_metrics(session, run_id)

    # revenue preview at demo-default GMV and default slider (labeled as such)
    f = metrics["coverage"]["f_task"]
    rev = compute_revenue(RevenueInputs(
        gmv_inr=800_000, gmv_source="demo-default", s_agent=0.20, s_agent_source="slider",
        f_task=f["value"], f_task_ci=(f["ci_low"], f["ci_high"]),
        usable_trials=f.get("usable_trials"),
    ))

    products = (
        (await session.execute(
            select(Product.sku, Product.title, Product.tier, Product.legibility_composite)
            .where(Product.catalog_id == run.catalog_id).order_by(Product.sku)
        ))
        .all()
    )
    return {
        **metrics,
        "revenue_preview": rev,
        "legibility": [
            {"sku": p.sku, "title": p.title, "tier": p.tier,
             "composite": p.legibility_composite}
            for p in products
        ],
    }


@router.get("/api/revenue/{run_id}")
async def get_revenue(run_id: str,
                      s_agent: float = Query(default=0.20),
                      gmv_inr: int | None = Query(default=None),
                      delta_run_id: str | None = Query(default=None),
                      session: AsyncSession = Depends(get_session)) -> dict:
    run = await _load_run(session, run_id)
    try:
        s_agent = validate_slider(s_agent)
    except ValueError as exc:
        raise AppError("E402", str(exc), status_code=422) from exc

    metrics = await compute_and_store_metrics(session, run_id)
    f = metrics["coverage"]["f_task"]

    delta_f = None
    if delta_run_id:
        from sqlalchemy import select as sel

        from app.db.models import Metric
        row = await session.scalar(sel(Metric.value).where(
            Metric.run_id == delta_run_id, Metric.key == "delta.coverage.f_task"))
        if row is not None:
            dlo = await session.scalar(sel(Metric.ci_low).where(
                Metric.run_id == delta_run_id, Metric.key == "delta.coverage.f_task"))
            dhi = await session.scalar(sel(Metric.ci_high).where(
                Metric.run_id == delta_run_id, Metric.key == "delta.coverage.f_task"))
            delta_f = (float(row), float(dlo or 0.0), float(dhi or 0.0))

    gmv_source = "user" if gmv_inr is not None else "demo-default"
    rev = compute_revenue(RevenueInputs(
        gmv_inr=gmv_inr or 800_000, gmv_source=gmv_source, s_agent=s_agent,
        s_agent_source="slider", f_task=f["value"], f_task_ci=(f["ci_low"], f["ci_high"]),
        delta_f=delta_f, usable_trials=f.get("usable_trials"),
    ))
    return {"run_id": run_id, "status": run.status, **rev}
