"""G12 demo check — verify demo/manifest.json numbers against the database.

Run: make demo-check   (after a recorded run; exits 0 silently-consistent, 1 on drift)
"""
import asyncio
import json
import sys
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "demo" / "manifest.json"
TOL = 0.05  # absolute tolerance on metric values


async def check() -> bool:
    if not MANIFEST_PATH.exists():
        print("demo/manifest.json absent — nothing to verify yet (record a run first)")
        return True
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    from sqlalchemy import select

    from app.db.models import Metric, Run
    from app.db.session import get_sessionmaker

    ok = True
    async with get_sessionmaker()() as session:
        for label, block in (("original_run", manifest["original_run"]),
                             ("rerun", manifest.get("rerun"))):
            if not block:
                continue
            run = await session.get(Run, block["run_id"])
            if run is None:
                print(f"[FAIL] {label}: run {block['run_id']} missing from DB")
                ok = False
                continue
            db_metrics = {
                m.key: m.value for m in (await session.execute(
                    select(Metric).where(Metric.run_id == block["run_id"]))).scalars()
            }
            for key, recorded in block["metrics"].items():
                db_v = db_metrics.get(key)
                if db_v is None:
                    print(f"[FAIL] {label}.{key}: metric missing in DB")
                    ok = False
                elif abs((db_v or 0) - (recorded.get("value") or 0)) > TOL:
                    print(f"[FAIL] {label}.{key}: manifest={recorded['value']} db={db_v}")
                    ok = False
            cost_recorded = block.get("cost_usd")
            if cost_recorded is not None and abs(run.cost_usd - cost_recorded) > 1.0:
                print(f"[FAIL] {label} cost drift: manifest={cost_recorded} db={run.cost_usd}")
                ok = False
    print("demo_check:", "OK — manifest matches database" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(check()) else 1)
