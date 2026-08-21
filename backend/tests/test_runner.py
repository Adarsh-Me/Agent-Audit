"""Runner integration tests — T4.4 (mocked full run < 60 s, cost-cap partial, cache hits)."""
import json
import pathlib
import time

import pytest
from sqlalchemy import func, select

from app.db.models import Run, Trial
from app.engine.client import LLMResponse
from app.engine.runner import Runner, RunnerDeps
from app.engine.model_registry import load_model_registry

FIXTURE = (pathlib.Path(__file__).resolve().parents[2] / "demo-store" / "products.json").resolve()
POOL = ["sku_007", "sku_017", "sku_029", "sku_001"]
NULL_PLAUSIBLE = {"P04", "P09", "P10", "P20"}


class FakeClient:
    """Deterministic scripted provider: no network, no sleep, tiny cost."""

    def __init__(self, cost_per_call: float = 0.01) -> None:
        self.cost_per_call = cost_per_call
        self.calls = 0
        self.feedbacks_seen: list[str | None] = []

    async def chat(self, entry, prompt: str, seed: int, system_feedback=None):
        self.calls += 1
        self.feedbacks_seen.append(system_feedback)
        # deterministic pick from prompt hash + seed; nulls only when the prompt allows
        null_allowed = "or return" in prompt  # forced prompts omit the null clause
        h = hash((prompt[:64], seed))
        if null_allowed and h % 7 == 0:
            choice = None  # some nulls exist → coverage signal
        else:
            choice = POOL[h % len(POOL)]
        content = json.dumps({"product_id": choice, "reason": "fake reason"})
        return LLMResponse(
            content=content,
            prompt_tokens=500,
            completion_tokens=40,
            cost_usd=self.cost_per_call,
            latency_ms=1,
            model_version=entry.version,
        )


async def _seed_demo_catalog(maker) -> str:
    from app.ingest.demo import load_demo_catalog

    async with maker() as session:
        return await load_demo_catalog(session)


async def _run_status(maker, run_id: str) -> Run:
    async with maker() as session:
        return await session.get(Run, run_id)


@pytest.fixture(scope="module")
def registry():
    return load_model_registry()


async def test_full_mocked_run_640_done_under_60s(db_env, registry):
    catalog_id = await _seed_demo_catalog(db_env)
    deps = RunnerDeps(registry=registry, client=FakeClient())
    runner = Runner(db_env, deps)
    t0 = time.monotonic()
    run_id = await runner.run_audit(catalog_id)
    elapsed = time.monotonic() - t0

    assert elapsed < 60, f"mocked full run took {elapsed:.1f}s"
    run = await _run_status(db_env, run_id)
    assert run.status == "done"
    assert run.cost_usd > 0

    async with db_env() as session:
        n = (await session.execute(
            select(func.count()).select_from(Trial).where(Trial.run_id == run_id)
        )).scalar()
        tiers = (await session.execute(
            select(Trial.tier, func.count()).where(Trial.run_id == run_id).group_by(Trial.tier)
        )).all()
        forced_nulls = (await session.execute(
            select(func.count()).select_from(Trial).where(
                Trial.run_id == run_id, Trial.null_allowed.is_(False), Trial.choice.is_(None),
                Trial.parse_ok.is_(True),
            )
        )).scalar()
    assert n == 640
    assert dict(tiers) == {"bulk": 600, "flagship": 40}
    assert forced_nulls == 0  # C3 must contain zero nulls by construction


async def test_cost_cap_aborts_partial(db_env, registry):
    catalog_id = await _seed_demo_catalog(db_env)
    deps = RunnerDeps(registry=registry, client=FakeClient(cost_per_call=0.05), cost_cap_usd=1.0)
    events: list[dict] = []
    runner = Runner(db_env, deps)

    async def cb(event: dict) -> None:
        events.append(event)

    run_id = await runner.run_audit(catalog_id, progress=cb)
    run = await _run_status(db_env, run_id)
    assert run.status == "partial"
    assert any(e["type"] == "e203_cost_cap" for e in events)
    async with db_env() as session:
        n = (await session.execute(
            select(func.count()).select_from(Trial).where(Trial.run_id == run_id)
        )).scalar()
    assert n < 640  # aborted mid-matrix; never silently complete


async def test_rerun_unchanged_catalog_is_100pct_cached(db_env, registry):
    catalog_id = await _seed_demo_catalog(db_env)
    fake = FakeClient()
    runner = Runner(db_env, RunnerDeps(registry=registry, client=fake))

    run1 = await runner.run_audit(catalog_id)
    calls_after_first = fake.calls
    assert calls_after_first == 640

    events: list[dict] = []

    async def cb(event: dict) -> None:
        events.append(event)

    import time as _t
    t0 = _t.monotonic()
    run2 = await runner.run_audit(catalog_id, progress=cb)
    elapsed = _t.monotonic() - t0

    assert await _run_status(db_env, run2) is not None
    assert fake.calls == calls_after_first, "second run must not re-bill identical trials"
    assert elapsed < 60
    async with db_env() as session:
        cached = (await session.execute(
            select(func.count()).select_from(Trial).where(
                Trial.run_id == run2, Trial.from_cache.is_(True)
            )
        )).scalar()
        total = (await session.execute(
            select(func.count()).select_from(Trial).where(Trial.run_id == run2)
        )).scalar()
    assert total == 640 and cached == 640, "unchanged-catalog rerun is ~100% cache-served"
