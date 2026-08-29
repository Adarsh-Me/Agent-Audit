"""Reproduce the runner's exact trial path against the live newest catalog.
Reveals finish_reason, usage, raw content, and parse verdict — never prints keys.
Run: $env:PYTHONPATH='.' ; python scripts/repro_runner.py
"""
import asyncio
import json

import httpx

from app.config import get_settings
from app.engine.client import OpenRouterClient
from app.engine.model_registry import load_model_registry
from app.engine.parse import parse_response


def build_prompt(persona: dict, products: list[dict], null_allowed: bool) -> str:
    # mirror app.engine.prompts.build_prompt without importing repo-only fixtures
    from app.engine.prompts import build_prompt as bp

    return bp(persona, products, null_allowed=null_allowed)


async def raw_call(entry, prompt: str, temperature: float) -> None:
    s = get_settings()
    key = getattr(s, entry.api_key_env, "") or s.openrouter_api_key
    base = (entry.base_url or "https://openrouter.ai/api/v1").rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    payload = {
        "model": entry.openrouter_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 6000,
    }
    async with httpx.AsyncClient(timeout=120) as cx:
        r = await cx.post(f"{base}/chat/completions", json=payload,
                          headers={"Authorization": f"Bearer {key}",
                                   "Content-Type": "application/json"})
        d = r.json()
        ch = (d.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        usage = d.get("usage") or {}
        content = msg.get("content")
        print(f"[raw t={temperature}] http={r.status_code} finish={ch.get('finish_reason')} "
              f"tok={usage.get('prompt_tokens')}/{usage.get('completion_tokens')}")
        print("content[:300]:", repr(content[:300]) if isinstance(content, str) else content)


async def main() -> None:
    import urllib.request

    # newest non-demo catalog = what _resolve_catalog picks
    with urllib.request.urlopen("https://agentaudit-api.antideploy.com/catalogs", timeout=20) as f:
        cats = json.load(f)["catalogs"]
    non_demo = [c for c in cats if c.get("source") != "demo"]
    cat = non_demo[0]
    cat_id = cat["id"]
    print(f"catalog: {cat.get('merchant')} ({cat_id[:8]}) products={cat.get('product_count')}")

    with urllib.request.urlopen(
            f"https://agentaudit-api.antideploy.com/catalog?catalog_id={cat_id}", timeout=30) as f:
        data = json.load(f)
    products = data["products"]
    skus = {p["sku"] for p in products}
    print(f"sku sample: {list(skus)[:3]}")

    persona = {
        "profile_summary": "Pragmatic gift shopper buying one item",
        "task": "Pick exactly one product that best matches your needs",
        "budget_inr": 3000,
    }
    # canonicalize rows the way the router does before building the prompt
    canon = []
    for p in products:
        canon.append({
            "id": p["sku"], "title": p.get("title"), "price_inr": p.get("price_inr"),
            "description": p.get("description"), "image_url": p.get("image_url"),
            "availability": p.get("availability"), "structured_data": p.get("structured_data") or {},
        })
    prompt = build_prompt(persona, canon, null_allowed=True)
    print(f"prompt_chars={len(prompt)} approx_tokens={len(prompt)//4}")

    entry = load_model_registry().bulk[0]

    # 1) probe-style raw call at default temperature (what enginecheck does)
    await raw_call(entry, prompt, 0.7)

    # 2) runner-style: OpenRouterClient.chat at temperature=1.0
    client = OpenRouterClient(min_interval_s=0)
    resp = await client.chat(entry, prompt, seed=1, temperature=1.0)
    print(f"[client t=1.0] content[:300]: {resp.content[:300]!r}")
    parsed = parse_response(resp.content, skus, None, null_allowed=True)
    print(f"[client t=1.0] parse_ok={parsed.parse_ok} choice={parsed.choice} err={parsed.error}")

    # 3) parse the RAW response from step 1 too
    await raw_call(entry, prompt, 1.0)
    asyncio.run  # noqa: B018


asyncio.run(main())
