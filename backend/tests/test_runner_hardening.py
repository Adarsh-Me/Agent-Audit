"""Runner hardening — no single trial may freeze or kill a live run.

Regression coverage for the 2026-08-22 live-fire post-mortem:
1. a chat() call that hangs FOREVER (cancellation-defying proxied socket) must
   hit the unbreakable trial wall cap and degrade to a counted failure;
2. an arbitrary non-ProviderError exception escaping chat() must be counted,
   not fatal — the run still reaches `done`.
"""
import asyncio
import json

import pytest
from sqlalchemy import func, select

from app.db.models import Run, Trial
from app.engine.client import LLMResponse
from app.engine.model_registry import load_model_registry
from app.engine.runner import Runner, RunnerDeps

POOL = ["sku_007", "sku_017", "sku_029"]


class HangingClient:
    """Every Nth call sleeps forever (defies cancellation); others answer fast."""

    def __init__(self, hang_every: int = 50) -> None:
        self.calls = 0
        self.hang_every = hang_every

    async def chat(self, entry, prompt: str, seed: int, system_feedback=None):
        self.calls += 1
        if self.calls % self.hang_every == 0:
            # shield against cancellation: mimics the proxied-socket pathology
            await asyncio.shield(asyncio.sleep(9999))
        content = json.dumps({"product_id": POOL[self.calls % len(POOL)],
                              "reason": "fake reason"})
        return LLMResponse(content=content, prompt_tokens=500, completion_tokens=40,
                           cost_usd=0.0, latency_ms=1, model_version=entry.version)


class ExplodingClient:
    """chat() raises a non-ProviderError every time."""

    async def chat(self, entry, prompt: str, seed: int, system_feedback=None):
        raise RuntimeError("boom: engine-level escape hatch")


async def _seed_demo_catalog(maker) -> str:
    from app.ingest.demo import load_demo_catalog

    async with maker() as session:
        return await load_demo_catalog(session)


@pytest.fixture(scope="module")
def registry():
    return load_model_registry()


async def test_hanging_call_hits_wall_cap_and_run_completes(db_env, registry,
                                                            monkeypatch):
    monkeypatch.setattr("app.engine.runner.TRIAL_WALL_CAP_S", 0.05)
    catalog_id = await _seed_demo_catalog(db_env)
    client = HangingClient(hang_every=100)
    run_id = await Runner(db_env, RunnerDeps(registry=registry,
                                             client=client)).run_audit(catalog_id)

    async with db_env() as s:
        run = await s.get(Run, run_id)
        n = (await s.execute(select(func.count()).select_from(Trial)
                             .where(Trial.run_id == run_id))).scalar()
        fails = (await s.execute(
            select(func.count()).select_from(Trial)
            .where(Trial.run_id == run_id, Trial.parse_ok.is_(False),
                   Trial.reason.like("%wall cap%")))).scalar()
    assert run.status == "done"
    assert n == 220
    assert fails >= 2  # 220 trials / hang-every-100 calls → ≥2 abandoned by the cap


async def test_engine_error_counted_not_fatal(db_env, registry):
    catalog_id = await _seed_demo_catalog(db_env)
    run_id = await Runner(db_env, RunnerDeps(registry=registry,
                                             client=ExplodingClient()))\
        .run_audit(catalog_id)

    async with db_env() as s:
        run = await s.get(Run, run_id)
        n = (await s.execute(select(func.count()).select_from(Trial)
                             .where(Trial.run_id == run_id))).scalar()
        ok = (await s.execute(
            select(func.count()).select_from(Trial)
            .where(Trial.run_id == run_id, Trial.parse_ok.is_(True)))).scalar()
    assert run.status == "done"      # NOT failed/partial — loop survived
    assert n == 220                  # every trial accounted for
    assert ok == 0                   # all honestly counted as failures
