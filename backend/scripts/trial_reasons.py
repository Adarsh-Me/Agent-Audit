"""Aggregate per-trial failure reasons for a run straight from the platform DB.
Never prints the connection string — only aggregated diagnostics.
Run: $env:PYTHONPATH='.' ; python scripts/trial_reasons.py <run_id8>
"""
import asyncio
import json
import os
import sys
from collections import Counter

import asyncpg


async def main() -> None:
    run8 = sys.argv[1]
    env = json.load(open(os.path.join(os.environ["TEMP"], "aa_ad_be_env.json"),
                         encoding="utf-8-sig"))
    url = env.get("DATABASE_URL") or env.get("POSTGRES_URL") or ""
    if not url:
        print("no DATABASE_URL in deploy env; keys:", sorted(env.keys()))
        return
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn, ssl="require", timeout=20)
    try:
        run = await conn.fetchrow(
            "SELECT id, status, abort_reason FROM run WHERE id::text LIKE $1 || '%'", run8)
        if run is None:
            print("run not found:", run8)
            return
        print("run:", str(run["id"])[:8], "status:", run["status"])

        rows = await conn.fetch(
            """SELECT parse_ok, choice IS NULL AS is_null, latency_ms,
                      LEFT(COALESCE(raw_response, ''), 160) AS raw_head,
                      COUNT(*) AS n
               FROM trial WHERE run_id = $1
               GROUP BY 1, 2, 3, 4 ORDER BY n DESC LIMIT 8""",
            run["id"])
        if not rows:
            # schema may differ; discover columns
            cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name='trial'")
            print("trial columns:", [c["column_name"] for c in cols])
            return
        for r in rows:
            print(f"n={r['n']} parse_ok={r['parse_ok']} null={r['is_null']} "
                  f"latency={r['latency_ms']} raw={r['raw_head']!r}")
    finally:
        await conn.close()


asyncio.run(main())
