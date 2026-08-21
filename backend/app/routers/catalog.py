"""Catalog read endpoints — GET /catalog, GET /catalog/{sku} (SCHEMA §7.1)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Catalog, Product
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


async def _latest_catalog(session: AsyncSession) -> Catalog:
    catalog = await session.scalar(
        select(Catalog).where(Catalog.source == "demo").order_by(Catalog.created_at.desc())
    )
    if catalog is None:
        raise AppError("E601", "no demo catalog loaded — run make seed-demo", status_code=404)
    return catalog


@router.get("/catalog")
async def get_catalog(order: str = "sku",
                      session: AsyncSession = Depends(get_session)) -> dict:
    catalog = await _latest_catalog(session)
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
async def get_product(sku: str, session: AsyncSession = Depends(get_session)) -> dict:
    catalog = await _latest_catalog(session)
    row = await session.scalar(
        select(Product).where(Product.catalog_id == catalog.id, Product.sku == sku)
    )
    if row is None:
        raise AppError("E601", f"product not found: {sku}", status_code=404)
    return _canonical(row)
