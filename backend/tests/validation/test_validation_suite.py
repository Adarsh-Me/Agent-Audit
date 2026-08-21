"""V1–V6 planted-bias validation suite (TECHSPEC §8.8, PRD §8.4.8).

Synthetic trial generators plant known ground truth; the metric layer must recover it.
Run via `make validate` — CI-gated from Day 6 18:00 onward, no exceptions.
A metric that fails its planted case does not ship.
"""
from __future__ import annotations

import random

import pytest

from app.stats.bootstrap import cluster_bootstrap
from app.stats.metrics import (
    compute_all,
    hhi_norm_from_shares,
    invisible_skus,
    m2_position,
    m5_stability,
    normalize,
    wilson_ci,
)

N = 40
SKUS = [f"sku_{i:03d}" for i in range(1, N + 1)]
BULK = ["m1", "m2", "m3"]
PERSONAS = [f"P{i:02d}" for i in range(1, 21)]


def mk_trial(model="m1", persona="P01", condition="C1-s1", choice=None,
             null_allowed=True, presented=None, parse_ok=True):
    return {
        "model": model,
        "model_version": "v1",
        "tier": "bulk",
        "persona_id": persona,
        "condition": condition,
        "seed": 0,
        "presented_order": presented or SKUS,
        "choice": choice,
        "null_allowed": null_allowed,
        "parse_ok": parse_ok,
        "reason": None,
    }


def c1_all_choice(sku: str) -> list[dict]:
    """400 null-allowed trials (3 models x C1), every one chooses `sku`."""
    return [
        mk_trial(model=m, persona=p, condition=f"C1-s{k}", choice=sku)
        for m in BULK
        for k in (1, 2, 3)
        for p in PERSONAS
    ]


def test_v1_monopoly_recovers():
    trials = c1_all_choice("sku_007")
    m = compute_all(trials, N, completeness=0.5, perms=100)
    assert m["hhi_norm"] >= 0.95
    boot = {
        f"share:{s}": (0.0, 0.001) for s in SKUS if s != "sku_007"
    } | {"share:sku_007": (0.99, 1.0)}
    inv = invisible_skus(boot, N)
    assert len(inv) == 39


def test_v2_uniform_recovers():
    rng = random.Random(7)
    trials = []
    for m in BULK:
        for k in (1, 2, 3):
            for p in PERSONAS:
                trials.append(mk_trial(model=m, persona=p, condition=f"C1-s{k}",
                                       choice=SKUS[rng.randrange(N)]))
    m = compute_all(trials, N, perms=100)
    assert m["hhi_norm"] <= 0.05


def test_v3_position_bias_detected():
    rng = random.Random(11)
    trials = []
    orders: dict[str, list[str]] = {}
    for k in (1, 2, 3):
        order = SKUS[:]
        rng.shuffle(order)
        orders[f"C2-s{k}"] = order
    for m in BULK:
        for k in (1, 2, 3):
            cond = f"C2-s{k}"
            for p in PERSONAS:
                order = orders[cond]
                if rng.random() < 0.8:
                    choice = order[0]          # slot 1 w.p. 0.8
                else:
                    choice = order[rng.randrange(N)]
                trials.append(mk_trial(model=m, persona=p, condition=cond,
                                       choice=choice, presented=list(order)))
    pos = m2_position(trials, N, perms=2000)
    assert pos["top3_capture"] > 0.25  # far above the 0.075 chance line
    assert pos["lift"] > 3.0
    assert pos["p_value"] < 0.001


def test_v4_disjoint_models_low_cosine():
    trials = []
    half = set(SKUS[:20])
    for p in PERSONAS:
        trials.append(mk_trial(model="m1", persona=p, choice=sorted(half)[hash(p) % 20]))
        trials.append(mk_trial(model="m2", persona=p, choice=sorted(set(SKUS[20:]))[hash(p) % 20]))
    stab = m5_stability(trials)
    assert stab["mean"] < 0.1


def test_v5_framing_swap_recovered():
    """X: 0.40→0.15, Y: 0.10→0.35, others equal share; deterministic counts."""
    subset = SKUS[:10]
    X, Y = subset[0], subset[1]
    others = [s for s in subset if s not in (X, Y)]
    n_per_arm_model = 200  # per model per arm → pooled 600/arm

    def make_arm(cond: str, wx: float, wy: float) -> list[dict]:
        trials = []
        for m in BULK:
            counts = {X: int(wx * n_per_arm_model), Y: int(wy * n_per_arm_model)}
            rest_w = (1 - wx - wy) / len(others)
            for s in others:
                counts[s] = int(rest_w * n_per_arm_model)
            # fix rounding: pad/trim via largest remainder on 'others'
            diff = n_per_arm_model - sum(counts.values())
            counts[others[0]] += diff
            flat = []
            for sku, c in counts.items():
                flat += [sku] * c
            for i, sku in enumerate(flat):
                trials.append(mk_trial(model=m, persona=PERSONAS[i % len(PERSONAS)],
                                       condition=f"{cond}-s{1 + i % 2}", choice=sku,
                                       null_allowed=False))
        return trials

    trials = make_arm("C3-A", 0.40, 0.10) + make_arm("C3-B", 0.15, 0.35)
    m = compute_all(trials, N, perms=0)
    deltas = {p["sku"]: p["delta"] for p in m["framing"]["per_product"]}
    assert 0.20 <= deltas[X] <= 0.30
    assert 0.20 <= deltas[Y] <= 0.30
    mean_delta = m["framing"]["mean_delta"]
    assert 0.04 <= mean_delta <= 0.06


def test_v6_wilson_contains_planted_null_rate():
    trials = []
    for i in range(400):
        choice = None if i % 10 < 3 else SKUS[i % N]   # exactly 30% null
        trials.append(mk_trial(persona=PERSONAS[i % len(PERSONAS)], choice=choice))
    cov = compute_all(trials, N)["coverage"]
    lo, hi = wilson_ci(120, 400)
    assert cov["f_task"] == pytest.approx(0.30)
    assert lo <= 0.30 <= hi
    # and through the pipeline's own CI:
    assert cov["ci_low"] <= 0.30 <= cov["ci_high"]


def test_bootstrap_score_ci_propagates():
    """Shared resample recomputes score — CI present and sane on monopoly data."""
    trials = c1_all_choice("sku_007")
    point = compute_all(trials, N, completeness=0.5, perms=0)
    boot = cluster_bootstrap(trials, N, completeness=0.5, B=120)
    lo, hi = boot["score"]
    assert lo <= point["score"] + 1e-9 <= hi or abs(point["score"] - hi) < 1e-6
    assert 0 <= lo <= hi <= 100


def test_hhi_norm_bounds():
    uniform = normalize({s: 1 for s in SKUS})
    assert hhi_norm_from_shares(uniform, N) == pytest.approx(0.0, abs=1e-9)
    mono = {"sku_007": 1.0}
    assert hhi_norm_from_shares(mono, N) == pytest.approx(1.0, abs=1e-9)
