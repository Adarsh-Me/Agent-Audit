"""Demo store fixture tests — T1.4 (tier counts, anchors, decorrelation, schema validity)."""
import json
import math
import pathlib
from collections import Counter

import pytest

from app.constants import DEMO_ANCHORS, PRICE_MAX_INR, PRICE_MIN_INR, TIER_BLOCK

FIXTURE = (
    pathlib.Path(__file__).resolve().parents[2] / "demo-store" / "products.json"
).resolve()
required_fixture = pytest.mark.skipif(not FIXTURE.exists(), reason="run demo-store/generate.py first")


def _load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@required_fixture
def test_counts_and_categories():
    data = _load()
    products = data["products"]
    assert len(products) == 40
    tiers = Counter(p["tier"] for p in products)
    assert tiers == {"rich": 10, "medium": 20, "starved": 10}
    cats = Counter(p["category"] for p in products)
    assert set(cats.values()) == {10} and len(cats) == 4


@required_fixture
def test_anchor_identities():
    data = _load()
    by_id = {p["id"]: p for p in data["products"]}
    assert by_id["sku_007"]["tier"] == "rich"
    assert by_id["sku_017"]["title"] == "AquaSteel Pro 1L Insulated Bottle — Matte Black"
    assert by_id["sku_017"]["price_inr"] == 749
    assert (
        by_id["sku_017"]["description"]
        == "Double-walled 18/8 steel; 24h cold, 12h hot; 290g; leak-proof cap; BPA-free."
    )
    hero = by_id["sku_023"]
    assert hero["tier"] == "starved" and hero["category"] == "backpacks"
    assert hero["price_inr"] == DEMO_ANCHORS["sku_023"]["price_inr"]
    assert hero["title"] == "Daypack"  # bare-category listing title per tier matrix
    assert hero["description"] == "Durable daypack for daily use."


@required_fixture
def test_baseline_order_block_pattern_and_hero_position():
    data = _load()
    order = data["baseline_order"]
    by_id = {p["id"]: p for p in data["products"]}
    assert len(order) == 40 and len(set(order)) == 40
    for pos, sku in enumerate(order, start=1):
        assert by_id[sku]["tier"] == TIER_BLOCK[(pos - 1) % 4], f"block broken at position {pos}"
    assert order[18] == "sku_023", "invisible hero must sit at baseline position 19"


@required_fixture
def test_tier_position_decorrelation():
    """|rho(tier, position)| < 0.15 on the baseline order (TECHSPEC §5.3)."""
    data = _load()
    order = data["baseline_order"]
    by_id = {p["id"]: p for p in data["products"]}
    rank = {"rich": 0, "medium": 1, "starved": 2}
    xs = [rank[by_id[s]["tier"]] for s in order]
    ys = list(range(1, 41))
    mx, my = sum(xs) / 40, sum(ys) / 40
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    rho = cov / (sx * sy)
    assert abs(rho) < 0.15, rho


@required_fixture
def test_starved_prices_sit_at_mid_ladder_deciles():
    data = _load()
    for cat in ("bottles", "headphones", "backpacks", "fitness"):
        ranked = sorted(
            (p for p in data["products"] if p["category"] == cat), key=lambda p: p["price_inr"]
        )
        for idx, item in enumerate(ranked, start=1):
            if item["tier"] == "starved":
                assert idx in (5, 6, 7), f"{item['id']} at decile {idx} of {cat}"


@required_fixture
def test_canonical_schema_validity():
    data = _load()
    for prod in data["products"]:
        assert prod["title"] and len(prod["title"]) <= 200
        assert PRICE_MIN_INR <= prod["price_inr"] <= PRICE_MAX_INR
        assert len(prod["description"]) > 0
        words = len(prod["description"].split())
        if prod["tier"] == "starved":
            assert words <= 10, f"{prod['id']} starved desc has {words} words"
        elif prod["tier"] == "medium":
            assert 15 <= words <= 35, f"{prod['id']} medium desc has {words} words"
        else:  # rich — sku_017 is the docs-pinned canonical example (short by design)
            if prod["id"] != "sku_017":
                assert words >= 40, f"{prod['id']} rich desc has only {words} words"

        sd = prod["structured_data"]
        if prod["tier"] == "rich":
            assert sd["jsonld_present"] and len(sd["fields_present"]) >= 6
            assert sd["price_fresh"] is True
        elif prod["tier"] == "medium":
            assert sd["fields_present"] == ["name", "price"] and sd["price_fresh"] is False
        else:
            assert not sd["jsonld_present"] and sd["fields_present"] == []
            assert sd["price_fresh"] is None


@required_fixture
def test_static_site_artifacts_exist():
    site = FIXTURE.parent / "site"
    data = _load()
    assert (site / "catalog.json").exists()
    assert (site / "llms.txt").exists()
    assert (site / "index.html").exists()
    for prod in data["products"]:
        assert (site / "p" / f"{prod['id']}.html").exists(), prod["id"]
        assert (site / "img" / f"{prod['id']}.svg").exists(), prod["id"]
