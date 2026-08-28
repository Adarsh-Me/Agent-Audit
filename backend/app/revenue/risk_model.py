"""Revenue-at-Risk model — PRD §8.6 / TECHSPEC §10. Every input labeled; every output CI'd.

  RaR          = GMV_monthly × s_agent × F_task
  Recoverable  = GMV_monthly × s_agent × max(0, ΔF)      (ΔF = F_before − F_after)

Honesty rules:
  - s_agent is the merchant's slider (share of buyers arriving via AI agents) — an
    assumption, never a measurement.
  - GMV is user-provided or, for the demo only, a labeled default of ₹8,00,000/mo.
  - F_task carries its Wilson CI; RaR bounds come from those bounds.
  - When zero usable missions exist, F_task is a placeholder (wilson sentinel [0,1])
    and RaR refuses to print ₹0 — "unknown" is not "safe".
"""
from __future__ import annotations

from dataclasses import dataclass

from app.constants import S_AGENT_DEFAULT, S_AGENT_SLIDER, TRIALS_PER_FULL_RUN

GMV_DEMO_DEFAULT_INR = 800_000


@dataclass
class RevenueInputs:
    gmv_inr: int
    gmv_source: str          # 'user' | 'demo-default'
    s_agent: float
    s_agent_source: str      # 'slider'
    f_task: float
    f_task_ci: tuple[float, float]
    delta_f: tuple[float, float, float] | None = None  # (point, lo, hi) when rerun exists
    # parse-OK, bulk-tier, null-allowed trials F_task was computed over.
    # 0 ⇒ f_task/f_task_ci are the "no data" placeholder — RaR returns
    # revenue_at_risk_inr=None with a not_measurable explanation instead of ₹0.
    usable_trials: int | None = None


def validate_slider(s_agent: float) -> float:
    if not any(abs(s_agent - v) < 1e-9 for v in S_AGENT_SLIDER):
        raise ValueError(f"s_agent must be one of {S_AGENT_SLIDER}")
    return s_agent


def compute_revenue(inputs: RevenueInputs) -> dict:
    # --- not-measurable guard -------------------------------------------------
    # wilson_ci(n=0) returns the (0.0, 1.0) "no data" sentinel and m4_coverage
    # then reports f_task=0.0. Multiplying that placeholder through would show a
    # confident ₹0 at risk — "unknown" disguised as "safe". Refuse instead.
    if inputs.usable_trials == 0:
        return {
            "inputs": {
                "gmv_inr": {"value": inputs.gmv_inr, "source": inputs.gmv_source,
                            "note": "monthly catalog GMV in INR"},
                "s_agent": {"value": inputs.s_agent, "source": inputs.s_agent_source,
                            "note": "your estimate of the share of buyers arriving via AI agents — "
                                    "an assumption you control"},
                "f_task": {"value": None, "source": "measured",
                           "ci_low": None, "ci_high": None,
                           "usable_trials": 0,
                           "note": "no shopping mission returned a usable answer "
                                   "(provider errors / truncated responses) — "
                                   "task-failure rate is unknown"},
            },
            "revenue_at_risk_inr": None,
            "not_measurable": True,
            "not_measurable_note": "0 usable shopping missions — every trial failed to parse "
                                   "or the provider errored, so the walk-away rate is unknown. "
                                   "₹0 here would mean unknown, not safe. Re-run the audit "
                                   "when the model provider is healthy.",
            "honesty_note": "If your AI share is lower than the slider, scale the number down "
                            "linearly — the model is deliberately simple and labeled.",
            "recoverable_inr": None,
            "delta_f": None,
        }

    rar_point = inputs.gmv_inr * inputs.s_agent * inputs.f_task
    rar_low = inputs.gmv_inr * inputs.s_agent * inputs.f_task_ci[0]
    rar_high = inputs.gmv_inr * inputs.s_agent * inputs.f_task_ci[1]

    zero_measured_note = (
        "Every measured mission ended in a purchase — ₹0 is a measured result here, "
        f"not missing data ({inputs.usable_trials} usable missions)."
        if inputs.usable_trials is not None and inputs.usable_trials > 0
        and inputs.f_task == 0.0
        else None
    )

    out = {
        "inputs": {
            "gmv_inr": {"value": inputs.gmv_inr, "source": inputs.gmv_source,
                        "note": "monthly catalog GMV in INR"},
            "s_agent": {"value": inputs.s_agent, "source": inputs.s_agent_source,
                        "note": "your estimate of the share of buyers arriving via AI agents — "
                                "an assumption you control"},
            "f_task": {"value": round(inputs.f_task, 4), "source": "measured",
                       "ci_low": round(inputs.f_task_ci[0], 4),
                       "ci_high": round(inputs.f_task_ci[1], 4),
                       "usable_trials": inputs.usable_trials,
                       "note": "share of agent shopping tasks that ended in no purchase "
                               f"({TRIALS_PER_FULL_RUN}-trial audit)"},
        },
        "revenue_at_risk_inr": {
            "value": round(rar_point),
            "ci_low": round(rar_low),
            "ci_high": round(rar_high),
        },
        "honesty_note": "If your AI share is lower than the slider, scale the number down "
                        "linearly — the model is deliberately simple and labeled.",
        "recoverable_inr": None,
        "delta_f": None,
    }
    if zero_measured_note:
        out["zero_measured_note"] = zero_measured_note

    if inputs.delta_f is not None:
        d_point, d_lo, d_hi = inputs.delta_f
        recov = max(0.0, d_point) * inputs.gmv_inr * inputs.s_agent
        out["delta_f"] = {"value": round(d_point, 4), "ci_low": round(d_lo, 4),
                          "ci_high": round(d_hi, 4)}
        # recoverable CI uses the delta CI (clamped at 0)
        out["recoverable_inr"] = {
            "value": round(recov),
            "ci_low": round(max(0.0, d_lo) * inputs.gmv_inr * inputs.s_agent),
            "ci_high": round(max(0.0, d_hi) * inputs.gmv_inr * inputs.s_agent),
            "note": "recoverable if approved fixes are applied (verified by re-run)",
        }
    return out


def demo_inputs(f_task: float, f_task_ci: tuple[float, float],
                s_agent: float = S_AGENT_DEFAULT,
                delta_f: tuple[float, float, float] | None = None) -> RevenueInputs:
    return RevenueInputs(
        gmv_inr=GMV_DEMO_DEFAULT_INR, gmv_source="demo-default",
        s_agent=s_agent, s_agent_source="slider",
        f_task=f_task, f_task_ci=f_task_ci, delta_f=delta_f,
    )
