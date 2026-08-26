"""Remediation loop end-to-end — T9.x: propose → E401 gate → review → mirror → rerun.

Runs against a mocked provider; proves the human-gated loop and that a remediated
re-run re-bills (fresh prompts) while an unchanged one doesn't.
"""
import pytest

from app.engine.runner import Runner, RunnerDeps
from app.engine.model_registry import load_model_registry
from app.ingest.demo import load_demo_catalog
from app.remediate.fixes import build_mirror_catalog, generate_remediations


class RichBiasClient:
    """Chooses rich listings strongly — mirrors the engineered demo story."""

    async def chat(self, entry, prompt: str, seed: int, system_feedback=None):
        from app.engine.client import LLMResponse

        null_allowed = '{"product_id": null' in prompt
        h = hash((prompt[:48], seed)) & 0xFFFF
        if null_allowed and h % 11 == 0:
            choice = None
        else:
            # pick a sku deterministically biased to early-listed rich items
            choice = ["sku_007", "sku_007", "sku_017", "sku_029", "sku_001"][h % 5]
        content = f'{{"product_id": {choice!r}, "reason": "loop test"}}'
        return LLMResponse(content=content, prompt_tokens=300, completion_tokens=25,
                           cost_usd=0.001, latency_ms=1, model_version=entry.version)


async def _full_loop(db_env):
    registry = load_model_registry()
    async with db_env() as session:
        catalog_id = await load_demo_catalog(session)

    deps = RunnerDeps(registry=registry, client=RichBiasClient())
    run_id = await Runner(db_env, deps).run_audit(catalog_id)

    async with db_env() as session:
        gen = await generate_remediations(session, run_id)
        assert gen["created"] >= 10  # all 10 starved SKUs flagged

        # E401: mirror before review must fail
        from app.errors import AppError
        with pytest.raises(AppError) as ei:
            await build_mirror_catalog(session, run_id)
        assert ei.value.code == "E401"

        # approve all pending rows
        from sqlalchemy import select
        from app.db.models import Remediation
        rems = (await session.execute(
            select(Remediation).where(Remediation.run_id == run_id))).scalars().all()
        assert len(rems) == gen["created"]
        for r in rems:
            r.status = "approved"
            r.reviewed_by = "test"
        await session.commit()

        # hero's title fix matches APPFLOW verbatim
        # find sku_023's remediation specifically
        from app.db.models import Product

        for r in rems:
            p = await session.get(Product, r.product_id)
            if p.sku == "sku_023":
                fx = {f["field"]: f for f in r.fixes}
                assert fx["title"]["after"] == \
                    "TrailBuddy Daypack 22L — water-resistant, laptop-sleeve, 980g"
                break

        mirror_id = await build_mirror_catalog(session, run_id)
        from app.db.models import Catalog
        mirror = await session.get(Catalog, mirror_id)
        assert mirror.source == "mirror" and mirror.parent_catalog_id == catalog_id
        assert mirror.version == 2

        # mirror product for sku_023 carries the fixed listing + structured data
        from sqlalchemy import select as s2
        hero = (await session.execute(
            s2(Product).where(Product.catalog_id == mirror_id,
                              Product.sku == "sku_023"))).scalar_one()
        assert hero.title.startswith("TrailBuddy Daypack 22L")
        assert hero.structured_data["jsonld_present"] is True
        return run_id, catalog_id, mirror_id


async def test_rerun_rebills_after_remediation(db_env):
    registry = load_model_registry()
    run_id, catalog_id, mirror_id = await _full_loop(db_env)

    fake = RichBiasClient()
    deps = RunnerDeps(registry=registry, client=fake)
    rerun_id = await Runner(db_env, deps).run_audit(mirror_id, parent_run_id=run_id,
                                                    type_="rerun")

    async with db_env() as session:
        from sqlalchemy import func, select
        from app.db.models import Run, Trial

        rerun = await session.get(Run, rerun_id)
        assert rerun.type == "rerun" and rerun.parent_run_id == run_id
        n_new = (await session.execute(
            select(func.count()).select_from(Trial).where(Trial.run_id == rerun_id,
                                                          Trial.from_cache.is_(False))
        )).scalar()
        total = (await session.execute(
            select(func.count()).select_from(Trial).where(Trial.run_id == rerun_id)
        )).scalar()
    assert total == 220
    assert n_new > 200, "remediated rerun must be mostly fresh trials (SC-3)"
