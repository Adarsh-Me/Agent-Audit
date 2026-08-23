"""Diagnostic: where do the pinned endpoints actually put their text?"""
import asyncio
import json

import httpx

from app.config import get_settings
from app.engine.client import OPENROUTER_URL


async def main() -> None:
    key = get_settings().openrouter_api_key
    prompt = ('You are choosing one product for a shopper. Reply with JSON only: '
              '{"product_id": "sku_001", "reason": "cheapest that fits"}')
    async with httpx.AsyncClient(timeout=90.0) as cx:
        for oid in ("stealth/ox-alpha", "nvidia/nemotron-3.5-lightning:free",
                    "z-ai/glm-5.2:free"):
            payload = {"model": oid, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 1.0,
                       "response_format": {"type": "json_object"}}
            r = await cx.post(OPENROUTER_URL, json=payload,
                              headers={"Authorization": f"Bearer {key}"})
            try:
                msg = r.json()["choices"][0]["message"]
                print(f"--- {oid} status={r.status_code}")
                for k, v in msg.items():
                    s = v if isinstance(v, str) else json.dumps(v)
                    print(f"    {k}: {s[:160]!r}")
            except Exception as exc:  # noqa: BLE001
                print(f"--- {oid} status={r.status_code} body={r.text[:200]!r} ({exc})")


asyncio.run(main())
