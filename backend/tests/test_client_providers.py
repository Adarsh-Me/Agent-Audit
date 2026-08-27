"""Alternate-provider routing tests — openai-style alt-base + anthropic-style.

No network: MockTransport asserts URL (incl. trailing-/v1 dedup), headers,
payload shape, and response parsing for each wire format. Found while wiring
mimo-v2.5-free on OpenCode Zen (2026-08-25), deepseek-v4-flash on tokenbom
(2026-08-26, same-day swap), and x-preview-f-free back on OpenCode Zen
(2026-08-26, current pin).

2026-08-27: provider swapped to Sarvam 105b (api.sarvam.ai, OpenAI-style).
Routing assertions (URL dedup, header, payload) still hold — the engine
imports the SDK only as a development-time helper; production traffic is
plain HTTP via the existing base_url/api_key_env machinery.
"""
import json

import httpx

from app.config import get_settings
from app.engine.client import OpenRouterClient
from app.engine.model_registry import ModelEntry


def _entry(**kw) -> ModelEntry:
    base = dict(id="xpreview", openrouter_id="x-preview-f-free",
                version="x-preview-f-free@2026-08-26")
    base.update(kw)
    return ModelEntry(**base)


async def test_openai_style_base_with_trailing_v1_is_not_doubled():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok":true}'}}],
            "usage": {"prompt_tokens": 261, "completion_tokens": 6},
        }, request=httpx.Request("POST", "https://x"))

    client = OpenRouterClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        min_interval_s=0)
    entry = _entry(base_url="https://opencode.ai/zen/v1",
                   api_key_env="opencode_zen_api_key")
    try:
        out = await client.chat(entry, "prompt", seed=1)
        # exactly one /v1 — a base that already ends with it must not double
        assert str(calls[0].url) == "https://opencode.ai/zen/v1/chat/completions"
        assert out.content == '{"ok":true}'
        assert req_headers_bearer(calls[0]) == get_settings().opencode_zen_api_key
        body = json.loads(calls[0].content)
        assert "reasoning" not in body  # OpenRouter-only extension dropped
        assert body["response_format"] == {"type": "json_object"}
        assert body["max_tokens"] == 3500  # reasoning-model headroom
    finally:
        await client.aclose()


def req_headers_bearer(request: httpx.Request) -> str:
    return request.headers["Authorization"].removeprefix("Bearer ")


async def test_anthropic_style_url_headers_payload_and_parse():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"content": [
            {"type": "text", "text": '{"product_id": "sku_007"}'}],
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }, request=httpx.Request("POST", "https://x"))

    client = OpenRouterClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        min_interval_s=0)
    try:
        out = await client.chat(_entry(
            base_url="https://gw-anthropic.example.com", endpoint="anthropic"),
            "prompt", seed=1)
        assert out.content == '{"product_id": "sku_007"}'
        assert out.prompt_tokens == 11 and out.completion_tokens == 7
        req = calls[0]
        assert str(req.url) == "https://gw-anthropic.example.com/v1/messages"
        assert "Authorization" not in req.headers or not req.headers["Authorization"]
        body = json.loads(req.content)
        # no OpenAI/OpenRouter-only fields on the anthropic wire
        assert "response_format" not in body and "reasoning" not in body
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
        out = await client.chat(_entry(base_url="https://gw-anthropic.example.com",
                                       endpoint="anthropic"), "p", seed=1)
        assert out.content == '{"a":1}'
    finally:
        await client.aclose()


async def test_openai_style_alt_base_without_v1_appends_it():
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
        assert str(calls[0].url) == "https://gw.example.com/v1/chat/completions"
    finally:
        await client.aclose()


async def test_sarvam_endpoint_uses_openai_style_and_sarvam_key():
    """2026-08-27 owner swap: Sarvam 105b is OpenAI-style chat.completions over
    https://api.sarvam.ai/v1/chat/completions with the sarvam_api_key header."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"product_id": "sku_007"}'}}],
            "usage": {"prompt_tokens": 261, "completion_tokens": 6},
        }, request=httpx.Request("POST", "https://x"))

    client = OpenRouterClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        min_interval_s=0)
    entry = _entry(openrouter_id="sarvam-105b-conversations",
                   base_url="https://api.sarvam.ai",
                   api_key_env="sarvam_api_key")
    try:
        out = await client.chat(entry, "prompt", seed=1)
        assert out.content == '{"product_id": "sku_007"}'
        assert str(calls[0].url) == "https://api.sarvam.ai/v1/chat/completions"
        assert req_headers_bearer(calls[0]) == get_settings().sarvam_api_key
        body = json.loads(calls[0].content)
        assert body["model"] == "sarvam-105b-conversations"
        # OpenAI-style + json mode + no OpenRouter reasoning extension
        assert "reasoning" not in body
        assert body["response_format"] == {"type": "json_object"}
    finally:
        await client.aclose()
