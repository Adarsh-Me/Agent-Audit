"""Record a DEMO-PROVIDER-LABELED manifest from a deterministic scripted run.

This proves the entire verification chain (run → metrics → remediation → mirror →
rerun → delta → manifest → demo_check) without spending money or pretending to be
live data. The manifest is explicitly labeled provider="mock-deterministic".
Replace with a real OPENROUTER_API_KEY run before quoting headline numbers publicly.

Run: python -m scripts.record_demo_run
"""
import asyncio
import json


class DeterministicClient:
    """Scripted provider: rich-biased choices, ~9% nulls where allowed."""

    async def chat(self, entry, prompt: str, seed: int, system_feedback=None):
        from app.engine.client import LLMResponse

        null_allowed = '{"product_id": null' in prompt
        h = hash((prompt[:48], seed)) & 0xFFFF
        if null_allowed and h % 11 == 0:
            choice = None
        else:
            choice = ["sku_007", "sku_007", "sku_017", "sku_029", "sku_001"][h % 5]
        return LLMResponse(
            content=json.dumps({"product_id": choice, "reason": "demo recording"}),
            prompt_tokens=420, completion_tokens=38,
            cost_usd=0.0, latency_ms=1, model_version=entry.version,
        )


async def main() -> None:
    from sqlalchemy import select

    from app.db.models import Catalog, Remediation
    from app.db.session import get_sessionmaker, init_db
    from app.engine.model_registry import load_model_registry
    from app.engine.runner import Runner, RunnerDeps
    from app.ingest.demo import load_demo_catalog
    from app.remediate.fixes import build_mirror_catalog, generate_remediations
    from app.routers.audit import compute_and_store_metrics
    from scripts.record_manifest import record

    await init_db()
    maker = get_sessionmaker()
    registry = load_model_registry()
    deps = RunnerDeps(registry=registry, client=DeterministicClient())

    async with maker() as session:
        catalog_id = await load_demo_catalog(session)

    original = await Runner(maker, deps).run_audit(catalog_id)

    async with maker() as session:
        await generate_remediations(session, original)
        rems = (await session.execute(
            select(Remediation).where(Remediation.run_id == original))).scalars().all()
        for r in rems:
            r.status = "approved"
            r.reviewed_by = "demo-recording"
        await session.commit()
        mirror_id = await build_mirror_catalog(session, original)

    rerun = await Runner(maker, deps).run_audit(mirror_id, parent_run_id=original,
                                                type_="rerun")

    async with maker() as session:
        await compute_and_store_metrics(session, original)
        await compute_and_store_metrics(session, rerun)

    manifest = await record(original, rerun)
    # explicit provider labeling — this is a scripted deterministic run, not live LLMs
    manifest["provider"] = "mock-deterministic"
    manifest["note"] += (" RECORDED WITH A SCRIPTED DETERMINISTIC PROVIDER — replace with "
                         "a live OpenRouter run before citing externally.")
    from scripts.record_manifest import MANIFEST_PATH

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"demo run recorded: original={original} rerun={rerun}")
    print(f"score:", manifest["metrics"].get("score"))


if __name__ == "__main__":
    asyncio.run(main())
