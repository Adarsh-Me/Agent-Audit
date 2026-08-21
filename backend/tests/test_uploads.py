"""Upload ingestion tests — T2.4: every error code + partial-valid fixture."""
import json

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_session


def _client():
    return TestClient(app)


def _valid_row(i: int) -> dict:
    return {
        "id": f"sku_{i:03d}",
        "title": f"Product {i}",
        "price_inr": 100 + i,
        "description": f"Test product number {i} with a plain description.",
    }


def _post_json(rows):
    with _client() as client:
        return client.post("/api/uploads", json=rows)


# --- happy paths ---

async def test_json_upload_40_valid(db):
    async def _ov():
        yield db
    app.dependency_overrides[get_session] = _ov
    try:
        r = _post_json([_valid_row(i) for i in range(1, 41)])
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["valid"] == 40 and body["invalid"] == []
        # tier forced to unknown; verify via catalog read
        from sqlalchemy import select
        from app.db.models import Product
        rows = (await db.execute(select(Product).where(Product.catalog_id == body["catalog_id"]))).scalars().all()
        assert len(rows) == 40 and all(p.tier == "unknown" for p in rows)
    finally:
        app.dependency_overrides.clear()


async def test_csv_upload_with_optional_urls(db):
    async def _ov():
        yield db
    app.dependency_overrides[get_session] = _ov
    try:
        csv_text = "id,title,price_inr,description,image_url,page_url\n" + "".join(
            f"sku_{i:03d},Item {i},{100 + i},Description for item {i} here.,,\n"
            for i in range(1, 11)
        )
        with _client() as client:
            r = client.post(
                "/api/uploads",
                files={"file": ("cat.csv", csv_text.encode("utf-8"), "text/csv")},
            )
        assert r.status_code == 201, r.text
        assert r.json()["valid"] == 10
    finally:
        app.dependency_overrides.clear()


async def test_partial_valid_fixture_38_of_40(db):
    """The plan's canonical fixture: 38 valid rows + 2 bad rows → 201 with per-row errors."""
    async def _ov():
        yield db
    app.dependency_overrides[get_session] = _ov
    try:
        rows = [_valid_row(i) for i in range(1, 39)]
        bad_price = _valid_row(39) | {"price_inr": 0}          # E104 at row 39
        bad_desc = _valid_row(40) | {"description": "x" * 2001}  # E105 at row 40
        r = _post_json(rows + [bad_price, bad_desc])
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["valid"] == 38
        codes = {(e["row"], e["code"]) for e in body["invalid"]}
        assert (39, "E104") in codes and (40, "E105") in codes
    finally:
        app.dependency_overrides.clear()


async def test_unknown_fields_stripped(db):
    async def _ov():
        yield db
    app.dependency_overrides[get_session] = _ov
    try:
        rows = [_valid_row(i) for i in range(1, 6)]
        rows[0]["secret_sauce"] = "should-not-persist"
        r = _post_json(rows)
        assert r.status_code == 201
        warnings = [e for e in r.json()["invalid"] if e["code"].startswith("W")]
        assert any("secret_sauce" in e["message"] for e in warnings)
    finally:
        app.dependency_overrides.clear()


# --- payload-level errors ---

def test_e101_too_many_products():
    r = _post_json([_valid_row(i % 1000) for i in range(501)])
    assert r.status_code == 400 and r.json()["error"]["code"] == "E101"


def test_e102_payload_too_large():
    big_row = _valid_row(1) | {"description": "y" * 300}
    payload = json.dumps([big_row] * 20_000)  # ~6 MB
    r = _post_json(json.loads(payload))
    assert r.status_code == 400 and r.json()["error"]["code"] == "E102"


def test_e107_too_few_valid_products():
    r = _post_json([_valid_row(1), _valid_row(2)])
    assert r.status_code == 400 and r.json()["error"]["code"] == "E107"


# --- row-level errors ---

async def test_row_error_codes(db):
    async def _ov():
        yield db
    app.dependency_overrides[get_session] = _ov
    try:
        rows = [_valid_row(i) for i in range(1, 9)]
        rows.append({"id": "sku_bad", "title": "No price", "description": "d"})       # E103
        rows.append(_valid_row(10) | {"price_inr": 20_000_001})                        # E104
        rows.append(_valid_row(11))
        rows.append(_valid_row(11))                                                    # E106 dup
        r = _post_json(rows)
        assert r.status_code == 201
        codes = [e["code"] for e in r.json()["invalid"]]
        assert "E103" in codes and "E104" in codes and "E106" in codes
    finally:
        app.dependency_overrides.clear()
