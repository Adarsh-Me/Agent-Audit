"""Diagnose a payment-link attempt: fetch link state + embedded payment attempts.

Usage: python scripts/rzp_attempt_check.py [plink_id]

Razorpay's GET /v1/payments does NOT accept a payment_link_id filter (the
field must be 17 chars — a payment id, not a plink_* id); the attempts ride
on the payment-link fetch response itself under `payments`.
"""
import asyncio
import base64
import json
import sys

import httpx

from app.config import get_settings


async def main() -> None:
    s = get_settings()
    auth = base64.b64encode(
        f"{s.razorpay_key_id}:{s.razorpay_key_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    link_id = sys.argv[1] if len(sys.argv) > 1 else "plink_TTM8L1vq0TeYsr"
    async with httpx.AsyncClient(timeout=30.0) as cx:
        r1 = await cx.get(f"https://api.razorpay.com/v1/payment_links/{link_id}",
                          headers=headers)
    if r1.status_code != 200:
        print("link:", r1.status_code, r1.text[:300])
        return
    body = r1.json()
    print("link:", json.dumps(
        {k: body.get(k) for k in ("id", "status", "amount", "updated_at",
                                  "short_url", "reference_id")},
        indent=1))
    for p in body.get("payments") or []:
        print("attempt:", json.dumps({
            "id": p.get("id"), "status": p.get("status"),
            "method": p.get("method"), "vpa": p.get("vpa"),
            "amount": p.get("amount"), "captured": p.get("captured"),
            "error_description": (p.get("error_description") or "")[:160],
            "created_at": p.get("created_at"),
        }, indent=1))


asyncio.run(main())
