"""Bracket/quote normalization for model answers (live-fire fix 2026-08-29)."""
from app.engine.parse import parse_response


def test_bracket_wrapped_sku_parses():
    raw = '{"product_id": "[shopify-var-46046524178586]", "reason": "best value"}'
    out = parse_response(raw, valid_skus={"shopify-var-46046524178586"}, null_allowed=True)
    assert out.parse_ok is True
    assert out.choice == "shopify-var-46046524178586"


def test_quoted_and_padded_sku_parses():
    raw = 'Sure!\n```json\n{"product_id": " \\"sku_001\\" ", "reason": "cheap"}\n```'
    out = parse_response(raw, valid_skus={"sku_001"}, null_allowed=True)
    assert out.parse_ok is True
    assert out.choice == "sku_001"


def test_salvaged_truncated_bracket_sku_parses():
    raw = '\n{"product_id": "[sku_042]", "reason": "The Insulated W'
    out = parse_response(raw, valid_skus={"sku_042"}, null_allowed=True)
    assert out.parse_ok is True
    assert out.choice == "sku_042"


def test_null_still_null():
    out = parse_response('{"product_id": null, "reason": "nothing fits"}',
                         valid_skus={"sku_001"}, null_allowed=True)
    assert out.parse_ok is True
    assert out.choice is None
