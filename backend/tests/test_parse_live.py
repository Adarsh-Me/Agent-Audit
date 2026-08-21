"""Parser tolerance regressions from the 2026-08-22 live fire."""
from app.engine.parse import parse_response

SKUS = {"sku_001", "sku_002", "sku_003"}
ORD = {"1": "sku_001", "2": "sku_002", "3": "sku_003"}


def test_exact_bracket_id_parses():
    r = parse_response('{"product_id": "sku_002", "reason": "fits"}', SKUS)
    assert r.parse_ok
    assert r.choice == "sku_002"
    assert r.reason == "fits"


def test_ordinal_answer_maps_to_presented_order():
    # models that ignore the bracket-id instruction answer with the line number
    r = parse_response('{"product_id": "3", "reason": "cheapest"}', SKUS,
                       ordinal_map=ORD)
    assert r.parse_ok
    assert r.choice == "sku_003"


def test_ordinal_out_of_range_still_fails():
    r = parse_response('{"product_id": "9"}', SKUS, ordinal_map=ORD)
    assert not r.parse_ok


def test_unescaped_quote_in_reason_is_salvaged():
    # 15-inch laptops break naive JSON quoting; the CHOICE must survive
    raw = '{"product_id": "sku_001", "reason": "fits a 15" laptop fine"}'
    r = parse_response(raw, SKUS)
    assert r.parse_ok
    assert r.choice == "sku_001"
    assert r.reason is None  # reason dropped rather than losing the trial


def test_unknown_sku_still_fails_cleanly():
    r = parse_response('{"product_id": "sku_999"}', SKUS)
    assert not r.parse_ok
    assert "not in catalog" in (r.error or "")


def test_null_decline_keeps_reason():
    r = parse_response('{"product_id": null, "reason": "nothing fits"}', SKUS)
    assert r.parse_ok
    assert r.choice is None
    assert r.reason == "nothing fits"


def test_non_string_raw_never_crashes():
    assert not parse_response(None, SKUS).parse_ok  # type: ignore[arg-type]
