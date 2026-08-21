"""Persona-cluster bootstrap — every CI in the product (TECHSPEC §8.7).

Resample PERSONAS with replacement (trials within a persona correlate), recompute all
metrics on the same resample, take percentile 95. The score CI is propagated, not assumed.
"""
from __future__ import annotations

import random
from collections import defaultdict

from app.constants import BOOTSTRAP_REPLICATES
from app.stats.metrics import compute_all, percentile_ci


def cluster_bootstrap(
    trials: list[dict],
    n_catalog: int,
    completeness: float = 0.0,
    B: int = BOOTSTRAP_REPLICATES,
    seed: int = 42,
) -> dict[str, tuple[float, float]]:
    """Returns {metric_path: (ci_low, ci_high)} for headline metrics + per-SKU shares.

    metric paths: hhi_norm, position.top3_capture, framing.mean_delta, coverage.f_task,
    stability.mean, score, share:{sku}
    """
    by_persona: dict[str, list[dict]] = defaultdict(list)
    for t in trials:
        by_persona[t["persona_id"]].append(t)
    personas = sorted(by_persona)
    if not personas:
        return {}

    rng = random.Random(seed)
    samples: dict[str, list[float]] = defaultdict(list)
    share_samples: dict[str, list[float]] = defaultdict(list)

    for _ in range(B):
        picked = [personas[rng.randrange(len(personas))] for _ in range(len(personas))]
        resampled = [t for pid in picked for t in by_persona[pid]]
        m = compute_all(resampled, n_catalog, completeness=completeness, perms=0)
        samples["hhi_norm"].append(m["hhi_norm"])
        samples["position.top3_capture"].append(m["position"]["top3_capture"])
        samples["framing.mean_delta"].append(m["framing"]["mean_delta"])
        samples["coverage.f_task"].append(m["coverage"]["f_task"])
        samples["stability.mean"].append(m["stability"]["mean"])
        samples["score"].append(m["score"])
        for sku, s in m["shares"].items():
            share_samples[sku].append(s)

    out = {
        "hhi_norm": percentile_ci(samples["hhi_norm"]),
        "position.top3_capture": percentile_ci(samples["position.top3_capture"]),
        "framing.mean_delta": percentile_ci(samples["framing.mean_delta"]),
        "coverage.f_task": percentile_ci(samples["coverage.f_task"]),
        "stability.mean": percentile_ci(samples["stability.mean"]),
        "score": percentile_ci(samples["score"]),
    }
    # SKUs absent from a resample have share 0 — include the implicit zeros
    for sku in set(share_samples):
        vals = share_samples[sku] + [0.0] * (B - len(share_samples[sku]))
        out[f"share:{sku}"] = percentile_ci(vals)
    return out


def bootstrap_f_task_delta(trials_before: list[dict], trials_after: list[dict],
                           n_catalog: int, B: int = 1000, seed: int = 42) -> tuple[float, float, float]:
    """ΔF = F_before − F_after with paired-ish bootstrap CI (same persona draws both sides)."""
    def personas_of(trials):
        d = defaultdict(list)
        for t in trials:
            d[t["persona_id"]].append(t)
        return sorted(d), d

    p_b, d_b = personas_of(trials_before)
    p_a, d_a = personas_of(trials_after)
    common = sorted(set(p_b) & set(p_a)) or p_b

    rng = random.Random(seed)
    deltas = []
    for _ in range(B):
        picked = [common[rng.randrange(len(common))] for _ in range(len(common))]
        mb = compute_all([t for pid in picked for t in d_b.get(pid, [])], n_catalog, perms=0)
        ma = compute_all([t for pid in picked for t in d_a.get(pid, [])], n_catalog, perms=0)
        deltas.append(mb["coverage"]["f_task"] - ma["coverage"]["f_task"])
    from app.stats.metrics import percentile_ci
    lo, hi = percentile_ci(deltas)
    point = compute_all(trials_before, n_catalog, perms=0)["coverage"]["f_task"] - \
        compute_all(trials_after, n_catalog, perms=0)["coverage"]["f_task"]
    return point, lo, hi
