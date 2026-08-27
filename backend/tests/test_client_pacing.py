"""Provider-paced interval override (env-driven; 2026-08-27)."""
import asyncio
import time
import httpx

from app.engine.client import OpenRouterClient, get_min_request_interval_s
from app.engine.model_registry import ModelEntry


def test_per_entry_interval_defaults_to_module_constant():
    e = ModelEntry(id="t", openrouter_id="t", version="t")
    # no env hint, no api_key_env → module default 3.2
    assert get_min_request_interval_s(e) == 3.2


def test_per_entry_interval_reads_env_override(monkeypatch):
    e = ModelEntry(id="t", openrouter_id="t", version="t", api_key_env="sarvam_api_key")
    monkeypatch.setenv("SARVAM_REQUEST_INTERVAL_S", "0")
    assert get_min_request_interval_s(e) == 0.0
    monkeypatch.setenv("SARVAM_REQUEST_INTERVAL_S", "0.25")
    assert get_min_request_interval_s(e) == 0.25


def test_env_garbage_falls_back_to_default(monkeypatch):
    e = ModelEntry(id="t", openrouter_id="t", version="t", api_key_env="sarvam_api_key")
    monkeypatch.setenv("SARVAM_REQUEST_INTERVAL_S", "not-a-number")
    assert get_min_request_interval_s(e) == 3.2


def test_client_honors_env_pace_override(monkeypatch):
    """When SARVAM_REQUEST_INTERVAL_S=0, two requests start ~immediately
    (no global 3.2 s guard) — proves the env wiring flows into chat()."""
    e = ModelEntry(id="t", openrouter_id="t", version="t",
                  base_url="https://api.sarvam.ai",
                  api_key_env="sarvam_api_key", json_mode=False)
    monkeypatch.setenv("SARVAM_REQUEST_INTERVAL_S", "0")

    starts: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        starts.append(time.monotonic())
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"product_id":"sku_007"}'}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }, request=httpx.Request("POST", "https://x"))

    c = OpenRouterClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        min_interval_s=3.2)  # ctor default retained; per-entry env must override
    try:
        async def run():
            await c.chat(e, "p1", seed=1)
            await c.chat(e, "p2", seed=2)

        t0 = time.monotonic()
        asyncio.run(run())
        elapsed = time.monotonic() - t0
        # Without override, two back-to-back chats would burn ~3.2s of pacing.
        # With SARVAM_REQUEST_INTERVAL_S=0, the cap should be near-zero.
        assert elapsed < 0.5, f"expected near-zero pacing, got {elapsed:.2f}s"
    finally:
        asyncio.run(c.aclose())
