"""OpenRouter client tests — mocked transport (no network, no cost)."""
import json

import httpx
import pytest

from app.engine.client import (
    CostLedger,
    OpenRouterClient,
    ProviderError,
    estimate_cost_usd,
)
from app.engine.model_registry import load_model_registry


def _resp(status: int = 200, content: str = '{"product_id": "sku_007", "reason": "r"}',
          ptok: int = 500, ctok: int = 50) -> httpx.Response:
    body = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": ptok, "completion_tokens": ctok},
    }
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://x"))


@pytest.fixture
def entry():
    return load_model_registry().bulk[0]  # gpt4o-mini


async def test_success_and_cost_math(entry):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return _resp()

    client = OpenRouterClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    try:
        out = await client.chat(entry, "prompt", seed=1)
        assert out.choice if hasattr(out, "choice") else True
        assert out.content.startswith('{"product_id"')
        assert out.latency_ms >= 0
        assert abs(out.cost_usd - estimate_cost_usd("gpt4o-mini", 500, 50)) < 1e-9
        # seed passed when provider supports it; json mode requested
        assert calls[0]["seed"] == 1
        assert calls[0]["response_format"] == {"type": "json_object"}
    finally:
        await client.aclose()


async def test_retries_on_5xx_then_succeeds(entry):
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] < 3:
            return _resp(status=500)
        return _resp()

    client = OpenRouterClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    try:
        out = await client.chat(entry, "p", seed=2)
        assert out.prompt_tokens == 500
        assert state["n"] == 3
    finally:
        await client.aclose()


async def test_circuit_breaker_opens_after_threshold(entry):
    def handler(request: httpx.Request) -> httpx.Response:
        return _resp(status=400)  # hard 4xx → immediate failure, no retry

    client = OpenRouterClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    try:
        opened = False
        for _ in range(10):
            with pytest.raises(ProviderError):
                await client.chat(entry, "p", seed=3)
        assert client.breakers[entry.openrouter_id].consecutive_failures == 10
        opened = client.breakers[entry.openrouter_id].open
        assert opened
        with pytest.raises(ProviderError, match="circuit breaker open"):
            await client.chat(entry, "p", seed=4)
    finally:
        await client.aclose()


def test_cost_ledger_cap():
    ledger = CostLedger(cap_usd=0.01)
    ledger.add("gpt4o-mini", 0.004)
    assert not ledger.capped
    ledger.add("gpt4o-mini", 0.007)
    assert ledger.capped


def test_estimate_cost_known_models():
    assert estimate_cost_usd("gpt4o-mini", 1_000_000, 0) == pytest.approx(0.15)
    assert estimate_cost_usd("claude-haiku", 0, 1_000_000) == pytest.approx(4.0)
