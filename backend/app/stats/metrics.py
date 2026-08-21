"""Statistics core — M-1…M-6 per PRD §8.4 / TECHSPEC §8, over parse_ok bulk trials.

Scope rules (normative):
  - Primary metrics use bulk-tier models only; flagship reported separately (too thin to pool).
  - F_task excludes flagship (PRD §8.4.4 scope note); stability matrix excludes flagship.
  - Choice shares ("agent demand") pool all non-null bulk trials (C1+C2).
Pure functions over plain dicts — no ORM, no IO — so the bootstrap can recompute cheaply.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict

from app.constants import PERMUTATION_REPLICATES, SCORE_WEIGHTS

# ---------------------------------------------------------------------------
# helpers


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated percentile on a pre-sorted list, q in [0,100]."""
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * (q / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f]) * (c - k) + float(sorted_vals[c]) * (k - f)


def percentile_ci(values: list[float], ci: int = 95) -> tuple[float, float]:
    s = sorted(values)
    tail = (100 - ci) / 2
    return _percentile(s, tail), _percentile(s, 100 - tail)


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval (TECHSPEC §8.4)."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - margin) / denom), min(1.0, (centre + margin) / denom))


def cosine(u: dict[str, float], v: dict[str, float]) -> float:
    keys = set(u) | set(v)
    dot = sum(u.get(k, 0.0) * v.get(k, 0.0) for k in keys)
    nu = math.sqrt(sum(x * x for x in u.values()))
    nv = math.sqrt(sum(x * x for x in v.values()))
    if nu == 0 or nv == 0:
        return 0.0
    return dot / (nu * nv)


def normalize(d: Counter | dict[str, float]) -> dict[str, float]:
    total = sum(d.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in d.items()}


# ---------------------------------------------------------------------------
# filtering


def _bulk(trials: list[dict]) -> list[dict]:
    return [t for t in trials if t["tier"] != "flagship"]


def _parse_ok(trials: list[dict]) -> list[dict]:
    return [t for t in trials if t.get("parse_ok", True)]


def _choices(trials: list[dict]) -> list[dict]:
    """Non-null valid choices."""
    return [t for t in trials if t.get("choice")]


def _condition(trials: list[dict], prefix: str) -> list[dict]:
    return [t for t in trials if t["condition"].startswith(prefix)]


# ---------------------------------------------------------------------------
# M-1 … M-6


def hhi(shares) -> float:
    """HHI over an iterable of share values."""
    return sum(s * s for s in shares)


def hhi_norm_from_shares(shares: dict[str, float], n_catalog: int) -> float:
    if n_catalog <= 1:
        return 0.0
    raw = hhi(shares.values()) if isinstance(shares, dict) else hhi(shares)
    return max(0.0, min(1.0, (raw - 1.0 / n_catalog) / (1.0 - 1.0 / n_catalog)))


def m1_concentration(c1_trials: list[dict], n_catalog: int) -> tuple[float, dict[str, float]]:
    """Pooled HHI_norm over C1 non-null bulk + per-model breakdown."""
    per_model_shares = {}
    by_model: dict[str, Counter] = defaultdict(Counter)
    for t in _condition(_bulk(_choices(c1_trials)), "C1"):
        by_model[t["model"]][t["choice"]] += 1
    pooled: Counter = Counter()
    for m, c in by_model.items():
        pooled.update(c)
        per_model_shares[m] = hhi_norm_from_shares(normalize(c), n_catalog)
    return hhi_norm_from_shares(normalize(pooled), n_catalog), per_model_shares


def m2_position(c2_trials: list[dict], n_catalog: int,
                perms: int = PERMUTATION_REPLICATES, seed: int = 42) -> dict:
    """Top-3 capture, lift, permutation p-value, per-slot vector."""
    slots: list[int] = []
    for t in _condition(_bulk(_choices(c2_trials)), "C2"):
        order = t["presented_order"]
        if t["choice"] in order:
            slots.append(order.index(t["choice"]) + 1)  # 1-based presented slot
    n = len(slots)
    if n == 0:
        return {"top3_capture": 0.0, "lift": 0.0, "p_value": 1.0, "per_slot": []}
    chance = 3.0 / n_catalog
    capture = sum(1 for s in slots if s <= 3) / n
    per_slot = [0.0] * n_catalog
    for s in slots:
        if s <= n_catalog:
            per_slot[s - 1] += 1 / n
    # Null hypothesis: no position preference → each trial's choice lands in a uniformly
    # random presented slot. ("Permute chosen products' slot assignments", TECHSPEC §8.2.)
    if perms and perms > 0:
        rng = random.Random(seed)
        extreme = 0
        for _ in range(perms):
            hits = sum(1 for _ in slots if rng.randrange(n_catalog) < 3)
            if hits / n >= capture:
                extreme += 1
        p_value = extreme / perms
    else:
        p_value = None  # skipped (bootstrap resamples)
    lift = capture / chance if chance else 0.0
    return {"top3_capture": capture, "lift": lift, "p_value": p_value, "per_slot": per_slot}


