"""Catalog read endpoints — GET /catalogs, GET /catalog, GET /catalog/{sku}.

`?catalog_id=` pins a specific store's catalog; without it the most recently
added non-demo catalog wins (imported store / CSV upload / mirror — i.e. the
store you actually ran), falling back to the demo seed on fresh deployments.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Catalog, Merchant, Product
from app.db.session import get_session
from app.errors import AppError

router = APIRouter()


def _canonical(row: Product) -> dict:
    return {
        "id": row.sku,
        "title": row.title,
        "price_inr": row.price_inr,
        "description": row.description,
        "image_url": row.image_url,
        "page_url": row.page_url,
        "tier": row.tier,
        "structured_data": row.structured_data,
    }


async def _resolve_catalog(session: AsyncSession, catalog_id: str | None) -> Catalog:
    if catalog_id:
        catalog = await session.get(Catalog, catalog_id)
        if catalog is None:
            raise AppError("E601", f"catalog not found: {catalog_id}", status_code=404)
        return catalog
    # newest user-added catalog first; fresh deployments fall through to demo
    for demo_only in (False, True):
        query = select(Catalog).order_by(Catalog.created_at.desc())
        query = (
            query.where(Catalog.source == "demo")
            if demo_only
            else query.where(Catalog.source != "demo")
        )
        catalog = await session.scalar(query)
        if catalog is not None:
            return catalog
    raise AppError(
        "E601", "no catalog yet — import a store, upload a CSV, or run make seed-demo",
        status_code=404,
    )


@router.get("/catalogs")
async def list_catalogs(session: AsyncSession = Depends(get_session)) -> dict:
    """Every known catalog, newest first — powers the /catalog store switcher."""
    rows = (
        await session.execute(
            select(Catalog, Merchant.name)
            .join(Merchant, Merchant.id == Catalog.merchant_id, isouter=True)
            .order_by(Catalog.created_at.desc())
        )
    ).all()
    catalogs = []
    for cat, merchant_name in rows:
        count = await session.scalar(
            select(func.count()).select_from(Product).where(Product.catalog_id == cat.id)
        )
        catalogs.append(
            {
                "catalog_id": cat.id,
                "source": cat.source,
                "merchant": merchant_name,
                "product_count": int(count or 0),
                "created_at": cat.created_at.isoformat() if cat.created_at else None,
            }
        )
    return {"catalogs": catalogs}


@router.get("/catalog")
async def get_catalog(order: str = "sku",
                      catalog_id: str | None = None,
                      session: AsyncSession = Depends(get_session)) -> dict:
    catalog = await _resolve_catalog(session, catalog_id)
    rows = (
        (await session.execute(
            select(Product).where(Product.catalog_id == catalog.id).order_by(Product.sku)
        ))
        .scalars()
        .all()
    )
    items = [_canonical(r) for r in rows]
    if order == "baseline":
        # demo fixture block order ([rich, medium, starved, medium]×10) drives the F4
        # heat-map axis; unknown skus (uploads/mirrors) keep sku-sorted tail order
        from app.engine.runner import load_baseline_order_fixture

        base = [s for s in load_baseline_order_fixture()]
        rank = {sku: i for i, sku in enumerate(base)}
        items.sort(key=lambda p: rank.get(p["id"], len(base)))
    return {
        "catalog_id": catalog.id,
        "source": catalog.source,
        "version": catalog.version,
        "count": len(items),
        "products": items,
    }


@router.get("/catalog/{sku}")
async def get_product(sku: str,
                      catalog_id: str | None = None,
                      session: AsyncSession = Depends(get_session)) -> dict:
    catalog = await _resolve_catalog(session, catalog_id)
    row = await session.scalar(
        select(Product).where(Product.catalog_id == catalog.id, Product.sku == sku)
    )
    if row is None:
        raise AppError("E601", f"product not found: {sku}", status_code=404)
    return _canonical(row)
