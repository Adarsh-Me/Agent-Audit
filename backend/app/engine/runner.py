"""Trial runner — full-matrix execution with production semantics (TECHSPEC §7.4).

Status machine (SCHEMA §2.5): queued → running → {done | partial | failed}
  partial = cost cap (E203) or circuit breaker — never rendered as complete anywhere.
Presented orders:
  C1     → catalog baseline order (demo: committed fixture block order; uploads: sku-sorted)
  C2-s{k}→ seeded shuffle shared across all personas and models
  C3-A/B → framing subset in baseline-relative order; B applies variant copy
"""
from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.constants import COST_CAP_USD, PARSE_RETRIES, TRIAL_WALL_CAP_S
from app.db.models import Product, Run, Trial
from app.engine import prompts as P
from app.engine.cache import cache_get, cache_put
from app.engine.client import CostLedger, LLMResponse, OpenRouterClient, ProviderError
from app.engine.conditions import TrialSpec, enumerate_trials, shuffle_seed
from app.engine.model_registry import ModelRegistry, load_model_registry
from app.engine.parse import parse_response
from pathlib import Path

ProgressCb = Callable[[dict], Awaitable[None]]

DEMO_ROOT = Path(__file__).resolve().parents[3] / "demo-store"


def _consume_task_exception(task: "asyncio.Task") -> None:
    """Done-callback so abandoned tasks never surface 'exception was never retrieved'."""
    if not task.cancelled():
        task.exception()


async def _shielded_live_call(coro: Awaitable[LLMResponse],
                              cap_s: float | None = None) -> LLMResponse:
    """Run one chat() call (retries + backoff included) under an UNBREAKABLE cap.

    Plain wait_for cannot bound a coroutine whose cancellation never completes —
    a proxied connection can hang past every httpx bound AND ignore cancel
    (2026-08-22 nemotron freeze). Shielding the task and abandoning it on
    timeout guarantees the caller resumes at the cap no matter what the inner
    task does; the leaked task is cancelled best-effort and its exception
    consumed. The trial degrades to a counted provider failure instead.
    """
    cap = TRIAL_WALL_CAP_S if cap_s is None else cap_s
    task = asyncio.create_task(coro)
    task.add_done_callback(_consume_task_exception)
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=cap)
    except TimeoutError:
        task.cancel()
        raise ProviderError(
            f"trial wall cap ({cap:.0f}s) exceeded — attempt abandoned") from None


@dataclass
class TrialOutcome:
    choice: str | None
    reason: str | None
    latency_ms: int
    from_cache: bool
    parse_ok: bool


@dataclass
class RunnerDeps:
    registry: ModelRegistry = field(default_factory=load_model_registry)
    client: OpenRouterClient | None = None
    cost_cap_usd: float | None = None  # overrides settings (tests / budget experiments)


def load_baseline_order_fixture() -> list[str]:
    return json.loads((DEMO_ROOT / "products.json").read_text("utf-8"))["baseline_order"]


def resolve_presented_order(
    condition: str,
    products: list[dict],  # canonical dicts for the catalog (sku-keyed fields)
    baseline: list[str],
) -> tuple[list[str], str]:
    """Returns (presented sku order, order_kind)."""
    by_sku = {p["id"]: p for p in products}
    if condition.startswith("C1"):
        return list(baseline), "baseline"
    if condition.startswith("C2"):
        rng = random.Random(shuffle_seed(condition))
        order = list(baseline)
        rng.shuffle(order)
        return order, f"shuffle:{condition}"
    if condition.startswith("C3"):
        variants = P.load_framing_variants()
        subset_ids = [k for k in variants if not k.startswith("_")]
        # framing subset in baseline-relative order (uploads: subset must exist in catalog;
        # selection per SCHEMA C-4 refined on Day 7 — interim: first 10 skus sorted)
        known = [s for s in subset_ids if s in by_sku]
        if len(known) < len(subset_ids):
            known = sorted(by_sku)[:10]
        known.sort(key=baseline.index)
        return known, f"framing:{condition}"
    raise ValueError(f"unknown condition {condition}")


