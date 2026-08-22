"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getRevenue,
  type RevenueResponse,
} from "@/lib/api";
import { inr, inrGrouped, parseInr } from "@/lib/format";
import { getRerunOf } from "@/lib/runs";
import { ErrorBox, PanelSkeleton, Skeleton, SourceChip } from "@/components/Bits";

const SLIDER_VALUES = [0.01, 0.05, 0.1, 0.2];
const DEMO_DEFAULT_GMV = 800000;

export default function RevenuePage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;

  const [sliderIdx, setSliderIdx] = useState(3); // default 20%
  const [gmvText, setGmvText] = useState(inrGrouped(DEMO_DEFAULT_GMV));
  const [gmvTouched, setGmvTouched] = useState(false);
  const [data, setData] = useState<RevenueResponse | null>(null);
  const [rerunId, setRerunId] = useState<string | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const debounceRef = useRef<number | null>(null);

  useEffect(() => {
    setRerunId(getRerunOf(runId));
  }, [runId]);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const rev = await getRevenue(runId, {
          s_agent: SLIDER_VALUES[sliderIdx],
          gmv_inr: undefined, // first load: let the server label its own demo default
          delta_run_id: rerunId ?? undefined,
        });
        if (!alive) return;
        setData(rev);
        setError(null);
      } catch (err) {
        if (!alive) return;
        if (err instanceof ApiError) setError({ code: err.code, message: err.message });
        else setError({ code: "E-UNK", message: "Failed to load revenue model." });
      }
    }
    void load();
    return () => {
      alive = false;
    };
  }, [runId, sliderIdx, rerunId]);

  // refetch when GMV edited (debounced)
  function onGmvChange(text: string) {
    setGmvText(text);
    setGmvTouched(true);
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(async () => {
      const parsed = parseInr(text);
      if (!Number.isFinite(parsed)) return;
      try {
        const rev = await getRevenue(runId, {
          s_agent: SLIDER_VALUES[sliderIdx],
          gmv_inr: parsed,
          delta_run_id: rerunId ?? undefined,
        });
        setData(rev);
        setError(null);
      } catch (err) {
        if (err instanceof ApiError) setError({ code: err.code, message: err.message });
      }
    }, 450);
  }

  const gmvParsed = parseInr(gmvText);
  const gmvValid = Number.isFinite(gmvParsed);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 14 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>Revenue at Risk</h1>
        <span className="sub" style={{ margin: 0 }}>
          run <span className="mono">{runId.slice(0, 8)}</span> ·{" "}
          <Link href={`/audit/${runId}/results`}>back to results</Link>
        </span>
      </div>

      {error ? (
        <ErrorBox code={error.code} message={error.message} />
      ) : !data ? (
        <PanelSkeleton lines={5} />
      ) : (
        <>
          {/* ---------- scenario controls ---------- */}
          <div className="panel">
            <div className="grid-2">
              <div>
                <label className="field-label" htmlFor="sagent-slider">
                  Agent-traffic share <SourceChip kind="assumed" />{" "}
                  <strong style={{ color: "var(--text)" }}>
                    {(SLIDER_VALUES[sliderIdx] * 100).toFixed(0)}%
                  </strong>{" "}
                  <span className="chip gray">you set this</span>
                </label>
                <input
                  id="sagent-slider"
                  type="range"
                  min={0}
                  max={3}
                  step={1}
                  value={sliderIdx}
                  onChange={(e) => setSliderIdx(Number(e.target.value))}
                />
                <div className="snapmarks" style={{ maxWidth: 420 }}>
                  {SLIDER_VALUES.map((v) => (
                    <span key={v}>{(v * 100).toFixed(0)}%</span>
                  ))}
                </div>
              </div>

              <div>
                <label className="field-label" htmlFor="gmv-input">
                  Monthly GMV{" "}
                  <span className={`chip ${gmvTouched ? "gray" : "gray"}`}>
                    {gmvTouched ? "you set this" : "demo default"}
                  </span>
                </label>
                <input
                  id="gmv-input"
                  type="text"
                  inputMode="numeric"
                  value={gmvText}
                  onChange={(e) => onGmvChange(e.target.value)}
                  aria-invalid={!gmvValid}
                />
                {!gmvValid ? (
                  <div style={{ color: "var(--flag)", fontSize: 12, marginTop: 4 }}>
                    E110 — enter a GMV above ₹10,000
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          {/* ---------- outputs ---------- */}
          <div className="grid-2">
            <div className="panel">
              <h2>Revenue at Risk</h2>
              <p className="sub">
                GMV × agent share × measured task-failure rate. Scenario output — it moves
                linearly with the two assumptions above.
              </p>
              <div style={{ fontSize: 28, fontWeight: 700 }} title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
                {inr(data.revenue_at_risk_inr.value)}/mo{" "}
                <span className="ci-range" style={{ fontSize: 15 }}>
                  [{inr(data.revenue_at_risk_inr.ci_low)} – {inr(data.revenue_at_risk_inr.ci_high)}]
                </span>
              </div>
              <div style={{ marginTop: 8, fontSize: 12.5 }}>
                <SourceChip kind="scenario" /> f_task {data.inputs.f_task.value.toFixed(4)}{" "}
                <span className="ci-range">
                  [{data.inputs.f_task.ci_low.toFixed(4)} – {data.inputs.f_task.ci_high.toFixed(4)}]
                </span>{" "}
                <span className="chip teal">measured over 640 trials</span>
              </div>
            </div>

            {data.recoverable_inr ? (
              <div className="panel" style={{ borderColor: "rgba(61,214,140,0.45)" }}>
                <h2>Recoverable</h2>
                <p className="sub">Recovered if the approved fixes hold up — verified by re-run.</p>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--pos)" }} title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
                  {inr(data.recoverable_inr.value)}/mo{" "}
                  <span className="ci-range" style={{ fontSize: 15 }}>
                    [{inr(data.recoverable_inr.ci_low)} – {inr(data.recoverable_inr.ci_high)}]
                  </span>
                </div>
                <div style={{ marginTop: 8, fontSize: 12.5 }}>
                  ΔF {data.delta_f ? data.delta_f.value.toFixed(4) : "—"}{" "}
                  {data.delta_f ? (
                    <span className="ci-range">
                      [{data.delta_f.ci_low.toFixed(4)} – {data.delta_f.ci_high.toFixed(4)}]
                    </span>
                  ) : null}{" "}
                  <span className="chip green">measured ΔF</span>{" "}
                  <Link href={`/delta/${rerunId}`} className="chip blue" style={{ textDecoration: "none" }}>
                    see verification →
                  </Link>
                </div>
              </div>
            ) : (
              <div className="panel">
                <h2>Recoverable</h2>
                <p className="sub" style={{ marginBottom: 0 }}>
                  Appears after a remediation re-run verifies how much risk the fixes actually
                  remove. No verified delta exists for this run yet.
                </p>
                <Link href={`/audit/${runId}/fixes`} style={{ display: "inline-block", marginTop: 10 }}>
                  Review fixes →
                </Link>
              </div>
            )}
          </div>

          {/* ---------- inputs ledger ---------- */}
          <div className="panel">
            <h2>Inputs — every number is labeled by where it came from</h2>
            <table className="data">
              <thead>
                <tr>
                  <th>Input</th>
                  <th>Value</th>
                  <th>Source</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Monthly GMV</td>
                  <td className="mono">{inrGrouped(gmvValid ? gmvParsed : DEMO_DEFAULT_GMV)}</td>
                  <td>
                    <span className="chip gray">{data.inputs.gmv_inr.source === "user" ? "you set this" : "demo default"}</span>
                  </td>
                  <td style={{ color: "var(--muted)" }}>{data.inputs.gmv_inr.note}</td>
                </tr>
                <tr>
                  <td>Agent share (S)</td>
                  <td className="mono">{(data.inputs.s_agent.value * 100).toFixed(0)}%</td>
                  <td>
                    <span className="chip amber">you set this</span>
                  </td>
                  <td style={{ color: "var(--muted)" }}>{data.inputs.s_agent.note}</td>
                </tr>
                <tr>
                  <td>Task failure rate (F_task)</td>
                  <td className="mono">
                    {(data.inputs.f_task.value * 100).toFixed(1)}%{" "}
                    <span className="ci-range">
                      [{(data.inputs.f_task.ci_low * 100).toFixed(1)} – {(data.inputs.f_task.ci_high * 100).toFixed(1)}]
                    </span>
                  </td>
                  <td>
                    <span className="chip teal">measured over 640 trials</span>
                  </td>
                  <td style={{ color: "var(--muted)" }}>{data.inputs.f_task.note}</td>
                </tr>
              </tbody>
            </table>
            <div className="honesty-note">{data.honesty_note}</div>
          </div>
        </>
      )}
    </div>
  );
}
