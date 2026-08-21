"""Demo loader — loads demo-store/products.json into catalogs(source='demo') + products.

Idempotent: reuses the latest demo catalog row and replaces its products, so runs that
reference the catalog keep a stable catalog_id across reseeds (TECHSPEC T1.5).
"""
import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Catalog, Merchant, Product

DEMO_ROOT = Path(__file__).resolve().parents[3] / "demo-store"
DEMO_MERCHANT_NAME = "AgentAudit Demo Merchant"
DEMO_DEFAULT_GMV_INR = 800_000


def load_fixture() -> dict:
    path = DEMO_ROOT / "products.json"
    if not path.exists():
        raise FileNotFoundError("demo-store/products.json missing — run: python demo-store/generate.py")
    return json.loads(path.read_text(encoding="utf-8"))


async def load_demo_catalog(session: AsyncSession) -> str:
    fixture = load_fixture()

    merchant = await session.scalar(select(Merchant).where(Merchant.name == DEMO_MERCHANT_NAME))
    if merchant is None:
        merchant = Merchant(name=DEMO_MERCHANT_NAME, gmv_monthly_inr=DEMO_DEFAULT_GMV_INR)
        session.add(merchant)
        await session.flush()

    catalog = await session.scalar(
        select(Catalog).where(Catalog.source == "demo").order_by(Catalog.created_at.desc())
    )
    if catalog is None:
        catalog = Catalog(merchant_id=merchant.id, source="demo", version=1)
        session.add(catalog)
        await session.flush()
    else:
        await session.execute(delete(Product).where(Product.catalog_id == catalog.id))

    for item in fixture["products"]:
        sd = dict(item["structured_data"])
        # additive demo metadata (display header name + category) — uploads never set these
        sd["display_name"] = item.get("display_name", item["title"])
        sd["category"] = item["category"]
        session.add(
            Product(
                catalog_id=catalog.id,
                sku=item["id"],
                title=item["title"],
                price_inr=item["price_inr"],
                description=item["description"],
                image_url=item.get("image_url"),
                page_url=item.get("page_url"),
                tier=item["tier"],
                structured_data=sd,
            )
        )
    await session.commit()
    return catalog.id
