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
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt4o-mini": (0.15, 0.60),
    "gemini-flash": (0.075, 0.30),
    "claude-haiku": (0.80, 4.00),
    "gpt4o": (2.50, 10.00),
    "gemini-pro": (1.25, 5.00),
}


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
                 api_key: str | None = None, concurrency: int = ENGINE_CONCURRENCY) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=60.0)
        self._api_key = api_key if api_key is not None else get_settings().openrouter_api_key
        self._semaphore = asyncio.Semaphore(concurrency)
        self.breakers: dict[str, CircuitBreaker] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    def _breaker_for(self, openrouter_id: str) -> CircuitBreaker:
        return self.breakers.setdefault(openrouter_id, CircuitBreaker())

    async def chat(self, entry: ModelEntry, prompt: str, seed: int, *,
                   temperature: float = 1.0, system_feedback: str | None = None) -> LLMResponse:
        """One completion. Retries on transport/5xx/timeouts with backoff.

        Raises ProviderError on circuit-open or exhausted retries.
        """
        breaker = self._breaker_for(entry.openrouter_id)
        if not breaker.allow():
            raise ProviderError(f"circuit breaker open for {entry.openrouter_id}")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        messages = [{"role": "user", "content": prompt}]
        if system_feedback:
            messages.append({"role": "user", "content": system_feedback})
        payload: dict = {
            "model": entry.openrouter_id,
            "messages": messages,
            "temperature": temperature,
        }
        if entry.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if entry.seed_supported:
            payload["seed"] = seed

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                async with self._semaphore:
                    t0 = time.monotonic()
                    resp = await self._client.post(OPENROUTER_URL, json=payload, headers=headers)
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
                content = data["choices"][0]["message"]["content"]
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
            except (httpx.TransportError, httpx.TimeoutException, ProviderError,
                    KeyError, ValueError) as exc:
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
