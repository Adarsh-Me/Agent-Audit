"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  getAudit,
  streamUrl,
  type AuditStatusResponse,
  type SseTrialEvent,
} from "@/lib/api";
import { usd } from "@/lib/format";
import { rememberRun } from "@/lib/runs";
import { ErrorBox } from "@/components/Bits";

const PARTIAL_BANNER =
  "Partial run — cost cap hit. Numbers below are real but incomplete.";
const MAX_SSE_FAILURES = 3;
const POLL_MS = 3000;

export default function ProgressPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const router = useRouter();

  const [status, setStatus] = useState<AuditStatusResponse["status"] | "loading">("loading");
  const [done, setDone] = useState(0);
  const [total, setTotal] = useState(640);
  const [costUsd, setCostUsd] = useState(0);
  const [etaS, setEtaS] = useState(0);
  const [ticker, setTicker] = useState<SseTrialEvent[]>([]);
  const [transport, setTransport] = useState<"sse" | "polling">("sse");
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const startedAtRef = useRef<number>(Date.now());
  const navigatedRef = useRef(false);

  const finishToResults = useCallback(
    (finalStatus: AuditStatusResponse["status"]) => {
      if (navigatedRef.current) return;
      setStatus(finalStatus);
      if (finalStatus === "done" || finalStatus === "partial") {
        navigatedRef.current = true;
        // APPFLOW F2: auto-redirect after 1.5 s
        window.setTimeout(() => router.push(`/audit/${runId}/results`), 1500);
      }
    },
    [router, runId],
  );

  // Initial status load
  useEffect(() => {
    let alive = true;
    getAudit(runId)
      .then((s) => {
        if (!alive) return;
        rememberRun(s.run_id);
        setDone(s.trials_done);
        setTotal(s.trials_total ?? 640);
        setCostUsd(s.cost_usd);
        setEtaS(s.eta_s);
        if (s.status === "queued" || s.status === "running") {
          setStatus(s.status);
          startedAtRef.current = Date.now();
        } else {
          finishToResults(s.status);
        }
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setStatus("failed");
        if (err instanceof ApiError) setError({ code: err.code, message: err.message });
        else setError({ code: "E-UNK", message: "Failed to load run." });
      });
    return () => {
      alive = false;
    };
  }, [runId, finishToResults]);

  // SSE with polling fallback
  useEffect(() => {
    if (status !== "queued" && status !== "running") return;
    let es: EventSource | null = null;
    let pollTimer: number | null = null;
    let failures = 0;
    let closed = false;

    const startPolling = () => {
      if (closed || pollTimer !== null) return;
      setTransport("polling");
      const tick = async () => {
        try {
          const s = await getAudit(runId);
          setDone(s.trials_done);
          setTotal(s.trials_total ?? 640);
          setCostUsd(s.cost_usd);
          setEtaS(s.eta_s);
          if (s.status !== "running" && s.status !== "queued") {
            closed = true;
            finishToResults(s.status);
            return;
          }
        } catch {
          /* keep polling */
        }
        pollTimer = window.setTimeout(tick, POLL_MS);
      };
      void tick();
    };

    try {
      es = new EventSource(streamUrl(runId));

      es.addEventListener("progress", (ev) => {
        try {
          const d = JSON.parse((ev as MessageEvent).data) as { done: number; total: number; cost_usd: number };
          setDone(d.done);
          setTotal(d.total);
          setCostUsd(d.cost_usd);
          setEtaS(Math.max(0, d.total - d.done) * 0.35);
        } catch {
          /* malformed event ignored */
        }
      });

      es.addEventListener("trial", (ev) => {
        try {
          const t = JSON.parse((ev as MessageEvent).data) as SseTrialEvent;
          setTicker((prev) => [...prev.slice(-5), t]);
        } catch {
          /* malformed event ignored */
        }
      });

      es.addEventListener("e203_cost_cap", () => {
        // banner shows via status transition to partial on complete
      });

      es.addEventListener("complete", (ev) => {
        try {
          const d = JSON.parse((ev as MessageEvent).data) as { status: AuditStatusResponse["status"] };
          es?.close();
          closed = true;
          finishToResults(d.status);
        } catch {
          /* fall through to polling */
        }
      });

      // heartbeat comments arrive without a named event — EventSource keeps the
      // connection alive automatically; nothing to handle explicitly.
      es.onerror = () => {
        failures += 1;
        if (failures >= MAX_SSE_FAILURES && !closed) {
          es?.close();
          startPolling();
        }
      };
    } catch {
      startPolling();
    }

    return () => {
      closed = true;
      es?.close();
      if (pollTimer !== null) window.clearTimeout(pollTimer);
    };
  }, [runId, status, finishToResults]);

  // elapsed timer
  useEffect(() => {
    if (status !== "running" && status !== "queued") return;
    const t = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000)),
      1000,
    );
    return () => window.clearInterval(t);
  }, [status]);

  if (error) {
    return (
      <div>
        <ErrorBox code={error.code} message={error.message}>
          <Link href="/">← Back to setup</Link>
        </ErrorBox>
      </div>
    );
  }

  const pctDone = total > 0 ? Math.min(1, done / total) : 0;

  return (
    <div>
      {status === "partial" ? <div className="banner amber">{PARTIAL_BANNER}</div> : null}
      {status === "failed" ? (
        <div className="banner red">
          Run failed — provider hard-fail. No charge beyond completed trials.{" "}
          <Link href="/">Start a new audit</Link> to retry.
        </div>
      ) : null}

      <div className="panel">
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span className={`chip ${status === "failed" ? "rose" : status === "partial" ? "amber" : "teal"}`}>
            ● {status === "loading" ? "Loading…" : status.charAt(0).toUpperCase() + status.slice(1)}
          </span>
          <span className="mono run-chip" title="run id (click to copy)" style={{ cursor: "pointer" }}
            onClick={() => navigator.clipboard?.writeText(runId).catch(() => {})}>
            {runId}
          </span>
          {(status === "running" || status === "queued") ? (
            <span style={{ color: "var(--muted)", fontSize: 13 }}>
              elapsed {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
            </span>
          ) : null}
          <span style={{ marginLeft: "auto", fontSize: 12 }}>
            {transport === "polling" ? (
              <span className="chip amber">reconnecting… (polling every 3s)</span>
            ) : (
              <span className="chip gray">live stream</span>
            )}
          </span>
        </div>

        <div style={{ margin: "16px 0 6px", display: "flex", justifyContent: "space-between", fontSize: 13 }}>
          <span className="mono">
            {done} / {total} trials
          </span>
          <span className="mono">cost {usd(costUsd)}</span>
        </div>
        <div className="progressbar">
          <div style={{ width: `${pctDone * 100}%` }} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, color: "var(--faint)", fontSize: 12 }}>
          <span>{Math.round(pctDone * 100)}% complete</span>
          {etaS > 0 ? <span className="mono">ETA ~{Math.round(etaS)}s</span> : null}
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Live trial ticker</h2>
          <p className="sub">Last 6 trials as they land. Amber rows chose &ldquo;nothing fits&rdquo;.</p>
          <div className="ticker">
            {ticker.length === 0 ? (
              <span className="dim">waiting for trials…</span>
            ) : (
              ticker.map((t, i) => (
                <div key={`${i}-${t.ts ?? i}`} className={t.choice === null ? "nullrow" : ""}>
                  {t.model.padEnd(12)} {t.persona_id.padEnd(4)} {t.condition.padEnd(7)} →{" "}
                  {t.choice === null ? "→ null (nothing fits)" : t.choice} {String(t.latency_ms)}ms
                </div>
              ))
            )}
          </div>
        </div>

        <details className="panel">
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>What&rsquo;s happening</summary>
          <p className="sub" style={{ marginTop: 10, marginBottom: 6 }}>
            <strong>C1 baseline</strong> — catalog presented in its normal order.
          </p>
          <p className="sub" style={{ marginBottom: 6 }}>
            <strong>C2 shuffled</strong> — randomized listing order isolates position bias.
          </p>
          <p className="sub" style={{ marginBottom: 6 }}>
            <strong>C3 rewritten copy</strong> — reframed descriptions isolate framing bias.
          </p>
          <p className="sub" style={{ marginBottom: 0 }}>
            1 in 3 trials may return &ldquo;nothing fits&rdquo; — that&rsquo;s the coverage metric.
          </p>
        </details>
      </div>

      {navigatedRef.current && (status === "done" || status === "partial") ? (
        <p style={{ textAlign: "center" }}>
          Redirecting… <Link href={`/audit/${runId}/results`}>View results now →</Link>
        </p>
      ) : null}
    </div>
  );
}
