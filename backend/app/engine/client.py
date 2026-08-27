"""OpenRouter async client — TECHSPEC §7.4 execution semantics.

- 10 parallel calls per provider (semaphore)
- 3 attempts, backoff 1s/2s/4s; on parse failure the runner appends RETRY_FEEDBACK
- circuit breaker: opens after 10 consecutive failures per provider, 60 s cooldown,
  half-open probe
- cost ledger: running token accounting priced per model; run aborts at COST_CAP_USD
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Final

import httpx

from app.config import get_settings
from app.constants import (
    CIRCUIT_BREAKER_COOLDOWN_S,
    CIRCUIT_BREAKER_THRESHOLD,
    ENGINE_CONCURRENCY,
    RETRY_BACKOFF_S,
)
from app.engine.model_registry import ModelEntry

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# USD per 1M tokens (input, output) — engine ids per SCHEMA §2.3.
# SINGLE-MODEL MODE 2026-08-27: Sarvam 105b via api.sarvam.ai (OpenAI-style
# chat.completions). Owner hasn't published a free tier; keep ledger rows
# present so the (1.0, 1.0) fallback doesn't bill phantom cost. UPDATE these
# numbers when pricing is confirmed — they affect the COST_CAP_USD abort.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "sarvam-105b": (1.0, 1.0),            # TBD — owner to confirm Sarvam rates
    "sarvam-105b-flagship": (1.0, 1.0),  # TBD — same; flagship reuses the model
}

# Free-tier endpoints allow ~20 requests/min; a triple-429 trial aborts the whole
# run to partial (runner catches ProviderError), so pace call STARTS globally to
# stay under the cap with headroom. Latency (~seconds) hides most of this interval,
# so wall-clock impact is minimal for the sequential trial loop.
MIN_REQUEST_INTERVAL_S: Final = 3.2

# Wall-clock ceiling per single completion attempt (see wait_for in chat()).
PER_ATTEMPT_CAP_S: Final = 75.0


def estimate_cost_usd(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = PRICING_USD_PER_MTOK.get(model_id, (1.0, 1.0))
    return prompt_tokens / 1e6 * pin + completion_tokens / 1e6 * pout


class ProviderError(Exception):
    pass


@dataclass
class CircuitBreaker:
    threshold: int = CIRCUIT_BREAKER_THRESHOLD
    cooldown_s: float = CIRCUIT_BREAKER_COOLDOWN_S
    consecutive_failures: int = 0
    opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.cooldown_s:
            # half-open: let a single probe through
            self.opened_at = None
            self.consecutive_failures = self.threshold - 1
            return True
        return False

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.opened_at = None

    def record_failure(self) -> bool:
        """Returns True if this failure just opened the breaker."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.threshold and self.opened_at is None:
            self.opened_at = time.monotonic()
            return True
        return False

    @property
    def open(self) -> bool:
        return self.opened_at is not None


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int
    model_version: str


@dataclass
class CostLedger:
    cap_usd: float = 30.0
    total_usd: float = 0.0
    events: list[dict] = field(default_factory=list)

    def add(self, model_id: str, cost: float) -> None:
        self.total_usd += cost
        self.events.append({"model": model_id, "cost_usd": round(cost, 6), "total_usd": round(self.total_usd, 6)})

    @property
    def capped(self) -> bool:
        return self.total_usd >= self.cap_usd


