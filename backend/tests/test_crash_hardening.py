"""Crash hardening — regression coverage for the ba545a33 post-mortem (2026-08-23).

Run ba545a33 died when (1) parse.py accepted "product_id": null as a VALID parse
inside a forced-choice condition, poisoning the batch and the response cache, and
(2) the semantics guard lived only in the commit except-block, so an unrelated
SQLite write failure was misreported as a choice-semantics AssertionError.
These tests pin both layers shut.
"""
import json

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from app.constants import (FLAGSHIP_MODEL_COUNT, FORCED_TRIALS, NULL_ALLOWED_TRIALS,
                           PARSE_RETRIES, PERSONA_COUNT)
from app.db.models import Run, Trial
from app.engine.cache import cache_put
from app.engine.client import CostLedger, LLMResponse
from app.engine.conditions import TrialSpec
from app.engine.model_registry import load_model_registry
from app.engine.runner import Runner, RunnerDeps, _assert_batch_semantics
from app.engine.parse import parse_response

POOL = ["sku_007", "sku_017", "sku_029"]


class PickClient:
    """Always answers with a valid catalog pick."""

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, entry, prompt: str, seed: int, system_feedback=None):
        self.calls += 1
        return LLMResponse(
            content=json.dumps({"product_id": POOL[self.calls % len(POOL)],
                                "reason": "fake reason"}),
            prompt_tokens=500, completion_tokens=40,
            cost_usd=0.0, latency_ms=1, model_version=entry.version)


class NullDeclinerClient:
    """Always declines — the exact behavior that killed run ba545a33 in a
    forced-choice condition."""

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, entry, prompt: str, seed: int, system_feedback=None):
        self.calls += 1
        return LLMResponse(content=json.dumps({"product_id": None}),
                           prompt_tokens=500, completion_tokens=40,
                           cost_usd=0.0, latency_ms=1, model_version=entry.version)


async def _seed_demo_catalog(maker) -> str:
    from app.ingest.demo import load_demo_catalog

    async with maker() as session:
        return await load_demo_catalog(session)


@pytest.fixture(scope="module")
def registry():
    return load_model_registry()


# ---------------------------------------------------------------- parse layer

def test_forced_condition_null_is_parse_failure():
    parsed = parse_response('{"product_id": null, "reason": "none fit"}',
                            set(POOL), null_allowed=False)
    assert parsed.parse_ok is False
    assert parsed.choice is None
    assert "forced" in (parsed.error or "")


def test_null_allowed_condition_null_stays_valid():
    parsed = parse_response('{"product_id": null, "reason": "nothing fits"}',
                            set(POOL), null_allowed=True)
    assert parsed.parse_ok is True
    assert parsed.choice is None


def test_forced_null_salvage_path_also_fails():
    # malformed JSON but salvageable product_id field → same forced rule applies
    raw = 'oops not json at all "product_id": null'
    parsed = parse_response(raw, set(POOL), null_allowed=False)
    assert parsed.parse_ok is False


# ------------------------------------------------------------ runner: retries

async def test_declining_model_survives_full_run_with_honest_failures(
        db_env, registry):
    """Forced-choice declines must exhaust PARSE_RETRIES then count as failures —
    never poison a batch; null-allowed declines stay valid picks-of-nothing."""
    catalog_id = await _seed_demo_catalog(db_env)
    client = NullDeclinerClient()
    progress: list[dict] = []

    async def cb(ev: dict) -> None:
        progress.append(ev)

    run_id = await Runner(db_env, RunnerDeps(registry=registry, client=client))\
        .run_audit(catalog_id, progress=cb)

    async with db_env() as s:
        run = await s.get(Run, run_id)
        forced_bad = (await s.execute(
            select(func.count()).select_from(Trial)
            .where(Trial.run_id == run_id, Trial.condition.like("C3%"),
                   Trial.parse_ok.is_(False)))).scalar()
        forced_total = (await s.execute(
            select(func.count()).select_from(Trial)
            .where(Trial.run_id == run_id, Trial.condition.like("C3%")))).scalar()
        allowed_null = (await s.execute(
            select(func.count()).select_from(Trial)
            .where(Trial.run_id == run_id, ~Trial.condition.like("C3%"),
                   Trial.parse_ok.is_(True), Trial.choice.is_(None)))).scalar()
        allowed_total = (await s.execute(
            select(func.count()).select_from(Trial)
            .where(Trial.run_id == run_id, ~Trial.condition.like("C3%")))).scalar()
    assert run.status == "done"
    assert forced_bad == forced_total > 0      # all forced declines counted failed
    assert allowed_null == allowed_total       # null-allowed declines stay valid
    flagship_trials = FLAGSHIP_MODEL_COUNT * PERSONA_COUNT
    expected_calls = (FORCED_TRIALS * PARSE_RETRIES          # forced retried ×PARSE_RETRIES
                      + (NULL_ALLOWED_TRIALS - flagship_trials)  # null-allowed bulk once
                      + flagship_trials)                     # null-allowed + flagships once
    assert client.calls == expected_calls


