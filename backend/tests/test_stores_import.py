"""Store import tests — pagination loop, edge-UA, FX mapping, error codes,
and the synchronous tier-assignment guarantee before the 201 returns."""
import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_session
from app.ingest import store as store_mod


PUBLIC_IP = ("93.184.216.34", 0)  # example.com — never actually dialed


def _fake_dns(monkeypatch):
    monkeypatch.setattr(
        store_mod.socket, "getaddrinfo",
        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", PUBLIC_IP)])


def _shopify_product(pid: int, vid: int, *, price="29.99", title="Trail Backpack 30L",
                     body="<p>Durable ripstop <b>backpack</b> — 30 L, rain cover.</p>",
                     vendor="TrailCo", image=True, handle=None):
    return {
        "id": pid,
        "title": title,
        "body_html": body,
        "vendor": vendor,
        "handle": handle or f"product-{pid}",
        "variants": [{"id": vid, "price": price, "available": True}],
        "images": [{"src": f"https://cdn.example.com/p{pid}.jpg"}] if image else [],
    }


def _mock_client(pages: dict[int, object], capture: dict | None = None):
    """pages: {page_number: list-of-products | httpx.Response | Exception}"""
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture["ua"] = request.headers.get("user-agent")
            capture["url"] = str(request.url)
        page = int(request.url.params.get("page", "1"))
        content = pages.get(page, [])
        if isinstance(content, Exception):
            raise content
        if isinstance(content, httpx.Response):
            return content
        return httpx.Response(200, json={"products": content})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0)


# --- normalize_store_url ---

def test_normalize_accepts_bare_domain_and_products_json(monkeypatch):
    _fake_dns(monkeypatch)
    assert store_mod.normalize_store_url("mystore.myshopify.com") == "https://mystore.myshopify.com"
    assert store_mod.normalize_store_url("https://shop.example.com/products.json?page=2") == "https://shop.example.com"


def test_normalize_refuses_private_hosts(monkeypatch):
    monkeypatch.setattr(
        store_mod.socket, "getaddrinfo",
        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))])
    with pytest.raises(store_mod.StoreImportError) as ei:
        store_mod.normalize_store_url("localhost")
    assert ei.value.code == "E212"


def test_normalize_refuses_http_scheme(monkeypatch):
    _fake_dns(monkeypatch)
    with pytest.raises(store_mod.StoreImportError) as ei:
        store_mod.normalize_store_url("http://shop.example.com")
    assert ei.value.code == "E212"


# --- mapping ---

def test_map_product_html_stripping_fx_and_structured_data():
    warnings: list[dict] = []
    row = store_mod.map_shopify_product(
        _shopify_product(101, 9001, price="29.99"), "https://shop.example.com",
        fx_rate=83.0, store_meta={"platform": "shopify"}, row_no=1, warnings=warnings)
    assert row["id"] == "shopify-var-9001"
    assert "<" not in row["description"] and "backpack" in row["description"]
    assert row["price_inr"] == 2489  # 29.99 × 83 rounded half-up
    assert row["page_url"] == "https://shop.example.com/products/product-101"
    sd = row["structured_data"]
    assert sd["jsonld_present"] is True and sd["price_fresh"] is True
    assert "price" in sd["fields_present"] and "brand" in sd["fields_present"]
    assert warnings == []


def test_map_product_no_variants_warns():
    warnings: list[dict] = []
    product = _shopify_product(1, 2)
    product["variants"] = []
    row = store_mod.map_shopify_product(
        product, "https://x.example.com", 1.0, {}, 1, warnings)
    assert row is None and warnings[0]["code"] == "W104"


def test_map_product_description_truncation_warns():
    warnings: list[dict] = []
    product = _shopify_product(1, 2, body="<p>" + "word " * 1000 + "</p>")
    row = store_mod.map_shopify_product(
        product, "https://x.example.com", 1.0, {}, 1, warnings)
    assert len(row["description"]) <= store_mod.DESCRIPTION_MAX_CHARS
    assert any(w["code"] == "W103" for w in warnings)


# --- fetch: pagination + UA + errors ---

async def test_fetch_paginates_until_empty_page(monkeypatch):
    pages = {1: [_shopify_product(i, 1000 + i) for i in range(1, 4)],
             2: [_shopify_product(i, 2000 + i) for i in range(4, 6)],
             3: []}
    async with _mock_client(pages) as client:
        res = await store_mod.fetch_shopify_rows(
            "https://shop.example.com", "INR", 100, http_client=client)
    assert res.pages_fetched == 3 and res.products_seen == 5
    assert len(res.rows) == 5 and res.capped_to is None


async def test_fetch_stops_at_cap():
    pages = {1: [_shopify_product(i, 1000 + i) for i in range(1, 31)],
             2: [_shopify_product(i, 2000 + i) for i in range(31, 61)]}
    async with _mock_client(pages) as client:
        res = await store_mod.fetch_shopify_rows(
            "https://shop.example.com", "INR", 10, http_client=client)
    assert len(res.rows) == 10 and res.capped_to == 10 and res.pages_fetched == 1


