"""Constants registry integrity — SCHEMA §12 / §4.2 sync rules."""
import pathlib

import yaml

from app import constants as C

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_score_weights_sum_to_one():
    C.validate_score_weights(C.SCORE_WEIGHTS)


def test_scoring_config_yaml_matches_constants():
    cfg = yaml.safe_load((BACKEND_ROOT / "app" / "scoring" / "config.yaml").read_text("utf-8"))
    assert {k: float(v) for k, v in cfg["weights"].items()} == C.SCORE_WEIGHTS
    assert cfg["bootstrap"]["replicates"] == C.BOOTSTRAP_REPLICATES
    assert cfg["bootstrap"]["cluster"] == C.BOOTSTRAP_CLUSTER
    assert cfg["permutation"]["replicates"] == C.PERMUTATION_REPLICATES
    assert float(cfg["cost_cap_usd"]) == C.COST_CAP_USD


def test_run_matrix_arithmetic():
    # TECHSPEC §22: 3 bulk × 200 + 40 flagship = 640; null split 400/240
    assert C.BULK_MODEL_COUNT * C.TRIALS_PER_BULK_MODEL + 40 == C.TRIALS_PER_FULL_RUN
    per_model_null = 60 + 60  # C1 + C2
    assert per_model_null * C.BULK_MODEL_COUNT + 40 == C.NULL_ALLOWED_TRIALS
    assert 80 * C.BULK_MODEL_COUNT == C.FORCED_TRIALS
    assert C.NULL_ALLOWED_TRIALS + C.FORCED_TRIALS == C.TRIALS_PER_FULL_RUN


def test_condition_codes_exhaustive():
    assert len(C.CONDITION_CODES) == 10
    assert set(C.NULL_ALLOWED_CONDITIONS) | set(C.FORCED_CONDITIONS) == set(C.CONDITION_CODES)
    assert not set(C.NULL_ALLOWED_CONDITIONS) & set(C.FORCED_CONDITIONS)


def test_error_codes_shape():
    for code, (_, status, _) in C.ERROR_CODES.items():
        assert code.startswith("E") and len(code) == 4
        assert status is None or 400 <= status < 600


def test_invalid_weights_rejected():
    import pytest

    with pytest.raises(ValueError, match="E402"):
        C.validate_score_weights({**C.SCORE_WEIGHTS, "visibility": 0.5})
