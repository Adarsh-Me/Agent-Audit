"""Agent Evidence endpoint — verbatim trial reasons grouped by chosen SKU."""
import pytest

from app.db.models import Run, Trial
from app.errors import AppError
from app.routers.evidence import get_evidence


async def _run(session) -> Run:
    run = Run(catalog_id="cat-1", type="audit", status="done", trials_total=640,
              models={}, seeds={})
    session.add(run)
    await session.flush()          # populate run.id for trial rows
    return run


def _trial(run_id, *, choice, reason, parse_ok=True, null_allowed=False,
           model="ox-alpha", persona="P01", condition="C1-s1"):
    return Trial(run_id=run_id, model=model, model_version="v", tier="bulk",
                 persona_id=persona, condition=condition, seed=1,
                 presented_order=[], choice=choice, reason=reason,
                 latency_ms=10, prompt_hash=f"h-{choice}-{persona}-{condition}",
                 from_cache=False, null_allowed=null_allowed, parse_ok=parse_ok)


async def test_quotes_grouped_by_chosen_sku(db):
    run = await _run(db)
    db.add_all([
        _trial(run.id, choice="sku_a", reason="  price was  clearly  stated  "),
        _trial(run.id, choice="sku_a", reason="best match for budget",
               model="nemotron-flash", persona="P02"),
        _trial(run.id, choice="sku_b", reason=None),
    ])
    await db.commit()
    out = await get_evidence(run.id, session=db)
    assert [p["sku"] for p in out["products"]] == ["sku_a", "sku_b"]  # picks desc
    assert out["products"][0]["picks"] == 2
    assert len(out["products"][0]["quotes"]) == 2
    assert out["products"][0]["quotes"][0]["text"] == "price was clearly stated"
    assert out["products"][1]["picks"] == 1
    assert out["products"][1]["quotes"] == []          # no reason → no quote
    assert out["declines"] == []


async def test_declines_collected_and_parse_failures_excluded(db):
    run = await _run(db)
    db.add_all([
        _trial(run.id, choice=None, reason="no option matched the occasion",
               null_allowed=True),
        _trial(run.id, choice=None, reason="budget mismatch", null_allowed=True,
               persona="P03"),
        _trial(run.id, choice=None, reason="garbled", parse_ok=False),   # excluded
        _trial(run.id, choice=None, reason=None, null_allowed=True),      # no quote
    ])
    await db.commit()
    out = await get_evidence(run.id, session=db)
    assert len(out["declines"]) == 2
    assert {d["text"] for d in out["declines"]} == {
        "no option matched the occasion", "budget mismatch"}


async def test_long_reason_clipped_and_quote_cap_enforced(db):
    run = await _run(db)
    long_reason = "x" * 500
    db.add_all([_trial(run.id, choice="sku_a", reason=long_reason,
                       persona=f"P0{i}", condition=f"C1-s{i}")
                for i in range(1, 6)])
    await db.commit()
    out = await get_evidence(run.id, session=db)
    entry = out["products"][0]
    assert entry["picks"] == 5
    assert len(entry["quotes"]) == 3                       # QUOTES_PER_SKU cap
    assert all(len(q["text"]) <= 321 for q in entry["quotes"])  # clip + ellipsis


async def test_unknown_run_raises_601(db):
    with pytest.raises(AppError) as ei:
        await get_evidence("nope", session=db)
    assert ei.value.code == "E601"
