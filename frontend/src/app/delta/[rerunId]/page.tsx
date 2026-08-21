"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ApiError,
  getDelta,
  getMetrics,
  type DeltaResponse,
} from "@/lib/api";
import { inr, num1, num2, pct } from "@/lib/format";
import { ErrorBox, PanelSkeleton, SourceChip } from "@/components/Bits";
import { ScoreDial } from "@/components/Dial";

const HONEST_FALLBACK_TITLE = "Delta within statistical noise.";
const HONEST_FALLBACK_BODY =
  "The before/after confidence intervals overlap, so we cannot claim this remediation moved agent demand on this catalog. The persistent gap is consistent with model-side bias documented in ACES (2025) — which is itself the finding. We do not tune seeds to manufacture a bigger number.";

interface DialCis {
  original: { lo: number; hi: number };
  rerun: { lo: number; hi: number };
}

export default function DeltaPage() {
  const params = useParams<{ rerunId: string }>();
  const rerunId = params.rerunId;

  const [delta, setDelta] = useState<DeltaResponse | null>(null);
  const [cis, setCis] = useState<DialCis | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const d = await getDelta(rerunId);
        if (!alive) return;
        setDelta(d);
        // delta endpoint reports point scores only; pull each run's metrics for the CIs
        try {
          const [before, after] = await Promise.all([
            getMetrics(d.original_run_id),
            getMetrics(d.rerun_run_id),
          ]);
          if (!alive) return;
          if ("score" in before && "score" in after) {
            setCis({
              original: { lo: before.score.ci_low, hi: before.score.ci_high },
              rerun: { lo: after.score.ci_low, hi: after.score.ci_high },
            });
          }
        } catch {
          /* dials still render from delta points; CI rows show when available */
        }
      } catch (err) {
        if (!alive) return;
        if (err instanceof ApiError) setError({ code: err.code, message: err.message });
        else setError({ code: "E-UNK", message: "Failed to load delta." });
      }
    })();
    return () => {
      alive = false;
    };
  }, [rerunId]);

  if (error) {
    return (
      <ErrorBox code={error.code} message={error.message}>
        <Link href="/">← Back to setup</Link>
      </ErrorBox>
    );
  }

  if (!delta) return <PanelSkeleton lines={6} />;

  // Non-overlap in the improvement direction ⇒ distinguishable; else render the honest panel.
  const ciOverlap =
    delta.f_task.after.ci_low < delta.f_task.before.ci_high &&
    delta.verdict.startsWith("coverage failure fell");
  const maxAbsChange = Math.max(...delta.per_sku_changes.map((c) => c.abs_change), 0.0001);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 14 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>Verification — did the fixes work?</h1>
        <span className="chip blue">verified re-run</span>
      </div>
      <p className="sub">
        Same 640-trial protocol against the mirrored catalog. Original run{" "}
        <span className="mono">{delta.original_run_id.slice(0, 8)}</span> vs re-run{" "}
        <span className="mono">{delta.rerun_run_id.slice(0, 8)}</span>.
      </p>

      {/* ---------- score dials ---------- */}
      <div className="panel">
        <div className="grid-2" style={{ alignItems: "center" }}>
          <div className="dial-wrap">
            <ScoreDial
              score={delta.score.before}
              lo={cis?.original.lo}
              hi={cis?.original.hi}
              size={150}
            />
            <div className="dial-label">Before · AgentReady</div>
          </div>
          <div className="dial-wrap">
            <ScoreDial
              score={delta.score.after}
              lo={cis?.rerun.lo}
              hi={cis?.rerun.hi}
              size={150}
            />
            <div className="dial-label">After · AgentReady</div>
          </div>
        </div>
        <p style={{ textAlign: "center", margin: "8px 0 0", fontSize: 16 }}>
          <strong>
            {num1(delta.score.before)} → {num1(delta.score.after)}
          </strong>{" "}
          {!cis ? (
            <span className="ci-range">(CI from run metrics unavailable)</span>
          ) : null}
        </p>
      </div>

      {/* ---------- coverage delta ---------- */}
      <div className="grid-2">
        <div className="panel">
          <h2>Coverage failure rate F_task</h2>
          <table className="data">
            <tbody>
              <tr>
                <td>Before</td>
                <td title="Wilson 95% confidence interval">
                  <strong>{pct(delta.f_task.before.value)}</strong>{" "}
                  <span className="ci-range">
                    [{pct(delta.f_task.before.ci_low)} – {pct(delta.f_task.before.ci_high)}]
                  </span>
                </td>
              </tr>
              <tr>
                <td>After</td>
                <td title="Wilson 95% confidence interval">
                  <strong>{pct(delta.f_task.after.value)}</strong>{" "}
                  <span className="ci-range">
                    [{pct(delta.f_task.after.ci_low)} – {pct(delta.f_task.after.ci_high)}]
                  </span>
                </td>
              </tr>
              <tr>
                <td>ΔF</td>
                <td title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
                  <strong>{(delta.f_task.delta.value * 100).toFixed(1)} pts</strong>{" "}
                  <span className="ci-range">
                    [{(delta.f_task.delta.ci_low * 100).toFixed(1)} – {(delta.f_task.delta.ci_high * 100).toFixed(1)}]
                  </span>{" "}
                  <SourceChip kind="measured" />
                </td>
              </tr>
            </tbody>
          </table>
          <p style={{ fontSize: 13.5, marginTop: 10 }}>
            Verdict: <strong>{delta.verdict}</strong>
          </p>
          <div className="metric-foot">{delta.honest_note}</div>
        </div>

        <div className="panel">
          <h2>Money recovered</h2>
          {delta.recoverable_inr ? (
            <>
              <div style={{ fontSize: 26, fontWeight: 700, color: "var(--green)" }} title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
                <span className="chip green" style={{ marginRight: 8 }}>Recoverable</span>
                {inr(delta.recoverable_inr.value)}/mo{" "}
                <span className="ci-range" style={{ fontSize: 14 }}>
                  [{inr(delta.recoverable_inr.ci_low)} – {inr(delta.recoverable_inr.ci_high)}]
                </span>
              </div>
              <p className="sub" style={{ marginTop: 10 }}>
                {delta.recoverable_inr.note ??
                  "recoverable if approved fixes are applied (verified by re-run)"}
              </p>
            </>
          ) : (
            <p className="sub">No recoverable estimate reported.</p>
          )}
          <Link
            href={`/checkout/${delta.original_run_id}`}
            className="btn primary"
            style={{ display: "inline-block", marginTop: 8 }}
          >
            Prove it can buy →
          </Link>
        </div>
      </div>

      {/* ---------- per-SKU changes ---------- */}
      <div className="panel">
        <h2>Per-product demand shift — top movers</h2>
        <p className="sub">Biggest absolute share changes between the two runs.</p>
        <table className="data">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Share before</th>
              <th>Share after</th>
              <th>|Δ|</th>
              <th style={{ width: "30%" }}>Change</th>
            </tr>
          </thead>
          <tbody>
            {delta.per_sku_changes.map((c) => {
              const gained = c.share_after >= c.share_before;
              return (
                <tr key={c.sku}>
                  <td className="mono">{c.sku}</td>
                  <td>{num2(c.share_before * 100)}%</td>
                  <td>{num2(c.share_after * 100)}%</td>
                  <td>{num2(c.abs_change * 100)}%</td>
                  <td>
                    <div className="bar-track">
                      <div
                        className={`bar-fill ${gained ? "green" : "rose"}`}
                        style={{ width: `${(c.abs_change / maxAbsChange) * 100}%` }}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="metric-foot">
          shares are pooled across models/conditions
          {delta.per_sku_changes.length >= 15 ? " · top 15 shown" : ""}
        </div>
      </div>

      {/* ---------- honest fallback ---------- */}
      {ciOverlap ? (
        <div className="banner amber" style={{ padding: 16 }}>
          <strong>{HONEST_FALLBACK_TITLE}</strong>
          <br />
          {HONEST_FALLBACK_BODY}
        </div>
      ) : null}
    </div>
  );
}
