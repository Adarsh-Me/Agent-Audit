"""SSE stream smoke — complete-runs emit terminal event immediately."""
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app
from app.engine.runner import RunnerDeps, Runner
from app.engine.model_registry import load_model_registry
from app.ingest.demo import load_demo_catalog
from tests.test_runner import FakeClient


async def test_stream_emits_complete_for_finished_run(db_env):
    from fastapi.responses import StreamingResponse  # noqa: F401

    async with db_env() as session:
        catalog_id = await load_demo_catalog(session)
    run_id = await Runner(db_env, RunnerDeps(registry=load_model_registry(),
                                             client=FakeClient())).run_audit(catalog_id)

    async def _ov():
        async with db_env() as s:
            yield s

    app.dependency_overrides[get_session] = _ov
    # stream endpoint uses global sessionmaker; point settings at nothing special —
    # instead patch get_sessionmaker indirectly via DATABASE_URL is overkill here.
    try:
        from unittest.mock import patch

        from app.routers import stream as stream_mod

        def fake_maker():
            return db_env

        with patch.object(stream_mod, "get_sessionmaker", fake_maker):
            with TestClient(app) as tc:
                with tc.stream("GET", f"/api/stream/{run_id}") as r:
                    body = "".join(chunk for chunk in r.iter_text())
        assert "event: complete" in body
        assert '"status": "done"' in body.replace("'", '"') or "done" in body
    finally:
        app.dependency_overrides.clear()
