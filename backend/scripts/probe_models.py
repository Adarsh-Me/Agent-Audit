"""Live pre-flight: one real call per pinned OpenRouter endpoint (json_mode on).

Usage: python -m scripts.probe_models [openrouter_id ...]
       (args override the registry-derived endpoint list)
"""
import asyncio
import sys

from app.engine.client import OpenRouterClient, ProviderError
from app.engine.model_registry import ModelEntry, load_model_registry


async def main() -> None:
    overrides = sys.argv[1:]
    if overrides:
        entries = [ModelEntry(id=f"probe-{i}", openrouter_id=oid,
                              version=f"{oid}@probe", json_mode=True)
                   for i, oid in enumerate(overrides)]
    else:
        reg = load_model_registry()
        entries = reg.bulk + reg.flagship
    client = OpenRouterClient(min_interval_s=1.0)
    try:
        seen: set[str] = set()
        for e in entries:
            if e.openrouter_id in seen:
                continue
            seen.add(e.openrouter_id)
            prompt = ('You are choosing one product for a shopper. Reply with JSON only: '
                      '{"product_id": "sku_001", "reason": "cheapest that fits"}')
            try:
                r = await client.chat(e, prompt, seed=1)
                print(f"OK   {e.openrouter_id:45s} tok={r.prompt_tokens}/{r.completion_tokens} "
                      f"cost=${r.cost_usd}")
                print(f"     content[:140]={r.content[:140]!r}")
            except (Exception, ProviderError) as exc:  # noqa: BLE001 — probe reports everything
                print(f"FAIL {e.openrouter_id}: {type(exc).__name__}: {str(exc)[:200]}")
    finally:
        await client.aclose()


asyncio.run(main())
