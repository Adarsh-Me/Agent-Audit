"""Reproduce one real trial end-to-end and dump the raw model output."""
import asyncio
import json
from pathlib import Path

from app.db.session import get_sessionmaker
from app.engine import prompts as P
from app.engine.client import OpenRouterClient
from app.engine.model_registry import load_model_registry
from app.engine.parse import parse_response
from sqlalchemy import select

from app.db.models import Product


async def main() -> None:
    maker = get_sessionmaker()
    async with maker() as s:
        rows = (await s.execute(select(Product).limit(40))).scalars().all()
    products = [{"id": r.sku, "title": r.title, "description": r.description or "",
                 "price_inr": r.price_inr, "structured_data": r.structured_data or {}}
                for r in rows]
    persona = json.loads(
        (Path("app/engine/personas/P05.json")).read_text(encoding="utf-8"))
    prompt = P.build_prompt(persona, products, null_allowed=True)
    print(f"prompt chars: {len(prompt)}")

    reg = load_model_registry()
    entry = reg.bulk[0]
    client = OpenRouterClient(min_interval_s=0)
    try:
        resp = await client.chat(entry, prompt, seed=123)
        print(f"tok={resp.prompt_tokens}/{resp.completion_tokens} latency={resp.latency_ms}ms")
        print(f"RAW[{len(resp.content)}]: {resp.content[:600]!r}")
        skus = {p['id'] for p in products}
        parsed = parse_response(resp.content, skus)
        print(f"parsed: ok={parsed.parse_ok} choice={parsed.choice!r} err={parsed.error!r}")
        if not parsed.parse_ok:
            # try again with feedback like the runner does
            resp2 = await client.chat(entry, prompt, seed=123,
                                      system_feedback=P.RETRY_FEEDBACK)
            print(f"RAW2: {resp2.content[:400]!r}")
            print("parsed2:", parse_response(resp2.content, skus))
    finally:
        await client.aclose()


asyncio.run(main())
