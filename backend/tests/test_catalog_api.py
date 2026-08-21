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
    finally:
        app.dependency_overrides.clear()
