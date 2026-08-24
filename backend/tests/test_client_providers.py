"""Alternate-provider routing tests — AiHubMix anthropic-style + openai-style alt-base.

No network: MockTransport asserts URL, headers, payload shape, and response
parsing for each wire format. Found while wiring coding-glm-5-turbo-free
(2026-08-24).
"""
import json

import httpx
import pytest

from app.config import get_settings
from app.engine.client import OpenRouterClient
from app.engine.model_registry import ModelEntry


def _entry(**kw) -> ModelEntry:
    return ModelEntry(id="glm", openrouter_id="coding-glm-5-turbo-free",
                      version="coding-glm-5-turbo-free@2026-08-24", **kw)


def _anth_body(text='{"product_id": "sku_007"}', tin=11, tout=7) -> dict:
    return {"content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": tin, "output_tokens": tout}}


async def test_anthropic_style_url_headers_payload_and_parse():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=_anth_body(),
                              request=httpx.Request("POST", "https://x"))

    client = OpenRouterClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        min_interval_s=0)
    try:
        out = await client.chat(_entry(
            base_url="https://aihubmix.com", endpoint="anthropic",
            api_key_env="aihubmix_api_key"), "prompt", seed=1)
        assert out.content == '{"product_id": "sku_007"}'
        assert out.prompt_tokens == 11 and out.completion_tokens == 7
        req = calls[0]
        assert str(req.url) == "https://aihubmix.com/v1/messages"
        assert req.headers["x-api-key"] == get_settings().aihubmix_api_key
        assert req.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(req.content)
        # no OpenAI/OpenRouter-only fields on the anthropic wire
        assert "response_format" not in body and "reasoning" not in body
        assert body["model"] == "coding-glm-5-turbo-free"
        assert body["max_tokens"] == 3500
    finally:
        await client.aclose()


async def test_anthropic_content_blocks_concatenated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [
            {"type": "text", "text": '{"a":'},
            {"type": "tool_use", "id": "t"},  # non-text block must be skipped
            {"type": "text", "text": "1}"},
        ], "usage": {}}, request=httpx.Request("POST", "https://x"))

    client = OpenRouterClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        min_interval_s=0)
    try:
        out = await client.chat(_entry(base_url="https://aihubmix.com",
                                       endpoint="anthropic"), "p", seed=1)
        assert out.content == '{"a":1}'
    finally:
        await client.aclose()


async def test_openai_style_alt_base_drops_reasoning_keeps_json_mode():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }, request=httpx.Request("POST", "https://x"))

    client = OpenRouterClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        min_interval_s=0)
    entry = _entry(base_url="https://gw.example.com")  # endpoint defaults to openai
    try:
        await client.chat(entry, "prompt", seed=1)
        req = calls[0]
        assert str(req.url) == "https://gw.example.com/v1/chat/completions"
        assert req.headers["Authorization"].startswith("Bearer ")
        body = json.loads(req.content)
        # reasoning is an OpenRouter extension — alternate gateways may reject it
        assert "reasoning" not in body
        assert body["response_format"] == {"type": "json_object"}
    finally:
        await client.aclose()
