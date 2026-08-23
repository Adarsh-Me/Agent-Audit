"""Razorpay checkout smoke — the FULL Day-3 flow, end to end (FINALSPRINT Tier 1).

Steps: keys check → pick product (mirror-aware) → create bounded test-mode payment
link → print hand-off URL → poll webhook status until captured → report the F8
badge flip. Exits non-zero on any policy refusal (E503/E504/E505) so CI/demo
scripts can distinguish "flow broken" from "payment not completed yet".

Run:  python -m scripts.razorpay_smoke <run_id> [--timeout 300]

Before first use (see Docs/RAZORPAY_SETUP.md):
  1. RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET (rzp_test_…) in backend/.env
  2. ngrok tunnel + RAZORPAY_WEBHOOK_SECRET for the capture half of the loop
     (without the webhook the poller still works via /payments fetch fallback… no —
     status flips only via webhook; without it this poll times out by design).
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select


def _pick_product(products: list) -> object:
    """Value heuristic (same as scripts/agent_checkout.py): structured-complete
    listings ranked by legibility-per-rupee among rich/medium tier."""
    candidates = [p for p in products if p.price_inr and p.tier in ("rich", "medium")]
    if not candidates:
        candidates = [p for p in products if p.price_inr]
    if not candidates:
        raise SystemExit("no purchasable product found")
    return max(candidates, key=lambda p: (p.legibility_composite or 0) / (p.price_inr or 1))


async def main(run_id: str, timeout_s: int) -> int:
    from app.config import get_settings
    from app.db.models import Catalog, Product, Run
    from app.db.session import get_sessionmaker
    from app.razorpay.client import RazorpayClient

    s = get_settings()

    print("=== AgentAudit Razorpay smoke ===")
    if not s.razorpay_key_id or not s.razorpay_key_secret:
        print("[setup] RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET missing from backend/.env")
        print("[setup] create a test account → Dashboard → Settings → API Keys, then:")
        print("[setup]   RAZORPAY_KEY_ID=rzp_test_xxx")
        print("[setup]   RAZORPAY_KEY_SECRET=xxx")
        print("[setup] see Docs/RAZORPAY_SETUP.md for the full 10-minute walkthrough")
        return 2
    if not s.razorpay_key_id.startswith("rzp_test_"):
        print(f"[refuse] E505 test-mode-only policy: key must start rzp_test_, got "
              f"{s.razorpay_key_id[:8]}… — live keys are refused by design")
        return 3

    maker = get_sessionmaker()
    async with maker() as session:
        run = await session.get(Run, run_id)
        if run is None:
            raise SystemExit(f"run {run_id} not found")
        catalog_id = run.catalog_id
        mirror = (await session.execute(
            select(Catalog)
            .where(Catalog.source == "mirror", Catalog.parent_catalog_id == catalog_id)
            .order_by(Catalog.version.desc())
        )).scalars().first()
        if mirror is not None:
            catalog_id = mirror.id
            print(f"[agent] using remediated catalog {mirror.id} (v{mirror.version})")
        products = (await session.execute(
            select(Product).where(Product.catalog_id == catalog_id))).scalars().all()

    pick = _pick_product(list(products))
    print(f"[agent] catalog scanned: {len(products)} listings")
    print(f"[agent] selected: {pick.sku} — {pick.title} @ ₹{pick.price_inr}")
    print("[agent] reason: best data-completeness per rupee among comparable listings")

    if pick.price_inr > s.max_agent_spend_inr:
        print(f"[refuse] E503 spend cap: ₹{pick.price_inr} > MAX_AGENT_SPEND_INR "
              f"₹{s.max_agent_spend_inr}")
        return 3

    rp = RazorpayClient(s.razorpay_key_id, s.razorpay_key_secret)
    try:
        idem = f"agentaudit:{run_id}:{pick.sku}"
        link = await rp.create_payment_link(
            amount_inr=pick.price_inr,
            reference_id=idem,
            description=f"AgentAudit checkout proof — {pick.title}",
            idempotency_key=idem,
        )
    finally:
        await rp.aclose()

    print(f"[agent] payment link created: {link.id}")
    print()
    print(f"[human] complete the TEST payment here:\n        {link.short_url}")
    print("[human] card 4111 1111 1111 1111 · any future expiry · any CVV")
    print("[human] (test mode — no real money moves)")
    print()

    if not s.razorpay_webhook_secret:
        print("[webhook] RAZORPAY_WEBHOOK_SECRET not set — cannot verify capture.")
        print("[webhook] set up the tunnel + webhook (Docs/RAZORPAY_SETUP.md) and re-run.")
        return 2

    print(f"[poll] waiting for payment_link.captured (timeout {timeout_s}s)…")
    from app.db.models import Payment

    maker2 = get_sessionmaker()
    waited = 0
    while waited < timeout_s:
        await asyncio.sleep(5)
        waited += 5
        async with maker2() as session:
            rows = (await session.execute(
                select(Payment).where(Payment.run_id == run_id)
                .order_by(Payment.id.desc())
            )).scalars().all()
        latest = rows[0] if rows else None
        if latest and latest.status == "captured":
            print(f"[badge] ✓ captured — payment {latest.razorpay_link_id} at "
                  f"{latest.captured_at.isoformat() if latest.captured_at else '?'}")
            print("[badge] agent-to-ledger loop closed. F8 badge would now read:")
            print(f"[badge]   \"Agent checkout verified ✓ {latest.razorpay_link_id}\"")
            return 0
        if latest and latest.status == "failed":
            print("[fail] payment failed — retry the test payment (link is idempotent)")
            return 1
        if waited % 30 == 0:
            print(f"[poll] …{waited}s elapsed, status={latest.status if latest else 'created'}")

    print("[timeout] no capture recorded — webhook not received?")
    print("[timeout] check: tunnel up? webhook URL matches? RAZORPAY_WEBHOOK_SECRET correct?")
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.run_id, args.timeout)))
