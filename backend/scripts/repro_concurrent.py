"""Repro: 10 CONCURRENT engine-client calls (pacing off) — mirrors the runner's
ENGINE_CONCURRENCY=10 + SARVAM_REQUEST_INTERVAL_S=0 burst profile.
Run: $env:PYTHONPATH='.' ; python scripts/repro_concurrent.py
"""
import asyncio
import json
import os

from app.engine.client import OpenRouterClient
from app.engine.model_registry import load_model_registry
from app.engine.parse import parse_response
from app.engine.prompts import build_prompt

CATALOG_FILE = os.path.join(os.environ.get("TEMP", "."), "aa_demo_catalog.json")


async def main() -> None:
    with open(CATALOG_FILE, encoding="utf-8") as f:
        data = json.load(f)
    products = data["products"]
    skus = {p["id"] for p in products}
    canon = [{
        "id": p["id"], "title": p.get("title"), "price_inr": p.get("price_inr"),
        "description": p.get("description"), "image_url": p.get("image_url"),
        "structured_data": p.get("structured_data") or {},
    } for p in products]
    persona = {
        "profile_summary": "Pragmatic gift shopper buying one item",
        "task": "Pick exactly one product that best matches your needs",
        "budget_inr": 3000,
    }
    prompt = build_prompt(persona, canon, null_allowed=True)
    entry = load_model_registry().bulk[0]

    client = OpenRouterClient(min_interval_s=0)  # matches deploy env

    async def one(i: int) -> str:
        try:
            resp = await client.chat(entry, prompt, seed=i, temperature=1.0)
            parsed = parse_response(resp.content, skus, None, null_allowed=True)
            tag = "OK " if parsed.parse_ok else "FAIL"
            print(f"[{i:02d}] {tag} len={len(resp.content)} choice={parsed.choice} "
                  f"err={parsed.error} head={resp.content[:120]!r}")
            return tag
        except Exception as exc:  # noqa: BLE001
            print(f"[{i:02d}] EXC {type(exc).__name__}: {str(exc)[:160]}")
            return "EXC"

    results = await asyncio.gather(*[one(i) for i in range(1, 11)])
    ok = results.count("OK ")
    print(f"SUMMARY: {ok}/10 parsed OK")


asyncio.run(main())
