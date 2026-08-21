"""Condition matrix — enumerates exactly 640 trials (TECHSPEC §7.2, SCHEMA §2.2).

Seed derivations (SCHEMA §3.3.3, normative):
  trial seed:   int(sha256("trial|{persona}|{condition}")[:8],16) % 2**31   — per persona × condition
  shuffle seed: int(sha256("shuffle|{condition}")[:8],16) % 2**31           — per C2 order, shared
                across all personas and models (3 controlled orderings measure position bias)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.constants import (
    CONDITION_CODES,
    FLAGSHIP_MODEL_COUNT,
    FORCED_CONDITIONS,
    NULL_ALLOWED_CONDITIONS,
    PERSONA_COUNT,
)
from app.engine.model_registry import ModelRegistry

PERSONA_IDS = [f"P{i:02d}" for i in range(1, PERSONA_COUNT + 1)]
BULK_CONDITIONS = list(CONDITION_CODES)  # 10 codes, all bulk-tier


@dataclass(frozen=True)
class TrialSpec:
    model: str
    model_version: str
    tier: str  # 'bulk' | 'flagship'
    persona_id: str
    condition: str
    seed: int
    null_allowed: bool


def trial_seed(persona_id: str, condition_code: str) -> int:
    digest = hashlib.sha256(f"trial|{persona_id}|{condition_code}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 2**31


def shuffle_seed(condition_code: str) -> int:
    digest = hashlib.sha256(f"shuffle|{condition_code}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 2**31


def enumerate_trials(registry: ModelRegistry) -> list[TrialSpec]:
    """Full matrix: 3 bulk × 200 + 2 flagship × 20 = 640."""
    trials: list[TrialSpec] = []
    for model in registry.bulk:
        for condition in BULK_CONDITIONS:
            null_allowed = condition in NULL_ALLOWED_CONDITIONS
            for persona in PERSONA_IDS:
                trials.append(TrialSpec(
                    model=model.id,
                    model_version=model.version,
                    tier="bulk",
                    persona_id=persona,
                    condition=condition,
                    seed=trial_seed(persona, condition),
                    null_allowed=null_allowed,
                ))
    for model in registry.flagship:
        for persona in PERSONA_IDS:
            trials.append(TrialSpec(
                model=model.id,
                model_version=model.version,
                tier="flagship",
                persona_id=persona,
                condition="C1-s1",
                seed=trial_seed(persona, "C1-s1"),
                null_allowed=True,
            ))
    return trials


def matrix_counts(trials: list[TrialSpec]) -> dict[str, int]:
    forced = sum(1 for t in trials if not t.null_allowed)
    return {
        "total": len(trials),
        "null_allowed": len(trials) - forced,
        "forced": forced,
    }


def assert_matrix_shape(trials: list[TrialSpec]) -> None:
    counts = matrix_counts(trials)
    assert counts == {"total": 640, "null_allowed": 400, "forced": 240}, counts
    bulk_models = {t.model for t in trials if t.tier == "bulk"}
    flagship_models = {t.model for t in trials if t.tier == "flagship"}
    assert len(bulk_models) == 3 and len(flagship_models) == FLAGSHIP_MODEL_COUNT
    # every (model, persona, condition) triple unique; seeds deterministic per pair
    seen: set[tuple] = set()
    for t in trials:
        key = (t.model, t.persona_id, t.condition)
        assert key not in seen, f"duplicate trial {key}"
        seen.add(key)
        assert t.seed == trial_seed(t.persona_id, t.condition)


def is_forced(condition: str) -> bool:
    assert condition in FORCED_CONDITIONS or condition in NULL_ALLOWED_CONDITIONS
    return condition in FORCED_CONDITIONS
