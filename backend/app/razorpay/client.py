"""Razorpay test-mode client — payment links + webhook signature verification.

Secrets stay server-side (PRD §8.8): the frontend/MCP/agent processes never touch
key_secret. All calls go through an injectable httpx client so tests are hermetic.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

import httpx

API_BASE = "https://api.razorpay.com/v1"


@dataclass
class PaymentLink:
    id: str
    short_url: str
    amount_inr: int
    status: str


def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """X-Razorpay-Signature = HMAC_SHA256(webhook_body, webhook_secret)."""
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class RazorpayError(Exception):
    pass


class RazorpayClient:
    def __init__(self, key_id: str, key_secret: str,
                 http_client: httpx.AsyncClient | None = None) -> None:
        self._auth = (key_id, key_secret)
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def create_payment_link(self, *, amount_inr: int, reference_id: str,
                                  description: str, customer_name: str = "Audit Viewer",
                                  idempotency_key: str | None = None) -> PaymentLink:
        payload = {
            "amount": amount_inr * 100,  # paise
            "currency": "INR",
            "accept_partial": False,
            "reference_id": reference_id,
            "description": description[:200],
            "customer": {"name": customer_name},
            "notify": {"sms": False, "email": False},
        }
        headers = {}
        if idempotency_key:
            headers["X-Razorpay-Idempotency-Key"] = idempotency_key
        resp = await self._client.post(f"{API_BASE}/payment_links", json=payload,
                                       auth=self._auth, headers=headers)
        if resp.status_code >= 400:
            raise RazorpayError(f"payment link failed ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        return PaymentLink(id=data["id"], short_url=data.get("short_url", ""),
                           amount_inr=amount_inr, status=data.get("status", "created"))

    async def fetch_payment_link(self, link_id: str) -> PaymentLink:
        """GET /v1/payment_links/{id} — replays use this so short_url stays fresh."""
        resp = await self._client.get(f"{API_BASE}/payment_links/{link_id}",
                                      auth=self._auth)
        if resp.status_code >= 400:
            raise RazorpayError(
                f"payment link fetch failed ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        return PaymentLink(id=data["id"], short_url=data.get("short_url", ""),
                           amount_inr=int(data.get("amount", 0)) // 100,  # paise → ₹
                           status=data.get("status", "created"))
