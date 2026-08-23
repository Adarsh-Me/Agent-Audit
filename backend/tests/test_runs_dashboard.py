"""Runs dashboard tests — startup reaper + GET /api/runs outcome summaries."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_session


async def _seed_run(db, *, status="done", abort_reason=None, n_trials=6, parse_ok_all=True,
                     all_failed=False, tier="medium", n_starved=2):
    from app.db.models import Catalog, Merchant, Product, Run, Trial

    merchant = Merchant(name="femella.in")
    db.add(merchant)
    await db.flush()
    catalog = Catalog(merchant_id=merchant.id, source="upload", version=1)
    db.add(catalog)
    await db.flush()
    for i in range(1, 7):
        db.add(Product(
            catalog_id=catalog.id, sku=f"shopify-var-{i}", title=f"Item {i}",
            price_inr=999 + i, description=f"Real product {i} with a plain description here.",
            tier="starved" if i <= n_starved else tier,
            legibility_composite=0.2 if i <= n_starved else 0.6,
        ))
    run = Run(
        catalog_id=catalog.id, type="audit", status=status, models={}, seeds={},
        cost_usd=0.0, trials_total=640, abort_reason=abort_reason,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc) if status != "running" else None,
    )
    db.add(run)
    await db.flush()
    order = [f"shopify-var-{i}" for i in range(1, 7)]
    for i in range(n_trials):
        ok = False if all_failed else (parse_ok_all or i % 2 == 0)
        db.add(Trial(
            run_id=run.id, model="ox-alpha", model_version="v1", tier="bulk",
            persona_id=f"P{i % 3:02d}", condition="C1-s1", seed=42 + i,
            presented_order=order,
            choice=order[i % 6] if ok else None,
            null_allowed=True, parse_ok=ok, from_cache=False,
            prompt_hash=f"hash{i}",
        ))
    await db.commit()
    return run


# --- reaper ---

async def test_reaper_marks_orphaned_running_runs_failed(db_env, monkeypatch):
    from app.db.models import Run
    import app.main as main_mod

    async with db_env() as session:
        run = await _seed_run(session, status="running")

    monkeypatch.setattr("app.db.session.get_sessionmaker", lambda: db_env)
    await main_mod._reap_orphaned_runs()

    async with db_env() as session:
        fresh = await session.get(Run, run.id)
        assert fresh.status == "failed"
        assert fresh.abort_reason.startswith("engine_lost")
        assert fresh.completed_at is not None


async def test_reaper_untouched_terminal_runs(db_env, monkeypatch):
    from app.db.models import Run
    import app.main as main_mod

    async with db_env() as session:
        done = await _seed_run(session, status="done")

    monkeypatch.setattr("app.db.session.get_sessionmaker", lambda: db_env)
    await main_mod._reap_orphaned_runs()

    async with db_env() as session:
        fresh = await session.get(Run, done.id)
        assert fresh.status == "done" and fresh.abort_reason is None


# --- GET /api/runs ---

async def test_runs_dashboard_row(db):
    async def _ov():
        yield db

    app.dependency_overrides[get_session] = _ov
    try:
        await _seed_run(db, status="failed",
                        abort_reason="engine_lost: the server restarted mid-run")
        with TestClient(app) as client:
            r = client.get("/api/runs")
        assert r.status_code == 200, r.text
        row = r.json()["runs"][0]
        assert row["status"] == "failed"
        assert "server restarted" in row["abort_reason"]
        assert row["catalog"]["merchant"] == "femella.in"
        assert row["catalog"]["products"] == 6
        assert row["fixes_needed"] == 2  # two starved listings
        assert row["trials_recorded"] == 6
        assert row["summary"]["parse_ok"] == 6
        assert 0 <= row["summary"]["score"] <= 100
    finally:
        app.dependency_overrides.clear()


async def test_runs_dashboard_no_summary_without_parse_ok(db):
    async def _ov():
        yield db

    app.dependency_overrides[get_session] = _ov
    try:
        await _seed_run(db, status="failed", abort_reason="engine_lost: restart",
                        n_trials=4, all_failed=True)
        with TestClient(app) as client:
            r = client.get("/api/runs")
        row = r.json()["runs"][0]
        assert row["summary"] is None  # zero parse_ok trials → no mid-data summary
        assert row["trials_recorded"] == 4
    finally:
        app.dependency_overrides.clear()


def test_abort_reason_humanization():
    from app.db.models import Run
    from app.routers.runs import _human_abort_reason

    run = Run(catalog_id="x", type="audit", status="failed", models={}, seeds={})
    run.abort_reason = "circuit_breaker: retries exhausted for nvidia/nemotron: rate limited"
    text = _human_abort_reason(run)
    assert "nemotron" in text and "recorded trials" in text

    run.abort_reason = None
    assert _human_abort_reason(run) is None
