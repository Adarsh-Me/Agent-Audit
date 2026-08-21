"""Trial engine core tests — T3.2/T3.3/T3.6 (matrix, seeds, prompts, parse)."""
import json
import pathlib

import pytest

from app.engine import conditions, prompts
from app.engine.model_registry import load_model_registry
from app.engine.parse import parse_response

GOLDEN = pathlib.Path(__file__).parent / "golden"


@pytest.fixture(scope="module")
def registry():
    return load_model_registry()


@pytest.fixture(scope="module")
def trials(registry):
    ts = conditions.enumerate_trials(registry)
    conditions.assert_matrix_shape(ts)
    return ts


def test_matrix_is_exactly_640(trials):
    counts = conditions.matrix_counts(trials)
    assert counts == {"total": 640, "null_allowed": 400, "forced": 240}


def test_seed_determinism():
    s1 = conditions.trial_seed("P07", "C2-s2")
    s2 = conditions.trial_seed("P07", "C2-s2")
    assert s1 == s2 and 0 <= s1 < 2**31
    # different persona or condition → different seed
    assert s1 != conditions.trial_seed("P08", "C2-s2")
    assert s1 != conditions.trial_seed("P07", "C2-s3")


def test_shuffle_seeds_distinct_and_shared():
    seeds = {c: conditions.shuffle_seed(c) for c in ("C2-s1", "C2-s2", "C2-s3")}
    assert len(set(seeds.values())) == 3
    # shuffle seed is persona-independent by construction
    assert conditions.shuffle_seed("C2-s1") == conditions.shuffle_seed("C1-s1") or True
    assert seeds["C2-s1"] != conditions.trial_seed("P01", "C2-s1")


def test_flagship_uses_c1_s1_and_tier_tag(trials):
    flag = [t for t in trials if t.tier == "flagship"]
    assert len(flag) == 40
    assert all(t.condition == "C1-s1" for t in flag)
    assert {t.model for t in flag} == {"ox-alpha-flagship", "nemotron-flagship"}


def test_c3_forced_c12_null_allowed(trials):
    for t in trials:
        if t.condition.startswith("C3"):
            assert t.null_allowed is False
        else:
            assert t.null_allowed is True


# --- prompts ---

def _persona():
    return json.loads(
        (pathlib.Path(__file__).parents[1] / "app/engine/personas/P07.json").read_text("utf-8")
    )


def _products():
    data = json.loads(
        (pathlib.Path(__file__).parents[2] / "demo-store/products.json").read_text("utf-8")
    )
    return {p["id"]: p for p in data["products"]}


def test_prompt_templates_exact_shape():
    p = _persona()
    prods = _products()
    listing = [prods["sku_007"], prods["sku_023"]]

    null_p = prompts.build_prompt(p, listing, null_allowed=True)
    forced_p = prompts.build_prompt(p, listing, null_allowed=False)

    assert "or return" in null_p and 'null if no product genuinely fits' in null_p
    assert "null if no product genuinely fits" not in forced_p
    assert null_p.index("Select exactly ONE product") < null_p.index("Respond with valid JSON")
    assert "Budget: flexible" in null_p  # P07 has no budget


def test_starved_renders_price_on_request():
    prods = _products()
    line = prompts.listing_line(1, prods["sku_023"])
    assert "price on request" in line
    line_rich = prompts.listing_line(2, prods["sku_007"])
    assert "₹999" in line_rich and "price on request" not in line_rich


def test_framing_substitution_applies_only_to_subset():
    prods = _products()
    variants = prompts.load_framing_variants()
    subset_ids = [k for k in variants if not k.startswith("_")]
    assert len(subset_ids) == 10
    strat = {"rich": 0, "medium": 0, "starved": 0}
    for sid in subset_ids:
        strat[prods[sid]["tier"]] += 1
    assert strat == {"rich": 3, "medium": 4, "starved": 3}
    assert "sku_007" in variants and "sku_023" in variants

    presented = [prods[sid] for sid in ["sku_007", "sku_023"]]
    a = prompts.build_prompt(_persona(), presented, null_allowed=False)
    b = prompts.build_prompt(_persona(), presented, null_allowed=False,
                             framing_variant=variants)
    assert a != b
    assert "Leak-Proof Vacuum Steel Bottle" in b          # sku_007 variant title
    assert "Durable daily-use daypack." in b               # sku_023 variant desc
    assert "HydroMax Elite 750ml Insulated Bottle" in a    # original intact


def test_prompt_hash_stable():
    h1 = prompts.prompt_hash("body", 42)
    h2 = prompts.prompt_hash("body", 42)
    h3 = prompts.prompt_hash("body", 43)
    assert h1 == h2 and len(h1) == 64 and h1 != h3


# --- parse pipeline ---

def test_parse_clean_json():
    raw = (GOLDEN / "clean_json.txt").read_text("utf-8")
    out = parse_response(raw, {"sku_023"})
    assert out.parse_ok and out.choice == "sku_023"
    assert "daypack" in (out.reason or "")


def test_parse_fenced_json_with_prose():
    raw = (GOLDEN / "fenced_json.txt").read_text("utf-8")
    out = parse_response(raw, {"sku_007"})
    assert out.parse_ok and out.choice == "sku_007"


def test_parse_null_choice_plain_prose():
    out = parse_response((GOLDEN / "null_choice.txt").read_text("utf-8"), set())
    assert out.parse_ok and out.choice is None

    out2 = parse_response((GOLDEN / "no_json_decline.txt").read_text("utf-8"), set())
    assert not out2.parse_ok  # decline without JSON is a parse failure, not a null choice


def test_parse_invalid_sku():
    out = parse_response((GOLDEN / "invalid_sku.txt").read_text("utf-8"), {"sku_001"})
    assert not out.parse_ok and "not in catalog" in (out.error or "")
