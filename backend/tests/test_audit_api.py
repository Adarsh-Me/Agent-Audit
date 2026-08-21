"""POST /api/audit regressions — found during first live fire (2026-08-22).

1. demo-default catalog resolution must actually resolve (was: un-awaited
   scalar bound a coroutine as catalog_id)
2. the background runner must ADOPT the row the API created (was: a second
   Run row got the real trials while the returned audit_id sat queued forever)
"""
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.engine.runner as runner_mod
from app.db.models import Run
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
