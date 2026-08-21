"""Agent checkout proof — a scripted autonomous agent buying from the audited catalog.

Flow (TECHSPEC §12): choose best-value product from (preferably) the MIRROR catalog →
create Razorpay test-mode payment link → print hand-off URL. The human completes payment;
the webhook flips status → F8 badge closes the agent-to-ledger loop.

Run: python -m scripts.agent_checkout <run_id>
"""
import asyncio
import sys

from sqlalchemy import select


def _pick_product(products: list) -> object:
    """Value heuristic: structured-complete listings ranked by price among in-stock rich/
    medium tier — deliberately simple, deterministic, and explainable."""
    candidates = [p for p in products if p.price_inr and p.tier in ("rich", "medium")]
    if not candidates:
        candidates = [p for p in products if p.price_inr]
    if not candidates:
        raise SystemExit("no purchasable product found")
    return max(candidates, key=lambda p: (p.legibility_composite or 0) / (p.price_inr or 1))


async def main(run_id: str) -> None:
    from app.config import get_settings
    from app.db.models import Catalog, Product, Run
    from app.db.session import get_sessionmaker
    from app.razorpay.client import RazorpayClient

    s = get_settings()
    maker = get_sessionmaker()

    async with maker() as session:
        run = await session.get(Run, run_id)
        if run is None:
            raise SystemExit(f"run {run_id} not found")

        catalog_id = run.catalog_id
        # an agent should buy from the FIXED catalog when one exists
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

    if not s.razorpay_key_id or not s.razorpay_key_secret:
        print("[agent] RAZORPAY_KEY_ID/SECRET missing — stopping before link creation.")
        print(f"[agent] would purchase: {pick.sku} for ₹{pick.price_inr}")
        return

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
    print(f"[human] complete the (test-mode) payment here: {link.short_url}")
    print("[webhook] payment_link.captured will flip the F8 badge automatically")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m scripts.agent_checkout <run_id>")
    asyncio.run(main(sys.argv[1]))
