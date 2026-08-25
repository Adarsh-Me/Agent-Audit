"""Catalog API + demo loader tests (T1.5)."""
from collections import Counter

from fastapi.testclient import TestClient

from app.db.session import get_session
from app.ingest.demo import load_demo_catalog
from app.main import app


async def test_load_demo_catalog_idempotent(db):
    cid1 = await load_demo_catalog(db)
    cid2 = await load_demo_catalog(db)
    assert cid1 == cid2
    import sqlalchemy

    rows = (await db.execute(
        sqlalchemy.text("select count(*) from products where catalog_id = :cid"), {"cid": cid1}
    )).scalar()
    assert rows == 40


async def test_catalog_endpoints(db):
    await load_demo_catalog(db)

    async def _override():
        yield db

    app.dependency_overrides[get_session] = _override
    try:
        with TestClient(app) as client:
            r = client.get("/catalog")
            assert r.status_code == 200
            body = r.json()
            assert body["count"] == 40 and body["source"] == "demo"
            tiers = Counter(p["tier"] for p in body["products"])
            assert tiers == {"rich": 10, "medium": 20, "starved": 10}

            r = client.get("/catalog/sku_023")
            assert r.status_code == 200
            hero = r.json()
            assert hero["tier"] == "starved"
            assert hero["structured_data"]["jsonld_present"] is False
            assert hero["structured_data"]["display_name"] == "TrailBuddy Daypack 22L"

            r = client.get("/catalog/sku_999")
            assert r.status_code == 404
            assert r.json()["error"]["code"] == "E601"

            # explicit demo selection works even though it's also the default here
            from sqlalchemy import text

            demo_id = (await db.execute(
                text("select id from catalogs where source = 'demo'")
            )).scalar()
            r = client.get("/catalog", params={"catalog_id": demo_id})
            assert r.status_code == 200 and r.json()["source"] == "demo"
    finally:
        app.dependency_overrides.clear()


async def test_multi_catalog_listing_and_selection(db):
    """Catalog listing + pinning: /catalogs lists every store; ?catalog_id=
    pins one; default = newest non-demo catalog (the imported store you ran),
    demo as fallback."""
    from app.db.models import Catalog, Merchant, Product

    demo_cid = await load_demo_catalog(db)

    merchant = Merchant(name="Suta Test")
    db.add(merchant)
    await db.flush()
    upload = Catalog(merchant_id=merchant.id, source="upload", version=1)
    db.add(upload)
    await db.flush()
    db.add(Product(catalog_id=upload.id, sku="SUT-1", title="Suta saree one",
                   price_inr=1999, tier="unknown"))
    db.add(Product(catalog_id=upload.id, sku="SUT-2", title="Suta saree two",
                   price_inr=2999, tier="rich",
                   structured_data={"fields_present": ["price"]}))
    await db.commit()

    async def _override():
        yield db

    app.dependency_overrides[get_session] = _override
    try:
        with TestClient(app) as client:
            # listing: newest first, merchant names + per-catalog counts
            r = client.get("/catalogs")
            assert r.status_code == 200
            listing = r.json()["catalogs"]
            assert [c["catalog_id"] for c in listing][:1] == [upload.id]
            by_id = {c["catalog_id"]: c for c in listing}
            assert by_id[upload.id]["merchant"] == "Suta Test"
            assert by_id[upload.id]["source"] == "upload"
            assert by_id[upload.id]["product_count"] == 2
            assert by_id[demo_cid]["product_count"] == 40
            assert by_id[demo_cid]["source"] == "demo"

            # default view flips to the imported store once one exists
            r = client.get("/catalog")
            assert r.status_code == 200
            body = r.json()
            assert body["catalog_id"] == upload.id and body["count"] == 2

            # …and ?catalog_id= reaches back to demo explicitly
            r = client.get("/catalog", params={"catalog_id": demo_cid})
            assert r.json()["catalog_id"] == demo_cid and r.json()["count"] == 40

            # detail route honours the pin and scoping
            r = client.get("/catalog/SUT-1", params={"catalog_id": upload.id})
            assert r.status_code == 200 and r.json()["title"] == "Suta saree one"
            r = client.get("/catalog/sku_023", params={"catalog_id": upload.id})
            assert r.status_code == 404  # that sku belongs to the demo catalog
            r = client.get("/catalog", params={"catalog_id": "does-not-exist"})
            assert r.status_code == 404 and r.json()["error"]["code"] == "E601"
    finally:
        app.dependency_overrides.clear()
