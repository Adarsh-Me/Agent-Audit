"""POST /api/audit regressions — found during first live fire (2026-08-22).

1. demo-default catalog resolution must actually resolve (was: un-awaited
   scalar bound a coroutine as catalog_id)
2. the background runner must ADOPT the row the API created (was: a second
   Run row got the real trials while the returned audit_id sat queued forever)

GET /api/audit/{id} regression — found during second live fire (2026-08-24):

3. mid-run polls must survive the ETA branch: SQLite round-trips started_at
   as a naive datetime, and subtracting it from aware utcnow() raised
   TypeError → 500 on every poll of a running run
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.engine.runner as runner_mod
from app.db.models import Run, Trial
from app.db.session import get_session
from app.ingest.demo import load_demo_catalog
from app.main import app


async def test_post_audit_resolves_demo_and_adopts_row(db_env, monkeypatch):
    async with db_env() as session:
        catalog_id = await load_demo_catalog(session)

    captured: dict = {}

    async def fake_execute_run(_session_factory, deps, cid, **kw):
        # mirror the real contract: adopt the existing row + stamp the snapshot.
        # use the FIXTURE maker — the passed-in factory binds the prod engine,
        # whereas in production both point at the same database.
        async with db_env() as s:
            row = await s.get(Run, kw["run_id"])
            assert row is not None
            row.catalog_id = cid
            row.models = deps.registry.snapshot()
            await s.commit()
        captured["catalog_id"] = cid
        captured["run_id"] = kw.get("run_id")
        return kw.get("run_id")

    monkeypatch.setattr(runner_mod, "execute_run", fake_execute_run)

    async def _ov():
        async with db_env() as s:
            yield s

    app.dependency_overrides[get_session] = _ov
    try:
        with TestClient(app) as tc:
            r = tc.post("/api/audit", json={"catalog_source": "demo"})
            assert r.status_code == 202, r.text
            body = r.json()
            assert body["status"] == "queued" and body["trials_total"] == 640

            # resolved the demo default AND adopted the API-created row
            assert captured["catalog_id"] == catalog_id
            assert captured["run_id"] == body["audit_id"]

            # exactly one Run row exists, carrying the real registry snapshot
            async with db_env() as s:
                n = (await s.execute(select(func.count()).select_from(Run))).scalar()
                assert n == 1
                row = await s.get(Run, body["audit_id"])
                assert row is not None
                assert set(row.models.keys()) == {"bulk", "flagship"}
                assert len(row.models["bulk"]) == 3
                assert len(row.models["flagship"]) == 2
    finally:
        app.dependency_overrides.clear()


async def test_post_audit_unknown_catalog_source_rejected(db_env):
    async def _ov():
        async with db_env() as s:
            yield s

    app.dependency_overrides[get_session] = _ov
    try:
        with TestClient(app) as tc:
            r = tc.post("/api/audit", json={"catalog_source": "scraped"})
            assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_get_audit_running_run_eta_survives_naive_started_at(db_env):
    """Regression #3: a running run with ≥1 trial takes the ETA branch; the
    naive started_at that SQLite hands back must not blow up against aware
    utcnow (was: HTTP 500 on every mid-run poll)."""
    async with db_env() as session:
        cid = await load_demo_catalog(session)
        run = Run(
            id=str(uuid4()), catalog_id=cid, type="audit", status="running",
            models={}, seeds={}, trials_total=640,
            # deliberately naive — mirrors what SQLite returns on read-back
            started_at=(datetime.now(timezone.utc) - timedelta(seconds=90)).replace(tzinfo=None),
        )
        session.add(run)
        session.add(Trial(
            run_id=run.id, model="ox-alpha", model_version="test-snap", tier="bulk",
            persona_id="P1", condition="control", seed=1, presented_order=["sku_001"],
            choice="sku_001", prompt_hash="h", null_allowed=False, parse_ok=True,
        ))
        await session.commit()
        rid = run.id

    async def _ov():
        async with db_env() as s:
            yield s

    app.dependency_overrides[get_session] = _ov
    try:
        with TestClient(app) as tc:
            r = tc.get(f"/api/audit/{rid}")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "running" and body["trials_done"] == 1
            # elapsed 90s > 30s floor → ETA must actually be computed, not skipped
            assert body["eta_s"] is not None and body["eta_s"] >= 0
    finally:
        app.dependency_overrides.clear()
