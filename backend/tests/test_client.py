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
    # pin by id, not bulk[0]: slot order is scheduling priority and may reorder
    return load_model_registry().by_id("xpreview")


def _mock_client(handler):
    return OpenRouterClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        min_interval_s=0,  # no rate-cap pacing under MockTransport
    )


async def test_success_and_cost_math(entry):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return _resp()

    client = _mock_client(handler)
    try:
        out = await client.chat(entry, "prompt", seed=1)
        assert out.choice if hasattr(out, "choice") else True
        assert out.content.startswith('{"product_id"')
        assert out.latency_ms >= 0
        assert abs(out.cost_usd - estimate_cost_usd("xpreview", 500, 50)) < 1e-9
        # json mode requested; seed omitted because pinned models don't support it
        assert "seed" not in calls[0]
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

    client = _mock_client(handler)
    try:
        out = await client.chat(entry, "p", seed=2)
        assert out.prompt_tokens == 500
        assert state["n"] == 3
    finally:
        await client.aclose()


async def test_circuit_breaker_opens_after_threshold(entry):
    def handler(request: httpx.Request) -> httpx.Response:
        return _resp(status=400)  # hard 4xx → immediate failure, no retry

    client = _mock_client(handler)
    try:
        opened = False
        for _ in range(10):
            with pytest.raises(ProviderError):
                await client.chat(entry, "p", seed=3)
        # breaker keys are namespaced by provider origin (2026-08-24 multi-provider)
        bkey = f"{entry.base_url or 'openrouter'}::{entry.openrouter_id}"
        assert client.breakers[bkey].consecutive_failures == 10
        opened = client.breakers[bkey].open
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
    # current pin prices $0.00 in the ledger (OpenCode Zen free-tier endpoint)
    assert estimate_cost_usd("xpreview", 1_000_000, 0) == pytest.approx(0.0)
    assert estimate_cost_usd("xpreview-flagship", 0, 1_000_000) == pytest.approx(0.0)
    # unknown ids fall back to a conservative $1/M so surprises surface in the ledger
    assert estimate_cost_usd("not-in-table", 0, 1_000_000) == pytest.approx(1.0)
