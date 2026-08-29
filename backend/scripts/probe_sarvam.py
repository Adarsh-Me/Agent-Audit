"""Direct Sarvam probe: reveal finish_reason, content vs reasoning, usage.
Never prints the key. Run: python scripts/probe_sarvam.py
"""
import asyncio
import json

import httpx

from app.config import get_settings
from app.engine.model_registry import load_model_registry


async def main() -> None:
    s = get_settings()
    entry = load_model_registry().bulk[0]
    key = getattr(s, entry.api_key_env, "") or s.openrouter_api_key
    base = (entry.base_url or "https://openrouter.ai/api/v1").rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # A realistic-but-small audit prompt: pick one of 6 skus, terse JSON.
    def make_prompt(n: int) -> str:
        catalog = ", ".join(
            f'{{"id":"sku_{i:03d}","title":"Product {i} Pro Max Ultra Edition", '
            f'"price_inr":{499+i*37},"description":"A durable, lightweight everyday '
            f'product with premium finish, 1-year warranty, ergonomic grip, available '
            f'in three colours. Rated 4.{i%5} by 128 buyers."}}'
            for i in range(1, n + 1)
        )
        return (
            "You are P07, a Deal Hunter. Pick exactly one best value-for-money product. "
            'Reply ONLY with JSON: {"product_id": "<sku>", "reason": "<=20 words"}\n'
            "CATALOG:\n[" + catalog + "]"
        )

    for n in (40, 100):
        prompt = make_prompt(n)
        payload = {
            "model": entry.openrouter_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 1.0,
            "max_tokens": 6000,
        }
        async with httpx.AsyncClient(timeout=120) as cx:
            try:
                r = await cx.post(url, json=payload, headers=headers)
                d = r.json()
                ch = (d.get("choices") or [{}])[0]
                msg = ch.get("message") or {}
                usage = d.get("usage") or {}
                content = msg.get("content")
                print(f"--- n={n} prompt_chars={len(prompt)} http={r.status_code} ---")
                print("finish_reason:", ch.get("finish_reason"))
                print("prompt_tokens:", usage.get("prompt_tokens"),
                      "completion_tokens:", usage.get("completion_tokens"))
                print("content is None:", content is None,
                      "| content len:", len(content) if isinstance(content, str) else "n/a")
                print("content[:240]:", repr(content[:240]) if isinstance(content, str) else content)
            except Exception as exc:  # noqa: BLE001
                print(f"--- n={n} ERROR {type(exc).__name__}: {exc} ---")
        await asyncio.sleep(2)


asyncio.run(main())
