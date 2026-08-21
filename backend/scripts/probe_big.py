"""Big-prompt latency probe: does reasoning-effort control fix the crawl?"""
import asyncio
import json
import time

import httpx

from app.config import get_settings
from app.engine.client import OPENROUTER_URL


def big_prompt() -> str:
    lines = []
    for i in range(1, 41):
        lines.append(
            f'{{"id": "sku_{i:03d}", "title": "Product {i} Pro Max Ultra", '
            f'"price_inr": {499 + i * 37}, "description": "A durable, lightweight '
            f'everyday product with premium finish, 1-year warranty, ergonomic grip, '
            f'available in three colours. Rated 4.{i % 5} by 128 buyers."}}'
        )
    catalog = ",\n".join(lines)
    return (
        "You are P07, a Deal Hunter shopper. Pick exactly one product that is the "
        "best value-for-money among the following catalog. Reply ONLY with JSON: "
        '{"product_id": "<sku>", "reason": "<=20 words"}\nCATALOG:\n[' + catalog + "]"
    )


async def call(cx: httpx.AsyncClient, key: str, oid: str, extra: dict) -> None:
    payload = {"model": oid,
               "messages": [{"role": "user", "content": big_prompt()}],
               "temperature": 1.0,
               "response_format": {"type": "json_object"}, **extra}
    t0 = time.monotonic()
    r = await cx.post(OPENROUTER_URL, json=payload,
                      headers={"Authorization": f"Bearer {key}"})
    dt = time.monotonic() - t0
    try:
        msg = r.json()["choices"][0]["message"]
        usage = r.json().get("usage", {})
        content = msg.get("content")
        print(f"{oid} extra={json.dumps(extra)} -> {dt:.1f}s status={r.status_code} "
              f"tok={usage.get('prompt_tokens')}/{usage.get('completion_tokens')} "
              f"content={'YES' if isinstance(content, str) and content.strip() else 'NULL'}"
              f" :: {str(content)[:80]!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"{oid} extra={json.dumps(extra)} -> {dt:.1f}s status={r.status_code} ERR {exc} {r.text[:120]!r}")


async def main() -> None:
    key = get_settings().openrouter_api_key
    oid = "stealth/ox-alpha"
    async with httpx.AsyncClient(timeout=300.0) as cx:
        await call(cx, key, oid, {})
        await asyncio.sleep(2)
        await call(cx, key, oid, {"max_tokens": 3500,
                                  "reasoning": {"effort": "low", "exclude": True}})


asyncio.run(main())
