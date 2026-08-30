"""Remediation engine — propose → human approve/reject → mirror catalog (PRD §8.7).

Nothing applies automatically. Fixes are SCHEMA §3.8 Fix objects:
  {"field": "title"|"description"|"structured_data", "before", "after", "rationale"}

Demo catalogs draw curated proposals from demo-store/fix_proposals.json.
Uploads get template proposals with explicit [seller to confirm] markers — we never
fabricate specs for a real merchant's products (claim discipline L-2).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Catalog, Product, Remediation, Run
from app.paths import resolve_dir

DEMO_ROOT = resolve_dir("demo-store")
TODO = "[seller to confirm]"


def _rationale_for(field: str, tier: str) -> str:
    return {
        "title": "Bare/generic title gives agents nothing to match against the task.",
        "description": "Too short to carry specs; agents can't verify fit or value.",
        "structured_data": "No machine-readable price/availability — renders as "
                           "'price on request' and loses structured comparisons.",
    }[field] + (" (invisible: share CI-upper < 1/N)" if tier == "starved" else "")


def _template_proposals(row: Product) -> list[dict[str, Any]]:
    """Honest enrichment templates for uploaded listings."""
    fixes = []
    words_title = len((row.title or "").split())
    words_desc = len((row.description or "").split())
    sd = row.structured_data or {}
    if not sd.get("jsonld_present"):
        fixes.append({
            "field": "structured_data",
            "before": json.dumps(sd),
            "after": json.dumps({"jsonld_present": True,
                                 "fields_present": ["name", "price", "availability"],
                                 "price_fresh": True}),
            "rationale": _rationale_for("structured_data", row.tier),
        })
    if words_title <= 2:
        fixes.append({
            "field": "title",
            "before": row.title,
            "after": f"{row.title} — {TODO} brand / key spec / variant",
            "rationale": _rationale_for("title", row.tier),
        })
    if words_desc < 15:
        fixes.append({
            "field": "description",
            "before": row.description,
            "after": f"{row.description} {TODO}: material, dimensions/capacity, weight, "
                     "warranty or returns.",
            "rationale": _rationale_for("description", row.tier),
        })
    return fixes


def _demo_proposals(row: Product) -> list[dict[str, Any]]:
    path = DEMO_ROOT / "fix_proposals.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    prop = data.get(row.sku)
    if not prop:
        return []
    fixes = [
        {"field": "title", "before": row.title, "after": prop["title"],
         "rationale": _rationale_for("title", row.tier)},
        {"field": "description", "before": row.description,
         "after": prop["description"], "rationale": _rationale_for("description", row.tier)},
        {"field": "structured_data", "before": json.dumps(row.structured_data or {}),
         "after": json.dumps(prop["structured_data"]),
         "rationale": _rationale_for("structured_data", row.tier)},
    ]
    return fixes


async def flagged_product_ids(session: AsyncSession, catalog_id: str) -> list[str]:
    """Listings the remediation plan targets — one source of truth for the
    generator AND the dashboard's fixes_needed count.

    Primary rule: starved tier OR legibility below the 0.30 visibility threshold.
    2026-08-29: when a catalog clears that bar entirely (the common case for
    real stores whose listings are all 'medium'), we still surface the WEAKEST
    QUARTILE by legibility (capped at 10) — an always-actionable plan beats a
    clean bill of health a merchant can't act on.
    """
    rows = (
        (await session.execute(
            select(Product).where(Product.catalog_id == catalog_id)
        ))
        .scalars()
        .all()
    )
    primary = [
        p.id for p in rows
        if p.tier == "starved"
        or (p.legibility_composite is not None and p.legibility_composite < 0.30)
    ]
    if primary or not rows:
        return primary

    scored = [p for p in rows if p.legibility_composite is not None]
    if not scored:
        return []
    scored.sort(key=lambda p: p.legibility_composite)
    weakest = max(1, min(10, math.ceil(len(scored) * 0.25)))
    return [p.id for p in scored[:weakest]]


async def generate_remediations(session: AsyncSession, run_id: str) -> dict:
    run = await session.get(Run, run_id)
    if run is None:
        from app.errors import AppError
        raise AppError("E601", "run not found", status_code=404)

    rows = (
        (await session.execute(
            select(Product).where(Product.catalog_id == run.catalog_id).order_by(Product.sku)
        ))
        .scalars()
        .all()
    )
    cat = await session.get(Catalog, run.catalog_id)
    is_demo = cat is not None and cat.source in ("demo",)

    flagged_ids = set(await flagged_product_ids(session, run.catalog_id))
    created, skipped = 0, 0
    for row in rows:
        if row.id not in flagged_ids:
            skipped += 1
            continue
        existing = await session.scalar(
            select(Remediation).where(Remediation.run_id == run_id,
                                      Remediation.product_id == row.id)
        )
        if existing is not None:
            continue
        fixes = _demo_proposals(row) if is_demo else _template_proposals(row)
        session.add(Remediation(run_id=run_id, product_id=row.id, fixes=fixes,
                                status="pending"))
        created += 1
    await session.commit()
    return {"run_id": run_id, "created": created, "not_flagged": skipped}


async def build_mirror_catalog(session: AsyncSession, run_id: str,
                               reviewed_by: str = "merchant") -> str:
    """Apply approved fixes into a mirror catalog; E401 unless every row reviewed."""
    from app.errors import AppError

    run = await session.get(Run, run_id)
    if run is None:
        raise AppError("E601", "run not found", status_code=404)

    rems = (
        (await session.execute(select(Remediation).where(Remediation.run_id == run_id)))
        .scalars()
        .all()
    )
    pending = [r for r in rems if r.status == "pending"]
    if pending:
        raise AppError("E401", f"{len(pending)} remediation(s) still pending review — "
                               "approve or reject each before mirroring", status_code=409)
    approved = [r for r in rems if r.status == "approved"]

    # version = parent +1 per SC-2
    parent_cat = await session.get(Catalog, run.catalog_id)
    mirror = Catalog(
        merchant_id=parent_cat.merchant_id,
        source="mirror",
        parent_catalog_id=parent_cat.id,
        version=(parent_cat.version or 1) + 1,
    )
    session.add(mirror)
    await session.flush()

    by_pid = {r.product_id: r for r in approved}
    products = (
        (await session.execute(
            select(Product).where(Product.catalog_id == run.catalog_id)
        ))
        .scalars()
        .all()
    )
    now_fixed = 0
    for p in products:
        new_p = Product(
            catalog_id=mirror.id, sku=p.sku, title=p.title, price_inr=p.price_inr,
            description=p.description, image_url=p.image_url, page_url=p.page_url,
            tier=p.tier, structured_data=dict(p.structured_data or {}),
            legibility_composite=p.legibility_composite,
        )
        rem = by_pid.get(p.id)
        if rem is not None:
            for fix in rem.fixes:
                field = fix["field"]
                if field == "title":
                    new_p.title = fix["after"]
                elif field == "description":
                    new_p.description = fix["after"]
                elif field == "structured_data":
                    try:
                        new_p.structured_data = json.loads(fix["after"])
                    except json.JSONDecodeError:
                        pass
            rem.applied_at = datetime.now(timezone.utc)
            now_fixed += 1
        session.add(new_p)
    await session.commit()
    return mirror.id