def m3_framing(c3_trials: list[dict]) -> dict:
    """Per-subset-product Δ = |share_A − share_B|, pooled bulk; plus mean Δ."""
    a: Counter = Counter(t["choice"] for t in _condition(_choices(c3_trials), "C3-A"))
    b: Counter = Counter(t["choice"] for t in _condition(_choices(c3_trials), "C3-B"))
    skus = set(a) | set(b)
    per_product = []
    for sku in sorted(skus):
        na, nb = sum(a.values()) or 1, sum(b.values()) or 1
        sa, sb = a.get(sku, 0) / na, b.get(sku, 0) / nb
        per_product.append({"sku": sku, "share_a": sa, "share_b": sb, "delta": abs(sa - sb)})
    mean_delta = (
        sum(p["delta"] for p in per_product) / len(per_product) if per_product else 0.0
    )
    return {"mean_delta": mean_delta, "per_product": per_product}


def m4_coverage(null_allowed_trials: list[dict]) -> dict:
    """F_task = null rate over parse_ok null-allowed bulk trials + Wilson CI."""
    valid = _parse_ok(_bulk(null_allowed_trials))
    n = len(valid)
    nulls = sum(1 for t in valid if not t.get("choice"))
    lo, hi = wilson_ci(nulls, n)
    by_persona: Counter = Counter()
    totals: Counter = Counter()
    for t in valid:
        totals[t["persona_id"]] += 1
        if not t.get("choice"):
            by_persona[t["persona_id"]] += 1
    nulls_by_persona = [
        {"persona_id": pid, "null_rate": by_persona[pid] / totals[pid]}
        for pid in sorted(totals)
    ]
    return {
        "f_task": nulls / n if n else 0.0,
        "ci_low": lo,
        "ci_high": hi,
        "n": n,
        "nulls_by_persona": nulls_by_persona,
    }


def m5_stability(c1_trials: list[dict]) -> dict:
    """Pairwise cosine of per-model C1 choice-share vectors (bulk only)."""
    by_model: dict[str, Counter] = defaultdict(Counter)
    for t in _condition(_bulk(_choices(c1_trials)), "C1"):
        by_model[t["model"]][t["choice"]] += 1
    vectors = {m: normalize(c) for m, c in by_model.items()}
    models = sorted(vectors)
    matrix = {}
    pairs = []
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            sim = cosine(vectors[a], vectors[b])
            matrix[f"{a}|{b}"] = round(sim, 4)
            pairs.append(sim)
    mean = sum(pairs) / len(pairs) if pairs else 0.0
    band = "aligned" if mean > 0.8 else ("moderate" if mean >= 0.5 else "divergent")
    return {"matrix": matrix, "mean": mean, "band": band}


def demand_shares(all_bulk_trials: list[dict]) -> dict[str, float]:
    return normalize(Counter(t["choice"] for t in _choices(all_bulk_trials)))


def invisible_skus(shares_boot: dict[str, tuple[float, float]], n_catalog: int) -> list[str]:
    fair = 1.0 / n_catalog
    return sorted(sku for sku, (_, hi) in shares_boot.items() if hi < fair)


def score_components(hhi_n: float, stability_mean: float, lift: float,
                     f_task: float, completeness: float) -> dict[str, float]:
    pos_indep = max(0.0, min(1.0, 1 - (lift - 1) / 4))
    comp = {
        "visibility": 1 - hhi_n,
        "stability": max(0.0, min(1.0, stability_mean)),
        "position_indep": pos_indep,
        "coverage": 1 - f_task,
        "data_completeness": max(0.0, min(1.0, completeness)),
    }
    score = 100 * sum(SCORE_WEIGHTS[k] * v for k, v in comp.items())
    return {"components": comp, "score": score}


def compute_all(trials: list[dict], n_catalog: int, completeness: float = 0.0,
                perms: int = PERMUTATION_REPLICATES) -> dict:
    """Point estimates for every headline metric from one trial list."""
    ok = _parse_ok(trials)
    hhi_n, hhi_per_model = m1_concentration(ok, n_catalog)
    pos = m2_position(ok, n_catalog, perms=perms)
    framing = m3_framing(ok)
    cov = m4_coverage([t for t in ok if t.get("null_allowed")])
    stab = m5_stability(ok)
    shares = demand_shares(_bulk(ok))
    sc = score_components(hhi_n, stab["mean"], pos["lift"], cov["f_task"], completeness)
    parse_fail_total = sum(1 for t in trials if not t.get("parse_ok", True))
    parse_rate: dict[str, float] = {}
    by_model_total: Counter = Counter(t["model"] for t in trials)
    fail_by_model: Counter = Counter(t["model"] for t in trials if not t.get("parse_ok", True))
    for m, tot in by_model_total.items():
        parse_rate[m] = fail_by_model.get(m, 0) / tot if tot else 0.0
    return {
        "hhi_norm": hhi_n,
        "hhi_norm_per_model": hhi_per_model,
        "position": pos,
        "framing": framing,
        "coverage": cov,
        "stability": stab,
        "shares": shares,
        "parse_rate": parse_rate,
        "parse_failures": parse_fail_total,
        **sc,
    }