class OpenRouterClient:
    def __init__(self, http_client: httpx.AsyncClient | None = None,
                 api_key: str | None = None, concurrency: int = ENGINE_CONCURRENCY,
                 min_interval_s: float | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=60.0)
        self._api_key = api_key if api_key is not None else get_settings().openrouter_api_key
        self._semaphore = asyncio.Semaphore(concurrency)
        self.breakers: dict[str, CircuitBreaker] = {}
        self._min_interval = (MIN_REQUEST_INTERVAL_S if min_interval_s is None
                              else min_interval_s)
        self._last_start = 0.0

    async def _pace(self) -> None:
        """Global min-interval between request starts (free-tier rate-cap guard)."""
        if self._min_interval <= 0:
            return
        while True:
            now = time.monotonic()
            wait = self._last_start + self._min_interval - now
            if wait <= 0:
                self._last_start = now
                return
            await asyncio.sleep(wait)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _breaker_for(self, openrouter_id: str) -> CircuitBreaker:
        return self.breakers.setdefault(openrouter_id, CircuitBreaker())

    def _route_for(self, entry: ModelEntry) -> tuple[str, dict[str, str], str]:
        """Resolve (url, headers, wire-style) for a model entry.

        Empty base_url → OpenRouter OpenAI-format. Alternate providers pick their
        format via entry.endpoint; anthropic = /v1/messages with x-api-key.
        """
        settings = get_settings()
        key_field = entry.api_key_env or "openrouter_api_key"
        api_key = getattr(settings, key_field, "") or self._api_key
        if not entry.base_url:
            return OPENROUTER_URL, {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }, "openai"
        # Tolerate bases that already carry /v1 (e.g. https://opencode.ai/zen/v1)
        base = entry.base_url.rstrip("/")
        v1 = "" if base.endswith("/v1") else "/v1"
        if entry.endpoint == "anthropic":
            return (f"{base}{v1}/messages", {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }, "anthropic")
        return (f"{base}{v1}/chat/completions", {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }, "openai")

    async def chat(self, entry: ModelEntry, prompt: str, seed: int, *,
                   temperature: float = 1.0, system_feedback: str | None = None) -> LLMResponse:
        """One completion. Retries on transport/5xx/timeouts with backoff.

        Raises ProviderError on circuit-open or exhausted retries.
        """
        breaker = self._breaker_for(f"{entry.base_url or 'openrouter'}::{entry.openrouter_id}")
        if not breaker.allow():
            raise ProviderError(f"circuit breaker open for {entry.openrouter_id}")

        url, headers, style = self._route_for(entry)
        messages = [{"role": "user", "content": prompt}]
        if system_feedback:
            messages.append({"role": "user", "content": system_feedback})
        if style == "anthropic":
            # Anthropic /v1/messages: no response_format (JSON enforced by the
            # prompt itself), no seed, no OpenRouter reasoning extension.
            payload: dict = {
                "model": entry.openrouter_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 3500,
            }
        else:
            payload = {
                "model": entry.openrouter_id,
                "messages": messages,
                "temperature": temperature,
                # reasoning-style endpoints otherwise burn minutes (and their whole
                # output budget) on chain-of-thought before the JSON: measured
                # 11.8s/452tok -> 2.4s/52tok on a catalog-size prompt (2026-08-22)
                "max_tokens": 3500,
            }
            if not entry.base_url:
                # OpenRouter-specific extension — alternate gateways may reject it.
                payload["reasoning"] = {"effort": "low", "exclude": True}
            if entry.json_mode:
                payload["response_format"] = {"type": "json_object"}
            if entry.seed_supported:
                payload["seed"] = seed

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                async with self._semaphore:
                    await self._pace()
                    t0 = time.monotonic()
                    # Hard wall-clock cap: a live-fire stall (2026-08-22, nemotron
                    # block) showed a request can hang PAST httpx's read/connect
                    # timeouts — wait_for guarantees the attempt terminates so the
                    # run always makes forward progress.
                    resp = await asyncio.wait_for(
                        self._client.post(url, json=payload, headers=headers),
                        timeout=PER_ATTEMPT_CAP_S,
                    )
                    latency_ms = int((time.monotonic() - t0) * 1000)
                if resp.status_code >= 500:
                    raise ProviderError(f"provider 5xx: {resp.status_code}")
                if resp.status_code == 429:
                    raise ProviderError("provider rate limited")
                if resp.status_code >= 400:
                    # 4xx (other than 429) is a hard error — no retry helps
                    breaker.record_failure()
                    raise ProviderError(f"provider {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                if style == "anthropic":
                    # content is a list of blocks; keep the text ones in order
                    try:
                        blocks = data["content"]
                        content = "".join(
                            b.get("text", "") for b in blocks
                            if isinstance(b, dict) and b.get("type") == "text")
                    except (KeyError, TypeError) as exc:
                        raise ProviderError("malformed completion payload") from exc
                    if not isinstance(content, str) or not content.strip():
                        raise ProviderError("empty content (null/blank message)")
                    usage = data.get("usage") or {}
                    ptok = int(usage.get("input_tokens") or 0)
                    ctok = int(usage.get("output_tokens") or 0)
                else:
                    try:
                        message = data["choices"][0]["message"]
                    except (KeyError, IndexError, TypeError) as exc:
                        raise ProviderError("malformed completion payload") from exc
                    content = message.get("content")
                    if not isinstance(content, str) or not content.strip():
                        # reasoning-style models intermittently return content=null with
                        # everything in `reasoning` — retryable, not a crash
                        raise ProviderError("empty content (null/blank message)")
                    usage = data.get("usage") or {}
                    ptok = int(usage.get("prompt_tokens") or 0)
                    ctok = int(usage.get("completion_tokens") or 0)
                cost = estimate_cost_usd(entry.id, ptok, ctok)
                breaker.record_success()
                return LLMResponse(
                    content=content,
                    prompt_tokens=ptok,
                    completion_tokens=ctok,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    model_version=entry.version,
                )
            except (httpx.TransportError, httpx.TimeoutException, TimeoutError,
                    ProviderError, KeyError, ValueError) as exc:
                last_exc = exc
                if isinstance(exc, ProviderError) and "provider 4" in str(exc):
                    break  # non-retryable
                if attempt < 2:
                    await asyncio.sleep(RETRY_BACKOFF_S[attempt])
        just_opened = breaker.record_failure()
        raise ProviderError(
            f"retries exhausted for {entry.openrouter_id}: {last_exc}"
            + (" [circuit opened]" if just_opened else "")
        ) from last_exc