class Runner:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession],
                 deps: RunnerDeps | None = None) -> None:
        self.session_factory = session_factory
        self.deps = deps or RunnerDeps()

    async def run_audit(self, catalog_id: str, *, parent_run_id: str | None = None,
                        type_: str = "audit", progress: ProgressCb | None = None,
                        run_id: str | None = None) -> str:
        """Execute the full matrix. If run_id is given, ADOPT that existing row
        (created by the API layer so the returned audit id is the live run)
        instead of inserting a second one."""
        settings = get_settings()
        cap = self.deps.cost_cap_usd if self.deps.cost_cap_usd is not None else (
            settings.cost_cap_usd if settings.cost_cap_usd else COST_CAP_USD
        )
        ledger = CostLedger(cap_usd=cap)

        async with self.session_factory() as session:
            if run_id is not None:
                run = await session.get(Run, run_id)
                assert run is not None, f"adopted run {run_id} not found"
                run.catalog_id = catalog_id
                run.type = type_
                if parent_run_id:
                    run.parent_run_id = parent_run_id
                run.status = "queued"
            else:
                run = Run(
                    catalog_id=catalog_id,
                    parent_run_id=parent_run_id,
                    type=type_,
                    status="queued",
                    trials_total=640,
                )
                session.add(run)
            run.models = self.deps.registry.snapshot()
            run.seeds = {
                "spec_version": 1,
                "trial": "int(sha256('trial|{persona}|{condition}')[:8],16) % 2^31",
                "shuffle": "int(sha256('shuffle|{condition}')[:8],16) % 2^31",
            }
            run.trials_total = 640
            await session.commit()
            run_id = run.id

        status = "done"
        abort_reason: str | None = None
        done = 0

        async def emit(event: dict) -> None:
            if progress:
                await progress(event)

        try:
            async with self.session_factory() as session:
                run = await session.get(Run, run_id)
                assert run is not None
                run.status = "running"
                run.started_at = datetime.now(timezone.utc)
                await session.commit()

                rows = (
                    (await session.execute(
                        select(Product).where(Product.catalog_id == catalog_id).order_by(Product.sku)
                    ))
                    .scalars()
                    .all()
                )
                products = [
                    {
                        "id": r.sku,
                        "title": r.title,
                        "description": r.description or "",
                        "price_inr": r.price_inr,
                        "structured_data": r.structured_data or {},
                    }
                    for r in rows
                ]
                by_sku = {p["id"]: p for p in products}

            baseline = self._baseline_for(catalog_id, products)

            personas_dir = Path(__file__).parent / "personas"
            persona_cache = {
                p.stem: json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(personas_dir.glob("P*.json"))
            }

            trials = enumerate_trials(self.deps.registry)
            batch: list[Trial] = []
            order_cache: dict[str, tuple[list[str], str]] = {}
            framing_variants = P.load_framing_variants()

            for spec in trials:
                if ledger.capped:
                    status, abort_reason = "partial", "cost_cap"
                    await emit({"type": "e203_cost_cap", "done": done, "total": len(trials),
                                "cost_usd": round(ledger.total_usd, 4)})
                    break

                key = spec.condition
                if key not in order_cache:
                    order_cache[key] = resolve_presented_order(key, products, baseline)
                presented_skus, _kind = order_cache[key]
                presented_products = [by_sku[s] for s in presented_skus]
                # models that answer with the line number instead of the bracket id
                # still get measured — map "1".."n" to the presented order
                ordinal_map = {str(i): sku for i, sku in enumerate(presented_skus, 1)}

                persona = persona_cache[spec.persona_id]
                variant = framing_variants if spec.condition.startswith("C3-B") else None
                prompt = P.build_prompt(persona, presented_products,
                                        null_allowed=spec.null_allowed, framing_variant=variant)
                phash = P.prompt_hash(prompt, spec.seed)

                try:
                    outcome = await self._execute_trial(spec, prompt, phash, set(by_sku),
                                                        ledger, emit, ordinal_map)
                except Exception as exc:  # noqa: BLE001
                    # Engine-level escape hatch: NO single trial may kill a
                    # 640-trial run (2026-08-22 freeze post-mortem). Counted as
                    # a provider-style failure, surfaced via parse_rate.
                    await emit({"type": "trial", "model": spec.model,
                                "persona_id": spec.persona_id,
                                "condition": spec.condition, "choice": None,
                                "latency_ms": 0, "parse_ok": False})
                    outcome = TrialOutcome(None, f"engine error: {exc}", 0, False, False)
                batch.append(Trial(
                    run_id=run_id,
                    model=spec.model,
                    model_version=spec.model_version,
                    tier=spec.tier,
                    persona_id=spec.persona_id,
                    condition=spec.condition,
                    seed=spec.seed,
                    presented_order=presented_skus,
                    choice=outcome.choice,
                    reason=outcome.reason,
                    latency_ms=outcome.latency_ms,
                    prompt_hash=phash,
                    from_cache=outcome.from_cache,
                    null_allowed=spec.null_allowed,
                    parse_ok=outcome.parse_ok,
                ))
                done += 1
                if done % 40 == 0 or done == len(trials):
                    try:
                        async with self.session_factory() as s2:
                            s2.add_all(batch)
                            await s2.commit()
                            run = await s2.get(Run, run_id)
                            assert run
                            run.cost_usd = round(ledger.total_usd, 4)
                            await s2.commit()
                    except Exception:
                        for t in batch:
                            if (t.parse_ok and t.choice is None and not t.null_allowed):
                                raise AssertionError(
                                    f"choice-semantics violation: {t.model} {t.persona_id} "
                                    f"{t.condition} cached={t.from_cache}"
                                )
                        raise
                    batch.clear()
                    await emit({"type": "progress", "done": done, "total": len(trials),
                                "cost_usd": round(ledger.total_usd, 4)})

            if batch:
                async with self.session_factory() as s2:
                    s2.add_all(batch)
                    await s2.commit()
        except ProviderError as exc:
            status, abort_reason = "partial", f"circuit_breaker: {exc}"
        except Exception as exc:  # noqa: BLE001 — any engine crash becomes a labeled failure
            status, abort_reason = "failed", f"engine_error: {type(exc).__name__}: {exc}"

        async with self.session_factory() as s3:
            run = await s3.get(Run, run_id)
            assert run
            run.status = status
            run.cost_usd = round(ledger.total_usd, 4)
            run.abort_reason = abort_reason
            run.completed_at = datetime.now(timezone.utc)
            await s3.commit()
        await emit({"type": "complete", "run_id": run_id, "status": status,
                    "abort_reason": abort_reason})
        return run_id

    def _baseline_for(self, catalog_id: str, products: list[dict]) -> list[str]:
        """Demo catalogs use the committed fixture block order (sku_023 @ position 19);
        other catalogs fall back to sku-sorted order."""
        skus = {p["id"] for p in products}
        fixture_order = load_baseline_order_fixture()
        if set(fixture_order) == skus:
            return fixture_order
        return sorted(skus)

    async def _execute_trial(self, spec: TrialSpec, prompt: str, phash: str,
                             valid_skus: set[str], ledger: CostLedger,
                             emit, ordinal_map: dict[str, str] | None = None) -> TrialOutcome:
        """Cache lookup → live call → parse retries with feedback."""
        async with self.session_factory() as session:
            cached = await cache_get(session, phash, spec.model_version)
        if cached is not None:
            choice = cached.get("product_id")
            ok = choice is None or choice in valid_skus
            return TrialOutcome(choice, cached.get("reason"), 0, True, ok)

        entry = self.deps.registry.by_id(spec.model)
        feedback: str | None = None
        last: LLMResponse | None = None
        for attempt in range(PARSE_RETRIES):
            try:
                resp = await _shielded_live_call(
                    self.deps.client.chat(entry, prompt, spec.seed,
                                          system_feedback=feedback))
            except ProviderError as exc:
                # provider-side failure (429 storm / breaker / blank content after
                # retries): count this trial as a parse failure and keep the run
                # alive — a single endpoint hiccup must not abort 640 trials.
                # Surfaced honestly via per-model parse_rate.
                await emit({"type": "trial", "model": spec.model,
                            "persona_id": spec.persona_id, "condition": spec.condition,
                            "choice": None, "latency_ms": 0, "parse_ok": False})
                return TrialOutcome(None, f"provider error: {exc}", 0, False, False)
            ledger.add(spec.model, resp.cost_usd)
            last = resp
            parsed = parse_response(resp.content, valid_skus, ordinal_map)
            if parsed.parse_ok:
                async with self.session_factory() as session:
                    await cache_put(session, phash, spec.model_version,
                                    {"product_id": parsed.choice, "reason": parsed.reason,
                                     "raw": resp.content})
                    await session.commit()
                await emit({
                    "type": "trial",
                    "model": spec.model,
                    "persona_id": spec.persona_id,
                    "condition": spec.condition,
                    "choice": parsed.choice,
                    "latency_ms": resp.latency_ms,
                    "parse_ok": True,
                })
                return TrialOutcome(parsed.choice, parsed.reason, resp.latency_ms, False, True)
            feedback = P.RETRY_FEEDBACK
        # parse failures excluded from metrics; counted via parse_rate:{model}
        await emit({"type": "trial", "model": spec.model, "persona_id": spec.persona_id,
                    "condition": spec.condition, "choice": None, "latency_ms": last.latency_ms,
                    "parse_ok": False})
        return TrialOutcome(None, None, last.latency_ms, False, False)


async def execute_run(session_factory, deps: RunnerDeps, catalog_id: str, **kw) -> str:
    runner = Runner(session_factory, deps)
    if runner.deps.client is None:
        runner.deps.client = OpenRouterClient()
    return await runner.run_audit(catalog_id, **kw)
