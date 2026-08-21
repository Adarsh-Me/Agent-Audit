"""Audit metrics endpoint contract — T6.6 (SCHEMA §3.5 shape, CIs present)."""
import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.engine.client import LLMResponse
from app.engine.model_registry import load_model_registry
from app.ingest.demo import load_demo_catalog

POOL = ["sku_007", "sku_017", "sku_029", "sku_001"]


class SkewClient:

    async def chat(self, entry, prompt: str, seed: int, system_feedback=None):
        null_allowed = '{"product_id": null' in prompt
        h = (hash((prompt[:48], seed)) & 0xFFFF)
        if null_allowed and h % 9 == 0:
            choice = None
        else:
            # bias toward sku_007 to create concentration + stability
            idx = 0 if h % 3 else h % len(POOL)
            choice = POOL[idx]
        content = f'{{"product_id": {choice!r}, "reason": "contract test"}}'
        return LLMResponse(content=content, prompt_tokens=400, completion_tokens=30,
                           cost_usd=0.001, latency_ms=2, model_version=entry.version)


async def test_metrics_contract(db_env, monkeypatch):
    from app.engine.runner import RunnerDeps
    from app.engine.runner import Runner

    async with db_env() as session:
        catalog_id = await load_demo_catalog(session)
    deps = RunnerDeps(registry=load_model_registry(), client=SkewClient())
    run_id = await Runner(db_env, deps).run_audit(catalog_id)

    async def _ov():
        async with db_env() as s:
            yield s

    from app.main import app
    app.dependency_overrides[get_session] = _ov
    try:
        with TestClient(app) as tc:
            r = tc.get(f"/api/audit/{run_id}")
            assert r.status_code == 200 and r.json()["status"] == "done"

            r = tc.get(f"/api/audit/{run_id}/metrics")
            assert r.status_code == 200, r.text
            body = r.json()
            for key in ("hhi_norm", "position", "framing", "coverage", "stability",
                        "invisible_skus", "score"):
                assert key in body, key
            for k in ("hhi_norm", "framing", "stability", "score", "coverage"):
                node = body[k]
                if k == "coverage":
                    node = node["f_task"]
                elif k == "framing":
                    node = node["mean_delta"]
                elif k == "stability":
                    node = node["mean"]
                assert "value" in node and "ci_low" in node and "ci_high" in node, k
                assert node["ci_low"] <= node["value"] <= node["ci_high"]
            assert body["trials"]["total"] == 640
            assert body["score"]["value"] == pytest.approx(
                100 * sum(v for v in body["score"]["components"].values()) / 5, rel=1e-6
            )
            assert len(body["invisible_skus"]) > 0 or body["hhi_norm"]["value"] < 0.5

            # persisted rows exist in metrics table
            from sqlalchemy import select, func as sfunc
            from app.db.models import Metric
            async with db_env() as s2:
                n = (await s2.execute(
                    select(sfunc.count()).select_from(Metric).where(Metric.run_id == run_id)
                )).scalar()
            assert n >= 8
    finally:
        app.dependency_overrides.clear()
