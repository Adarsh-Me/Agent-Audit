"""Repro: runner-path call (engine client, temp=1.0) against a saved catalog JSON.
Run: $env:PYTHONPATH='.' ; python scripts/repro_demo.py
"""
import asyncio
import json
import os

from app.engine.client import OpenRouterClient
from app.engine.model_registry import load_model_registry
from app.engine.parse import parse_response
from app.engine.prompts import build_prompt

CATALOG_FILE = os.path.join(os.environ.get("TEMP", "."), "aa_demo_catalog.json")


def main_sync_calls() -> None:
    with open(CATALOG_FILE, encoding="utf-8") as f:
        data = json.load(f)
    products = data["products"]
    skus = {p["id"] for p in products}
    print("sku sample:", sorted(skus)[:3], "count:", len(skus))

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
    print("prompt_chars:", len(prompt))

    entry = load_model_registry().bulk[0]
    client = OpenRouterClient(min_interval_s=0)

    async def call(t: float) -> None:
        resp = await client.chat(entry, prompt, seed=1, temperature=t)
        parsed = parse_response(resp.content, skus, None, null_allowed=True)
        print(f"t={t} content_len={len(resp.content)} parse_ok={parsed.parse_ok} "
              f"choice={parsed.choice} err={parsed.error}")
        print("content[:220]:", repr(resp.content[:220]))

    asyncio.run(call(1.0))
    asyncio.run(call(1.0))


main_sync_calls()