async def test_fetch_sends_identified_user_agent():
    capture: dict = {}
    pages = {1: [_shopify_product(i, 1000 + i) for i in range(1, 6)]}
    async with _mock_client(pages, capture) as client:
        await store_mod.fetch_shopify_rows("https://shop.example.com", "INR", 100, client)
    assert "AgentAudit/1.0" in capture["ua"] and "Mozilla" in capture["ua"]
    assert "products.json" in capture["url"]


async def test_fetch_403_raises_e210():
    async with _mock_client({1: httpx.Response(403, text="forbidden")}) as client:
        with pytest.raises(store_mod.StoreImportError) as ei:
            await store_mod.fetch_shopify_rows("https://shop.example.com", "INR", 100, client)
    assert ei.value.code == "E210"


async def test_fetch_non_json_raises_e210():
    async with _mock_client({1: httpx.Response(200, text="<html>login</html>")}) as client:
        with pytest.raises(store_mod.StoreImportError) as ei:
            await store_mod.fetch_shopify_rows("https://shop.example.com", "INR", 100, client)
    assert ei.value.code == "E210"


async def test_fetch_429_surfaces_e211_after_retry(monkeypatch):
    async def _fast_sleep(_):
        return None

    monkeypatch.setattr("asyncio.sleep", _fast_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, text="slow down")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(store_mod.StoreImportError) as ei:
            await store_mod.fetch_shopify_rows("https://shop.example.com", "INR", 100, client)
    assert ei.value.code == "E211" and calls["n"] == 2  # one retry, then surface


# --- full route integration ---

async def test_import_route_commits_tiers_before_201(db, monkeypatch):
    _fake_dns(monkeypatch)
    pages = {1: [_shopify_product(i, 5000 + i, price="1200.00") for i in range(1, 6)]}
    real_fetch = store_mod.fetch_shopify_rows

    async def patched_fetch(base_url, currency, max_products, http_client=None):
        async with _mock_client(pages) as client:
            return await real_fetch(base_url, currency, max_products, client)

    from app.routers import stores as stores_router
    monkeypatch.setattr(stores_router, "fetch_shopify_rows", patched_fetch)

    async def _ov():
        yield db

    app.dependency_overrides[get_session] = _ov
    try:
        with TestClient(app) as client:
            r = client.post("/api/stores/import", json={
                "url": "realstore.myshopify.com", "store_currency": "INR"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["products"]["valid"] == 5
        assert body["fx"]["converted"] is False
        assert body["merchant"] == "realstore.myshopify.com"

        from sqlalchemy import select
        from app.db.models import Product
        rows = (await db.execute(
            select(Product).where(Product.catalog_id == body["catalog_id"]))).scalars().all()
        # tiers committed inside the request — never still 'unknown' after 201
        assert all(p.tier in ("rich", "medium", "starved") for p in rows), \
            {p.sku: p.tier for p in rows}
        assert all(p.legibility_composite is not None for p in rows)
    finally:
        app.dependency_overrides.clear()


async def test_import_route_usd_conversion_label(db, monkeypatch):
    _fake_dns(monkeypatch)
    pages = {1: [_shopify_product(i, 7000 + i, price="19.50") for i in range(1, 6)]}
    real_fetch = store_mod.fetch_shopify_rows

    async def patched_fetch(base_url, currency, max_products, http_client=None):
        async with _mock_client(pages) as client:
            return await real_fetch(base_url, currency, max_products, client)

    from app.routers import stores as stores_router
    monkeypatch.setattr(stores_router, "fetch_shopify_rows", patched_fetch)

    async def _ov():
        yield db

    app.dependency_overrides[get_session] = _ov
    try:
        with TestClient(app) as client:
            r = client.post("/api/stores/import", json={
                "url": "https://usstore.example.com", "store_currency": "USD"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["fx"]["converted"] is True
        assert "assumed FX" in body["fx"]["note"]
        assert body["fx"]["rate"] == 83.0
    finally:
        app.dependency_overrides.clear()


async def test_import_route_e210_maps_to_400(db, monkeypatch):
    _fake_dns(monkeypatch)
    pages = {1: httpx.Response(404, text="missing")}
    real_fetch = store_mod.fetch_shopify_rows

    async def patched_fetch(base_url, currency, max_products, http_client=None):
        async with _mock_client(pages) as client:
            return await real_fetch(base_url, currency, max_products, client)

    from app.routers import stores as stores_router
    monkeypatch.setattr(stores_router, "fetch_shopify_rows", patched_fetch)

    async def _ov():
        yield db

    app.dependency_overrides[get_session] = _ov
    try:
        with TestClient(app) as client:
            r = client.post("/api/stores/import", json={"url": "gone.example.com"})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "E210"
    finally:
        app.dependency_overrides.clear()
