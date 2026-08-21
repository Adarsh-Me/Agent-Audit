"""Revenue-at-Risk model — PRD §8.6 / TECHSPEC §10. Every input labeled; every output CI'd.

  RaR          = GMV_monthly × s_agent × F_task
  Recoverable  = GMV_monthly × s_agent × max(0, ΔF)      (ΔF = F_before − F_after)

Honesty rules:
  - s_agent is the merchant's slider (share of buyers arriving via AI agents) — an
    assumption, never a measurement.
  - GMV is user-provided or, for the demo only, a labeled default of ₹8,00,000/mo.
  - F_task carries its Wilson CI; RaR bounds come from those bounds.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.constants import S_AGENT_DEFAULT, S_AGENT_SLIDER

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


def validate_slider(s_agent: float) -> float:
    if not any(abs(s_agent - v) < 1e-9 for v in S_AGENT_SLIDER):
        raise ValueError(f"s_agent must be one of {S_AGENT_SLIDER}")
    return s_agent


def compute_revenue(inputs: RevenueInputs) -> dict:
    rar_point = inputs.gmv_inr * inputs.s_agent * inputs.f_task
    rar_low = inputs.gmv_inr * inputs.s_agent * inputs.f_task_ci[0]
    rar_high = inputs.gmv_inr * inputs.s_agent * inputs.f_task_ci[1]

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
                        "note": "share of agent shopping tasks that ended in no purchase "
                                "(640-trial audit)"},
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
