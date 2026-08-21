"""Delta endpoint contract test — T10.1 (before/after verification)."""
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.engine.runner import Runner, RunnerDeps
from app.engine.model_registry import load_model_registry
from app.ingest.demo import load_demo_catalog
from app.remediate.fixes import build_mirror_catalog, generate_remediations
from app.main import app
from tests.test_runner import FakeClient


async def test_delta_contract(db_env):
    registry = load_model_registry()

    async with db_env() as session:
        catalog_id = await load_demo_catalog(session)
    deps = RunnerDeps(registry=registry, client=FakeClient())
    original = await Runner(db_env, deps).run_audit(catalog_id)

    async with db_env() as session:
        await generate_remediations(session, original)
        from sqlalchemy import select
        from app.db.models import Remediation
        rems = (await session.execute(
            select(Remediation).where(Remediation.run_id == original))).scalars().all()
        for r in rems:
            r.status = "approved"
        await session.commit()
        mirror_id = await build_mirror_catalog(session, original)

    # rerun with a different bias so deltas are nonzero
    class Shifted(FakeClient):
        async def chat(self, entry, prompt, seed, system_feedback=None):
            from app.engine.client import LLMResponse
            h = hash((prompt[:48], seed)) & 0xFFFF
            null_allowed = '{"product_id": null' in prompt
            choice = None if (null_allowed and h % 3 == 0) else \
                ["sku_029", "sku_029", "sku_007", "sku_001"][h % 4]
            return LLMResponse(content=f'{{"product_id": {choice!r}, "reason": "d"}}',
                               prompt_tokens=300, completion_tokens=20,
                               cost_usd=0.001, latency_ms=1, model_version=entry.version)

    rerun = await Runner(db_env, RunnerDeps(registry=registry, client=Shifted()))\
        .run_audit(mirror_id, parent_run_id=original, type_="rerun")

    async def _ov():
        async with db_env() as s:
            yield s

    app.dependency_overrides[get_session] = _ov
    try:
        with TestClient(app) as tc:
            r = tc.get(f"/api/delta/{rerun}")
            assert r.status_code == 200, r.text
            body = r.json()
            for k in ("f_task", "score", "per_sku_changes", "recoverable_inr", "verdict"):
                assert k in body, k
            d = body["f_task"]["delta"]
            assert d["ci_low"] <= d["value"] <= d["ci_high"]
            assert len(body["per_sku_changes"]) > 0

            # non-rerun run → 404 semantics
            r2 = tc.get(f"/api/delta/{original}")
            assert r2.status_code == 404
    finally:
        app.dependency_overrides.clear()
