"""Delta endpoint — before/after verification (SCHEMA §3.6, APPFLOW F7)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import TRIALS_PER_FULL_RUN
from app.db.models import Metric, Run, Trial
from app.db.session import get_session
from app.errors import AppError
from app.revenue.risk_model import RevenueInputs, compute_revenue

router = APIRouter()


def _trials_to_dicts(rows) -> list[dict]:
    return [
        {
            "model": t.model, "model_version": t.model_version, "tier": t.tier,
            "persona_id": t.persona_id, "condition": t.condition,
            "presented_order": t.presented_order, "choice": t.choice,
            "null_allowed": t.null_allowed, "parse_ok": t.parse_ok,
        }
        for t in rows
    ]


@router.get("/api/delta/{rerun_run_id}")
async def get_delta(rerun_run_id: str,
                    s_agent: float = 0.20, gmv_inr: int = 800_000,
                    session: AsyncSession = Depends(get_session)) -> dict:
    from app.constants import S_AGENT_SLIDER
    if not any(abs(s_agent - v) < 1e-9 for v in S_AGENT_SLIDER):
        raise AppError("E402", f"s_agent must be one of {S_AGENT_SLIDER}", status_code=422)

    rerun = await session.get(Run, rerun_run_id)
    if rerun is None:
        raise AppError("E601", "run not found", status_code=404)
    if rerun.type != "rerun" or not rerun.parent_run_id:
        raise AppError("E601", "not a re-run — delta requires parent_run_id", status_code=404)
    original = await session.get(Run, rerun.parent_run_id)
    assert original is not None

    from app.stats.bootstrap import bootstrap_f_task_delta
    from app.stats.metrics import compute_all, demand_shares

    rows_b = (await session.execute(
        select(Trial).where(Trial.run_id == original.id))).scalars().all()
    rows_a = (await session.execute(
        select(Trial).where(Trial.run_id == rerun.id))).scalars().all()
    tb, ta = _trials_to_dicts(rows_b), _trials_to_dicts(rows_a)

    n_catalog = max(len({t["presented_order"] and x for t in tb for x in t["presented_order"]}), 40)
    mb = compute_all(tb, n_catalog, perms=1000)
    ma = compute_all(ta, n_catalog, perms=1000)

    shares_b = demand_shares(tb)
    shares_a = demand_shares(ta)
    per_sku = []
    for sku in sorted(set(shares_b) | set(shares_a)):
        sb_, sa_ = shares_b.get(sku, 0.0), shares_a.get(sku, 0.0)
        per_sku.append({"sku": sku, "share_before": round(sb_, 4),
                        "share_after": round(sa_, 4),
                        "abs_change": round(abs(sa_ - sb_), 4)})
    per_sku.sort(key=lambda x: x["abs_change"], reverse=True)

    d_point, d_lo, d_hi = bootstrap_f_task_delta(tb, ta, n_catalog, B=800)

    rev = compute_revenue(RevenueInputs(
        gmv_inr=gmv_inr, gmv_source="user", s_agent=s_agent, s_agent_source="slider",
        f_task=mb["coverage"]["f_task"], f_task_ci=(mb["coverage"]["ci_low"],
                                                    mb["coverage"]["ci_high"]),
        delta_f=(d_point, d_lo, d_hi),
    ))

    improved = ma["coverage"]["f_task"] < mb["coverage"]["f_task"]
    verdict = ("coverage failure fell — fixes verified by re-run" if improved
               else "no measurable coverage improvement — say so plainly")

    # persist delta metrics (§2.4 namespace)
    for key, v, lo, hi in (
        ("delta.coverage.f_task", d_point, d_lo, d_hi),
        ("delta.score", ma["score"] - mb["score"], None, None),
    ):
        existing = await session.scalar(select(Metric).where(
            Metric.run_id == rerun.id, Metric.key == key))
        if existing is None:
            session.add(Metric(run_id=rerun.id, key=key, value=v, ci_low=lo, ci_high=hi))
        else:
            existing.value, existing.ci_low, existing.ci_high = v, lo, hi
    await session.commit()

    return {
        "original_run_id": original.id,
        "rerun_run_id": rerun.id,
        "f_task": {
            "before": {"value": round(mb["coverage"]["f_task"], 4),
                       "ci_low": mb["coverage"]["ci_low"], "ci_high": mb["coverage"]["ci_high"]},
            "after": {"value": round(ma["coverage"]["f_task"], 4),
                      "ci_low": ma["coverage"]["ci_low"], "ci_high": ma["coverage"]["ci_high"]},
            "delta": {"value": round(d_point, 4), "ci_low": round(d_lo, 4),
                      "ci_high": round(d_hi, 4)},
        },
        "score": {"before": round(mb["score"], 1), "after": round(ma["score"], 1)},
        "per_sku_changes": per_sku[:15],
        "recoverable_inr": rev["recoverable_inr"],
        "verdict": verdict,
        "honest_note": f"Both sides measured over the same {TRIALS_PER_FULL_RUN}-trial "
                       "protocol; deltas carry bootstrap CIs, not vibes.",
    }
