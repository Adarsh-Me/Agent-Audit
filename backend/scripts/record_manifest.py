"""Record the demo manifest — the provenance artifact behind README headline numbers.

Usage: python -m scripts.record_manifest <run_id> [rerun_run_id]
Writes demo/manifest.json: models+versions, seed spec, cost, headline metrics with CIs,
git sha, prompt-hash sample. `make demo-check` re-verifies these against the DB (G12).
"""
import asyncio
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "demo" / "manifest.json"


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()[:12]
    except Exception:
        return "unknown"


async def record(run_id: str, rerun_id: str | None) -> dict:
    from sqlalchemy import func, select

    from app.db.models import Metric, Run, Trial
    from app.db.session import get_sessionmaker

    maker = get_sessionmaker()
    async with maker() as session:
        run = await session.get(Run, run_id)
        if run is None:
            raise SystemExit(f"run {run_id} not found")
        metrics = {
            m.key: {"value": m.value, "ci_low": m.ci_low, "ci_high": m.ci_high}
            for m in (await session.execute(
                select(Metric).where(Metric.run_id == run_id))).scalars()
        }
        n_trials = (await session.execute(
            select(func.count()).select_from(Trial).where(Trial.run_id == run_id))).scalar()
        n_cached = (await session.execute(
            select(func.count()).select_from(Trial).where(Trial.run_id == run_id,
                                                          Trial.from_cache.is_(True)))).scalar()
        sample = (await session.execute(
            select(Trial.prompt_hash).where(Trial.run_id == run_id).limit(1))).scalar()

        rerun_block = None
        if rerun_id:
            rmetrics = {
                m.key: {"value": m.value, "ci_low": m.ci_low, "ci_high": m.ci_high}
                for m in (await session.execute(
                    select(Metric).where(Metric.run_id == rerun_id))).scalars()
            }
            rerun_block = {"run_id": rerun_id, "metrics": rmetrics}

    manifest = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "original_run": {
            "run_id": run_id,
            "status": run.status,
            "trials": int(n_trials),
            "cache_hits": int(n_cached),
            "cost_usd": round(run.cost_usd or 0.0, 4),
            "models": run.models,
            "seed_spec": run.seeds,
            "prompt_hash_sample": sample,
            "prompt_hash_sample_sha256": hashlib.sha256(
                (sample or "").encode()).hexdigest()[:16],
        },
        "metrics": metrics,
        "rerun": rerun_block,
        "note": "All numbers regenerated deterministically from committed seeds and a "
                "pinned model list; response cache keyed on prompt_hash + model_version.",
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    rid = sys.argv[1] if len(sys.argv) > 1 else ""
    if not rid:
        raise SystemExit("usage: python -m scripts.record_manifest <run_id> [rerun_run_id]")
    rr = sys.argv[2] if len(sys.argv) > 2 else None
    man = asyncio.run(record(rid, rr))
    print(f"manifest written: {MANIFEST_PATH}")
    print(json.dumps(man["metrics"], indent=2)[:400])
