"""Legibility + revenue model tests (T7.x, T8.1)."""
import pytest

from app.revenue.risk_model import RevenueInputs, compute_revenue, validate_slider
from app.stats.legibility import (
    heuristic_description_score,
    heuristic_title_score,
    score_product,
)


def _prod(sku="sku_001", title="Test Product", desc="A test product.", tier="medium",
          sd=None, image=None):
    return {"id": sku, "title": title, "description": desc, "tier": tier,
            "structured_data": sd or {}, "image_url": image}


# --- heuristics separate tiers ---

def test_title_scores_separate_tiers():
    starved = heuristic_title_score("Daypack")
    medium = heuristic_title_score("CampusSip 650ml Sipper Bottle")
    rich = heuristic_title_score("HydroMax Elite 750ml Insulated Bottle — 24h Cold Vacuum Steel, Leak-Proof")
    assert starved < medium < rich
    assert starved <= 0.25 and rich >= 0.8


def test_description_scores_separate_tiers():
    starved = heuristic_description_score("Durable daypack for daily use.")
    rich = heuristic_description_score(
        "Double-wall vacuum-insulated 750ml bottle in 18/8 food-grade steel keeps drinks "
        "cold for 24 hours and hot for 12; powder-coated matte finish resists scratches; "
        "leak-proof twist cap; 310g; BPA-free."
    )
    assert starved < 0.2 < rich


def test_structured_checklist():
    rich_sd = {"jsonld_present": True,
               "fields_present": ["name", "price", "availability", "image", "brand",
                                  "aggregateRating"], "price_fresh": True}
    res = score_product(_prod(
        title="AquaSteel Pro 1L Insulated Bottle — 24h Cold Vacuum Steel, Leak-Proof",
        desc="Double-wall vacuum-insulated 1L bottle in 18/8 food-grade steel keeps drinks "
             "cold for 24 hours and hot for 12; powder-coated matte finish resists sweat; "
             "leak-proof cap; 290g; BPA-free; lifetime insulation warranty.",
        sd=rich_sd, image="/x.svg"))
    assert res.structured == pytest.approx(1.0)
    assert res.proposed_tier == "rich"
    res_starved = score_product(_prod(title="Bottle", desc="Bottle.", sd={}))
    assert res_starved.composite < 0.25
    assert res_starved.proposed_tier == "starved"
    assert res.proposed_tier == "rich"


async def test_c4_upload_tier_assignment(db):
    from app.db.models import Catalog, Merchant, Product
    from app.stats.legibility import score_catalog_and_persist

    m = Merchant(name="T")
    db.add(m)
    await db.flush()
    c = Catalog(merchant_id=m.id, source="upload", version=1)
    db.add(c)
    await db.flush()
    starved_row = Product(catalog_id=c.id, sku="a_1", title="X", price_inr=10,
                          tier="unknown")
    rich_row = Product(
        catalog_id=c.id, sku="a_2",
        title="Premium Pro ANC Wireless Headphones — 40h Battery, LDAC",
        price_inr=10,
        description="Hybrid active noise cancelling with 40 hour battery life, USB-C "
                    "fast charge, memory foam earcups and multipoint bluetooth 5.3.",
        tier="unknown",
        structured_data={"jsonld_present": True, "fields_present": [
            "name", "price", "availability", "image", "brand", "aggregateRating"],
            "price_fresh": True},
        image_url="/x.svg",
    )
    db.add_all([starved_row, rich_row])
    await db.commit()

    out = await score_catalog_and_persist(db, c.id)
    by_sku = {o["sku"]: o for o in out}
    assert by_sku["a_1"]["proposed_tier"] == "starved" if "proposed_tier" in by_sku["a_1"] \
        else by_sku["a_1"]["tier"] == "starved"
    assert by_sku["a_2"]["legibility_composite"] >= 0.75
    # upload rows get reassigned tiers; composites persisted
    assert starved_row.legibility_composite < 0.25
    assert starved_row.tier == "starved"


# --- revenue model ---

def test_slider_validation():
    for v in (0.01, 0.05, 0.10, 0.20):
        assert validate_slider(v) == v
    with pytest.raises(ValueError):
        validate_slider(0.03)


def test_rar_math_and_labeled_inputs():
    inputs = RevenueInputs(gmv_inr=800_000, gmv_source="demo-default", s_agent=0.20,
                           s_agent_source="slider", f_task=0.25, f_task_ci=(0.20, 0.30))
    out = compute_revenue(inputs)
    assert out["revenue_at_risk_inr"]["value"] == round(800_000 * 0.20 * 0.25)
    assert out["revenue_at_risk_inr"]["ci_low"] == round(800_000 * 0.20 * 0.20)
    assert out["revenue_at_risk_inr"]["ci_high"] == round(800_000 * 0.20 * 0.30)
    assert out["inputs"]["gmv_inr"]["source"] == "demo-default"
    assert out["inputs"]["s_agent"]["source"] == "slider"  # assumption, labeled as such
    assert out["recoverable_inr"] is None


def test_recoverable_uses_delta_ci():
    inputs = RevenueInputs(gmv_inr=800_000, gmv_source="user", s_agent=0.20,
                           s_agent_source="slider", f_task=0.256, f_task_ci=(0.22, 0.29),
                           delta_f=(0.114, 0.076, 0.153))
    out = compute_revenue(inputs)
    rec = out["recoverable_inr"]
    assert rec["value"] == round(800_000 * 0.20 * 0.114)
    assert rec["ci_low"] == round(800_000 * 0.20 * 0.076)
    assert rec["ci_high"] == round(800_000 * 0.20 * 0.153)


def test_zero_usable_trials_refuses_r0():
    """wilson_ci(n=0) is a [0,1] 'no data' sentinel → f_task would be 0.0.
    compute_revenue must return revenue_at_risk_inr=None + not_measurable
    rather than a confident ₹0 (unknown disguised as safe)."""
    inputs = RevenueInputs(gmv_inr=800_000, gmv_source="demo-default", s_agent=0.20,
                           s_agent_source="slider", f_task=0.0, f_task_ci=(0.0, 1.0),
                           usable_trials=0)
    out = compute_revenue(inputs)
    assert out["not_measurable"] is True
    assert out["revenue_at_risk_inr"] is None
    assert out["inputs"]["f_task"]["value"] is None
    assert out["inputs"]["f_task"]["usable_trials"] == 0
    assert out["recoverable_inr"] is None


def test_measured_true_zero_has_note():
    """f_task truly 0 but with usable missions is a measured ₹0 — flags a note,
    not not_measurable."""
    inputs = RevenueInputs(gmv_inr=800_000, gmv_source="demo-default", s_agent=0.20,
                           s_agent_source="slider", f_task=0.0, f_task_ci=(0.0, 0.02),
                           usable_trials=100)
    out = compute_revenue(inputs)
    assert out.get("not_measurable") is None
    assert out["revenue_at_risk_inr"]["value"] == 0
    assert "measured result here" in out["zero_measured_note"]