async def test_progress_flushes_at_least_every_20_trials(db_env, registry):
    """Dashboard counter must move smoothly: flush cadence ≤ FLUSH_TRIALS."""
    catalog_id = await _seed_demo_catalog(db_env)
    progress: list[dict] = []

    async def cb(ev: dict) -> None:
        progress.append(ev)

    await Runner(db_env, RunnerDeps(registry=registry, client=PickClient()))\
        .run_audit(catalog_id, progress=cb)

    ticks = [p for p in progress if p.get("type") == "progress"]
    assert len(ticks) >= 220 // 20             # ≥ one tick per 20 trials
    assert ticks[-1]["done"] == 220


# --------------------------------------------------- cache-replay guard

async def _execute_via_cache(db_env, registry, *, null_allowed: bool):
    """Seed a poisoned cache row (decline), then execute ONE trial against it."""
    spec = TrialSpec(model="xpreview", model_version=registry.by_id("xpreview").version,
                     tier="bulk", persona_id="P01",
                     condition="C3-B-s1" if not null_allowed else "C1-s1",
                     seed=7, null_allowed=null_allowed)
    phash = f"poisoned-{null_allowed}"
    async with db_env() as s:
        await cache_put(s, phash, spec.model_version,
                        {"product_id": None, "reason": "stale decline", "raw": "{}"})
        await s.commit()
    runner = Runner(db_env, RunnerDeps(registry=registry, client=PickClient()))

    async def emit(_ev: dict) -> None:
        pass

    outcome = await runner._execute_trial(spec, "prompt", phash, set(POOL),
                                          CostLedger(cap_usd=5.0), emit)
    return outcome, runner.deps.client


async def test_poisoned_cache_decline_ignored_under_forced_condition(
        db_env, registry):
    outcome, client = await _execute_via_cache(db_env, registry, null_allowed=False)
    assert outcome.from_cache is False          # live path taken
    assert outcome.choice in POOL               # real pick recorded
    assert client.calls == 1


async def test_cached_decline_still_valid_when_null_allowed(db_env, registry):
    outcome, client = await _execute_via_cache(db_env, registry, null_allowed=True)
    assert outcome.from_cache is True
    assert outcome.choice is None
    assert client.calls == 0                    # replayed without a live call


# --------------------------------------------- persistence error propagation

class _FlakyMaker:
    """Session factory whose Trial-batch commits fail (first N attempts or always)."""

    def __init__(self, maker, *, fail_first: int = 0, forever: bool = False) -> None:
        self._maker = maker
        self.fail_first = fail_first
        self.forever = forever

    def __call__(self):
        session = self._maker()
        orig_commit = session.commit

        async def commit():
            if any(isinstance(o, Trial) for o in session.new) and (
                    self.forever or self.fail_first > 0):
                if not self.forever:
                    self.fail_first -= 1
                raise OperationalError("INSERT failed", {},
                                       Exception("database is locked"))
            await orig_commit()

        session.commit = commit  # type: ignore[method-assign]
        return session


async def test_transient_commit_failure_retried_run_completes(db_env, registry,
                                                              monkeypatch):
    monkeypatch.setattr("app.engine.runner.COMMIT_RETRY_DELAYS", (0.01, 0.02))
    catalog_id = await _seed_demo_catalog(db_env)
    run_id = await Runner(_FlakyMaker(db_env, fail_first=1),
                          RunnerDeps(registry=registry, client=PickClient()))\
        .run_audit(catalog_id)

    async with db_env() as s:
        run = await s.get(Run, run_id)
        n = (await s.execute(select(func.count()).select_from(Trial)
                             .where(Trial.run_id == run_id))).scalar()
    assert run.status == "done"
    assert n == 220                              # no trials lost to the retry


async def test_persistent_commit_failure_keeps_real_error_identity(
        db_env, registry):
    """The old code masked ANY commit failure as 'choice-semantics violation'.
    The abort reason must now carry the original database error instead."""
    catalog_id = await _seed_demo_catalog(db_env)
    run_id = await Runner(_FlakyMaker(db_env, forever=True),
                          RunnerDeps(registry=registry, client=PickClient()))\
        .run_audit(catalog_id)

    async with db_env() as s:
        run = await s.get(Run, run_id)
    assert run.status == "failed"
    assert run.abort_reason is not None
    assert "OperationalError" in run.abort_reason
    assert "database is locked" in run.abort_reason
    assert "choice-semantics" not in run.abort_reason


def test_semantics_gate_raises_outside_error_handlers():

    bad = Trial(run_id="r", model="m", model_version="v", tier="bulk",
                persona_id="P12", condition="C3-B-s1", seed=1,
                presented_order=[], choice=None, reason="x", latency_ms=1,
                prompt_hash="h", from_cache=False, null_allowed=False,
                parse_ok=True)
    with pytest.raises(AssertionError, match="choice-semantics"):
        _assert_batch_semantics([bad])


# ------------------------------------------------------------------ SQLite

async def test_sqlite_wal_and_busy_timeout_applied():
    from app.db.session import get_engine

    engine = get_engine()
    assert engine.url.drivername.startswith("sqlite")
    async with engine.connect() as conn:
        mode = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
        busy = (await conn.execute(text("PRAGMA busy_timeout"))).scalar()
    assert str(mode).lower() == "wal"
    assert int(busy) == 15000
