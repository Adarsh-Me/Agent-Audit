"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  getAudit,
  getReport,
  getRevenue,
  type AuditStatusResponse,
  type InvisibleSku,
  type LegibilityRow,
  type MetricsPayload,
  type RevenueResponse,
} from "@/lib/api";
import { inr, num1, num2, pct, usd } from "@/lib/format";
import { getLastRun, getRerunOf } from "@/lib/runs";
import { ErrorBox, PanelSkeleton, Skeleton, SourceChip, StatCard, TierChip } from "@/components/Bits";
import { ScoreDial } from "@/components/Dial";

const PARTIAL_BANNER =
  "Partial run — cost cap hit. Numbers below are real but incomplete.";
const STRIP_CAPTION =
  "Scenario model. Measured: task-failure rate, concentration, remediation delta. Assumed: agent-traffic share — you set it.";
const SLIDER_VALUES = [0.01, 0.05, 0.1, 0.2];
const DEFAULT_S_AGENT = 0.2;
/** Fair share = 1/N (N=40 demo SKUs) = 2.5% */
const FAIR_SHARE = 1 / 40;

export default function ResultsPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;

  const [status, setStatus] = useState<AuditStatusResponse["status"] | "loading">("loading");
  const [report, setReport] = useState<(MetricsPayload & { legibility?: LegibilityRow[] }) | null>(null);
  const [preview, setPreview] = useState<RevenueResponse | null>(null);
  const [recoverable, setRecoverable] = useState<RevenueResponse["recoverable_inr"]>(null);
  const [rerunId, setRerunId] = useState<string | null>(null);
  const [sAgent, setSAgent] = useState(DEFAULT_S_AGENT);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  useEffect(() => {
    let alive = true;

    async function load() {
      try {
        // wait for a terminal status before pulling computed metrics
        let st: AuditStatusResponse;
        for (;;) {
          st = await getAudit(runId);
          if (!alive) return;
          if (st.status === "done" || st.status === "partial" || st.status === "failed") break;
          await new Promise((r) => setTimeout(r, 2000));
        }
        if (!alive) return;
        if (st.status === "failed") {
          setStatus("failed");
          return;
        }
        setStatus(st.status);
        const rep = await getReport(runId);
        if (!alive) return;
        setReport(rep);
        setPreview(rep.revenue_preview);
      } catch (err) {
        if (!alive) return;
        if (err instanceof ApiError) setError({ code: err.code, message: err.message });
        else setError({ code: "E-UNK", message: "Failed to load results." });
      }
    }
    void load();
    return () => {
      alive = false;
    };
  }, [runId]);

  // rerun linkage → recoverable
  useEffect(() => {
    setRerunId(getRerunOf(runId));
  }, [runId]);

  useEffect(() => {
    if ((status !== "done" && status !== "partial") || !rerunId) return;
    let alive = true;
    getRevenue(runId, {
      s_agent: DEFAULT_S_AGENT,
      delta_run_id: rerunId,
    })
      .then((rev) => {
        if (alive) setRecoverable(rev.recoverable_inr);
      })
      .catch(() => {
        /* recoverable stays hidden — it only appears when a rerun delta exists */
      });
    return () => {
      alive = false;
    };
  }, [runId, status, rerunId]);

  const invisibleBySku = useMemo(() => {
    const m = new Map<string, InvisibleSku>();
    for (const inv of report?.invisible_skus ?? []) m.set(inv.sku, inv);
    return m;
  }, [report]);

  const movers = useMemo(
    () =>
      [...(report?.framing.per_product ?? [])]
        .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
        .slice(0, 5),
    [report],
  );

  if (error) {
    return (
      <ErrorBox code={error.code} message={error.message}>
        <Link href="/">← Back to setup</Link>
      </ErrorBox>
    );
  }

  if (status === "failed") {
    return (
      <div className="banner red">
        This run failed. <Link href="/">Start a new audit</Link>.
      </div>
    );
  }

  if (!report) {
    return (
      <div>
        <PanelSkeleton lines={3} />
        <PanelSkeleton lines={5} />
        <PanelSkeleton lines={5} />
      </div>
    );
  }

  // RaR scales linearly with the slider (multiplication only — never a measured quantity)
  const baseRar = preview?.revenue_at_risk_inr;
  const rarScale =
    baseRar && preview && preview.inputs.s_agent.value > 0
      ? sAgent / preview.inputs.s_agent.value
      : 0;

  return (
    <div>
      {report.partial || status === "partial" ? (
        <div className="banner amber">{PARTIAL_BANNER}</div>
      ) : null}

      {/* ---------- sticky three-number strip ---------- */}
      <div className="sticky-strip">
        <div className="strip-grid">
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            <ScoreDial score={report.score.value} lo={report.score.ci_low} hi={report.score.ci_high} size={110} />
            <div>
              <div className="dial-label">AgentReady Score</div>
              <div
                className="ci-range"
                title="95% confidence interval, persona-cluster bootstrap, B = 2,000"
                style={{ fontSize: 12.5 }}
              >
                [{report.score.ci_low.toFixed(1)} – {report.score.ci_high.toFixed(1)}]
              </div>
            </div>
          </div>

          <div>
            <div className="dial-label">Revenue at Risk /mo @ {(sAgent * 100).toFixed(0)}%</div>
            {baseRar ? (
              <>
                <div style={{ fontSize: 22, fontWeight: 700 }} title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
                  {inr(baseRar.value * rarScale)}{" "}
                  <span className="ci-range" style={{ fontSize: 13 }}>
                    [{inr(baseRar.ci_low * rarScale)} – {inr(baseRar.ci_high * rarScale)}]
                  </span>
                </div>
                <div style={{ marginTop: 2 }}>
                  F_task {pct(report.coverage.f_task.value)}{" "}
                  <span className="ci-range">
                    [{pct(report.coverage.f_task.ci_low)} – {pct(report.coverage.f_task.ci_high)}]
                  </span>{" "}
                  <SourceChip kind="measured" /> · S={(sAgent * 100).toFixed(0)}%{" "}
                  <SourceChip kind="assumed" />
                </div>
              </>
            ) : (
              <Skeleton w="60%" />
            )}
          </div>

          <div>
            <div className="dial-label">Recoverable</div>
            {recoverable ? (
              <>
                <div style={{ fontSize: 22, fontWeight: 700, color: "var(--green)" }} title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
                  {inr(recoverable.value)}/mo{" "}
                  <span className="ci-range" style={{ fontSize: 13 }}>
                    [{inr(recoverable.ci_low)} – {inr(recoverable.ci_high)}]
                  </span>
                </div>
                <span className="chip teal">[measured ΔF]</span>{" "}
                <span className="chip green">verified re-run</span>
              </>
            ) : (
              <>
                <div style={{ color: "var(--muted)", fontSize: 18 }}>—</div>
                <div style={{ color: "var(--faint)", fontSize: 11.5 }}>(after remediation re-run)</div>
              </>
            )}
          </div>
        </div>

        <div className="strip-caption">
          {STRIP_CAPTION}
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, marginLeft: 12 }}>
            <input
              type="range"
              min={0}
              max={3}
              step={1}
              value={SLIDER_VALUES.indexOf(sAgent)}
              onChange={(e) => setSAgent(SLIDER_VALUES[Number(e.target.value)])}
              aria-label="agent-traffic share"
              style={{ width: 140 }}
            />
            <span className="snapmarks" style={{ width: 130 }}>
              <span>1%</span><span>5%</span><span>10%</span><span>20%</span>
            </span>
          </span>
        </div>
      </div>

      {/* ---------- S1 choice heat list ---------- */}
      <div className="panel">
        <h2>Choice heat map</h2>
        <p className="sub">
          How agent demand spread across the catalog. Concentration (HHI, normalized):{" "}
          <span title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
            {num2(report.hhi_norm.value)}{" "}
            <span className="ci-range">
              [{num2(report.hhi_norm.ci_low)} – {num2(report.hhi_norm.ci_high)}]
            </span>
          </span>{" "}
          — higher means agents pile onto fewer products.
        </p>
        <table className="data">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Title</th>
              <th>Tier</th>
              <th>Demand share</th>
              <th>Legibility</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(report.legibility ?? []).map((row) => {
              const inv = invisibleBySku.get(row.sku);
              const comp = row.composite ?? 0;
              return (
                <tr key={row.sku} className={inv ? "invisible-row" : ""}>
                  <td className="mono">
                    {inv ? "⚠ " : ""}
                    {row.sku}
                  </td>
                  <td>{row.title}</td>
                  <td><TierChip tier={row.tier} /></td>
                  <td>
                    {inv ? (
                      <span title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
                        <Barish value={inv.share.value} /> {pct(inv.share.value)}{" "}
                        <span className="ci-range">
                          [{pct(inv.share.ci_low)} – {pct(inv.share.ci_high)}]
                        </span>
                      </span>
                    ) : (
                      <span style={{ color: "var(--faint)" }}>—</span>
                    )}
                  </td>
                  <td style={{ minWidth: 110 }}>
                    <div className="bar-track">
                      <div className="bar-fill blue" style={{ width: `${comp * 100}%` }} />
                    </div>
                    <span style={{ color: "var(--faint)", fontSize: 11 }}>{row.composite !== null ? num2(comp) : "n/a"}</span>
                  </td>
                  <td>
                    {inv ? <span className="chip rose">⚠ Invisible</span> : <span className="chip gray">Visible</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="metric-foot">
          legend: Hatched = agent-invisible (95% CI upper bound below 2.5% fair share) · demand share renders only where the API reports it (invisible SKUs); “—” = per-SKU share not exposed by current backend · metric: hhi_norm
          {report.partial ? ` · computed on ${report.trials.total}/640 trials` : ""}
        </div>
      </div>

      {/* ---------- Invisible-to-agents strip ---------- */}
      <div className="panel">
        <h2>Invisible to agents</h2>
        <p className="sub">
          Flagged because the upper bound of their 95% demand-share interval sits below fair
          share (1/N = 2.5%) — an agent picking uniformly at random would beat them.
        </p>
        {report.invisible_skus.length === 0 ? (
          <p className="sub" style={{ color: "var(--green)" }}>
            None flagged in this run.
          </p>
        ) : (
          <div className="stat-cards">
            {report.invisible_skus.map((s) => (
              <StatCard
                key={s.sku}
                k={s.sku}
                v={
                  <span title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
                    {pct(s.share.value)}{" "}
                    <span className="ci-range" style={{ fontSize: 12 }}>
                      [{pct(s.share.ci_low)} – {pct(s.share.ci_high)}]
                    </span>
                  </span>
                }
                sub={<span style={{ color: "var(--rose)" }}>CI-upper &lt; 1/N → invisible</span>}
              />
            ))}
          </div>
        )}
      </div>

      {/* ---------- Framing sensitivity ---------- */}
      <div className="panel">
        <h2>Framing sensitivity</h2>
        <p className="sub">
          Rewriting listing copy (condition C3-A vs C3-B) shifts agent choices. Mean shift across
          the framing subset:{" "}
          <span title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
            {pct(report.framing.mean_delta.value)}{" "}
            <span className="ci-range">
              [{pct(report.framing.mean_delta.ci_low)} – {pct(report.framing.mean_delta.ci_high)}]
            </span>
          </span>
        </p>
        {movers.length > 0 ? (
          <table className="data">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Share A (control copy)</th>
                <th>Share B (variant copy)</th>
                <th>Δ</th>
              </tr>
            </thead>
            <tbody>
              {movers.map((m) => (
                <tr key={m.sku}>
                  <td className="mono">{m.sku}</td>
                  <td>{pct(m.share_a)}</td>
                  <td>{pct(m.share_b)}</td>
                  <td
                    style={{
                      color:
                        Math.abs(m.delta) > report.framing.mean_delta.value
                          ? "var(--amber)"
                          : undefined,
                    }}
                  >
                    {m.delta >= 0 ? "+" : ""}
                    {pct(m.delta)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="sub">No framing-subset data reported for this catalog.</p>
        )}
        <div className="metric-foot">metric: framing.mean_delta</div>
      </div>

      {/* ---------- Stability + Position ---------- */}
      <div className="grid-2">
        <div className="panel">
          <h2>Stability across models</h2>
          <p className="sub">
            Pairwise cosine similarity of product rankings between models. Mean:{" "}
            <span title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
              {num2(report.stability.mean.value)}{" "}
              <span className="ci-range">
                [{num2(report.stability.mean.ci_low)} – {num2(report.stability.mean.ci_high)}]
              </span>
            </span>{" "}
            <BandChip band={report.stability.band} />
          </p>
          <StabilityMatrix matrix={report.stability.matrix} />
          <div className="metric-foot">aligned &gt; 0.8 · moderate 0.5–0.8 · divergent &lt; 0.5 · metric: stability.mean</div>
        </div>

        <div className="panel">
          <h2>Position bias</h2>
          <p className="sub">
            Agents favor what&rsquo;s listed first; randomized order (C2) isolates this.
          </p>
          <ul style={{ margin: "0 0 10px", paddingLeft: 18, fontSize: 13 }}>
            <li>
              Top-3 capture:{" "}
              <span title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
                {pct(report.position.top3_capture.value)}{" "}
                <span className="ci-range">
                  [{pct(report.position.top3_capture.ci_low)} – {pct(report.position.top3_capture.ci_high)}]
                </span>
              </span>
            </li>
            <li>Lift vs chance: {num1(report.position.lift)}×</li>
            <li>
              Permutation p-value:{" "}
              {report.position.p_value < 0.001 ? "< 0.001" : report.position.p_value.toFixed(4)}{" "}
              {report.position.p_value < 0.05 ? (
                <span className="chip green">significant</span>
              ) : (
                <span className="chip gray">not significant</span>
              )}
            </li>
          </ul>
          <SlotChart perSlot={report.position.per_slot} />
          <div className="metric-foot">dashed line = 2.5% fair share per slot · metric: position.top3_capture</div>
        </div>
      </div>

      {/* ---------- Coverage ---------- */}
      <div className="panel">
        <h2>Coverage — &ldquo;nothing fits&rdquo; rate</h2>
        <p className="sub">
          Share of agent tasks that ended with no purchase:{" "}
          <span title="95% confidence interval, Wilson score" style={{ fontSize: 16 }}>
            <strong>{pct(report.coverage.f_task.value)}</strong>{" "}
            <span className="ci-range">
              [{pct(report.coverage.f_task.ci_low)} – {pct(report.coverage.f_task.ci_high)}]
            </span>
          </span>{" "}
          <SourceChip kind="measured" /> — this measured failure rate drives the Revenue-at-Risk
          model.
        </p>
        {report.coverage.nulls_by_persona.length > 0 ? (
          <table className="data" style={{ maxWidth: 420 }}>
            <thead>
              <tr>
                <th>Persona</th>
                <th>Null rate</th>
              </tr>
            </thead>
            <tbody>
              {[...report.coverage.nulls_by_persona]
                .sort((a, b) => b.null_rate - a.null_rate)
                .slice(0, 5)
                .map((p) => (
                  <tr key={p.persona_id}>
                    <td className="mono">{p.persona_id}</td>
                    <td>{pct(p.null_rate)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        ) : null}
        <div className="metric-foot">metric: coverage.f_task</div>
      </div>

      {/* ---------- Run footer ---------- */}
      <div className="panel">
        <h2>Run details</h2>
        <div className="stat-cards">
          <StatCard
            k="Trials"
            v={`${report.trials.total}`}
            sub={`${report.trials.parse_ok} parsed ok · ${report.trials.forced} forced-choice`}
          />
          <StatCard k="Cost" v={usd(report.cost_usd)} sub="billed provider spend" />
          <StatCard k="Run id" v={<span className="mono" style={{ fontSize: 13 }}>{report.run_id.slice(0, 8)}</span>} sub={report.manifest_ref ?? "live run"} />
        </div>
        <table className="data" style={{ maxWidth: 480 }}>
          <thead>
            <tr>
              <th>Model</th>
              <th>Parse-failure rate</th>
            </tr>
          </thead>
          <tbody>
            {report.models_meta.map((m) => (
              <tr key={m.id}>
                <td className="mono">{m.id}</td>
                <td>{pct(m.parse_failure_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* CTAs */}
      <div className="cta-stack">
        <Link href={`/checkout/${runId}`} className="btn">
          Watch an agent buy →
        </Link>
        <Link href={`/audit/${runId}/fixes`} className="btn primary">
          Fix what&rsquo;s broken →
        </Link>
      </div>
    </div>
  );
}

function BandChip({ band }: { band: string }) {
  const cls = band === "aligned" ? "green" : band === "moderate" ? "amber" : "rose";
  return <span className={`chip ${cls}`}>{band}</span>;
}

function StabilityMatrix({ matrix }: { matrix: Record<string, number> }) {
  const entries = Object.entries(matrix);
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {entries.map(([pair, val]) => {
        const cls = val > 0.8 ? "green" : val >= 0.5 ? "amber" : "rose";
        return (
          <div
            key={pair}
            style={{
              display: "grid",
              gridTemplateColumns: "170px 1fr 44px",
              gap: 10,
              alignItems: "center",
              fontSize: 12.5,
            }}
          >
            <span className="mono" style={{ color: "var(--muted)" }}>
              {pair.replace("|", " ↔ ")}
            </span>
            <div className="bar-track">
              <div className={`bar-fill ${cls}`} style={{ width: `${val * 100}%` }} />
            </div>
            <span className="mono">{num2(val)}</span>
          </div>
        );
      })}
    </div>
  );
}

function SlotChart({ perSlot }: { perSlot: number[] }) {
  if (perSlot.length === 0) {
    return <p className="sub">No per-slot data reported.</p>;
  }
  const max = Math.max(...perSlot, FAIR_SHARE);
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        alignItems: "flex-end",
        gap: 2,
        height: 90,
        borderLeft: "1px solid var(--border)",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: `${(FAIR_SHARE / max) * 100}%`,
          borderTop: "1px dashed var(--faint)",
        }}
      />
      {perSlot.map((v, i) => (
        <div
          key={i}
          title={`slot ${i + 1}: ${pct(v)}`}
          style={{
            flex: 1,
            background: i < 3 ? "var(--teal)" : "var(--blue)",
            opacity: i < 3 ? 1 : 0.55,
            height: `${(v / max) * 100}%`,
            minHeight: 1,
          }}
        />
      ))}
    </div>
  );
}

/* tiny inline share bar used inside table cells */
function Barish({ value }: { value: number }) {
  return (
    <span style={{ display: "inline-flex", width: 60, verticalAlign: "middle", marginRight: 6 }}>
      <span className="bar-track" style={{ flex: 1 }}>
        <span
          className="bar-fill rose"
          style={{ display: "block", width: `${Math.min(100, value * 400)}%`, height: "100%" }}
        />
      </span>
    </span>
  );
}
