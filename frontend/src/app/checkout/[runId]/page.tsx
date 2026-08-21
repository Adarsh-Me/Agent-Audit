"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  createPaymentLink,
  getCatalog,
  getPaymentStatus,
  type CatalogProduct,
  type PaymentLinkResponse,
} from "@/lib/api";
import { inr } from "@/lib/format";
import { ErrorBox } from "@/components/Bits";

interface ConsoleLine {
  id: number;
  text: string;
  cls?: string;
}

type PayPhase = "idle" | "running" | "link_ready" | "captured" | "error";

const TRUST_NOTE =
  "The agent never saw a Razorpay key. The backend created this link; the agent only received a URL.";
const CAPTURED_BANNER = "Payment captured — agent-to-ledger loop closed.";

export default function CheckoutPage() {
  const params = useParams<{ runId: string }>();
  const runId = params.runId;

  const [lines, setLines] = useState<ConsoleLine[]>([]);
  const [phase, setPhase] = useState<PayPhase>("idle");
  const [product, setProduct] = useState<CatalogProduct | null>(null);
  const [link, setLink] = useState<PaymentLinkResponse | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [waitingSince, setWaitingSince] = useState<number | null>(null);

  const lineIdRef = useRef(0);
  const runningRef = useRef(false);
  const pollRef = useRef<number | null>(null);

  const addLine = useCallback((text: string, cls?: string) => {
    lineIdRef.current += 1;
    setLines((prev) => [...prev, { id: lineIdRef.current, text, cls }]);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // webhook-badge poller: GET /api/payments/{run_id}/status every 1 s until captured
  const startPolling = useCallback(() => {
    if (pollRef.current !== null) return;
    setWaitingSince(Date.now());
    pollRef.current = window.setInterval(async () => {
      try {
        const st = await getPaymentStatus(runId);
        if (st.captured) {
          stopPolling();
          setPhase("captured");
        } else if (st.payments[0]?.status === "failed") {
          stopPolling();
          setError({ code: "E-PAY", message: "Payment failed — retry the test payment." });
        }
      } catch {
        /* keep polling until timeout */
      }
    }, 1000);
  }, [runId, stopPolling]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  async function ensureLink(sku: string): Promise<PaymentLinkResponse> {
    if (link) return link;
    addLine(`step 4  tool: create_payment_link → POST /api/payments/link`, "tool");
    const res = await createPaymentLink(runId, sku);
    addLine(`        → ${res.short_url || "(no url returned)"}  ✓`, "ok");
    setLink(res);
    setPhase("link_ready");
    startPolling();
    return res;
  }

  async function startAgent() {
    if (runningRef.current) return;
    runningRef.current = true;
    setError(null);
    setLines([]);
    setProduct(null);
    setLink(null);
    setPhase("running");

    try {
      // step 1 — real catalog read
      addLine("step 1  tool: list_products", "tool");
      await sleep(500);
      const catalog = await getCatalog();
      addLine(`        → ${catalog.count} products received`, "ok");

      // step 2 — scripted Deal-Hunter reasoning
      await sleep(600);
      addLine(
        'step 2  reasoning (P07 · Deal Hunter): "Best value-for-money item…"',
        "reason",
      );
      addLine("        comparing price vs. described specs across catalog…", "reason");

      // deterministic choice rule: cheapest rich-tier listing with a structured price,
      // else cheapest overall — logged honestly as a scripted stand-in for the live agent
      const candidates = catalog.products.filter(
        (p) => p.structured_data && Object.keys(p.structured_data).length > 0,
      );
      const pool = candidates.length > 0 ? candidates : catalog.products;
      const rich = pool.filter((p) => p.tier === "rich");
      const chosen = [...(rich.length > 0 ? rich : pool)].sort(
        (a, b) => a.price_inr - b.price_inr,
      )[0];
      if (!chosen) throw new ApiError("E-CAT", "Catalog has no products to buy.", 0);

      await sleep(600);
      addLine(`step 3  tool: get_product → id: "${chosen.id}"`, "tool");
      addLine(`        ${chosen.title} — ${inr(chosen.price_inr)} (${chosen.tier})`);
      setProduct(chosen);

      await sleep(500);
      await ensureLink(chosen.id);

      await sleep(400);
      addLine("step 5  hand to human → open the payment page and pay (test mode)");
      runningRef.current = false;
    } catch (err) {
      runningRef.current = false;
      setPhase("error");
      if (err instanceof ApiError) {
        setError({ code: err.code, message: err.message });
        addLine(`        error ${err.code}: ${err.message}`, "");
      } else {
        setError({ code: "E-UNK", message: "Agent run failed unexpectedly." });
      }
    }
  }

  function onPay() {
    if (!link || !link.short_url) {
      setError({ code: "E502", message: "No payment link available — restart the agent." });
      return;
    }
    window.open(link.short_url, "_blank", "noopener,noreferrer");
  }

  const waitingLong = waitingSince !== null && Date.now() - waitingSince > 60_000;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 14 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>Agent checkout proof</h1>
        <span className="sub" style={{ margin: 0 }}>
          run <span className="mono">{runId.slice(0, 8)}</span>
        </span>
      </div>

      <div className="grid-2">
        {/* ---------- left: agent console ---------- */}
        <div className="panel">
          <h2>Agent console</h2>
          <p className="sub">
            Scripted P07 &ldquo;Deal Hunter&rdquo; walkthrough: choose a product, create a
            payment link, hand off to a human.
          </p>
          <div className="console">
            {lines.length === 0 ? (
              <span style={{ color: "var(--faint)" }}>idle — press “Start agent”</span>
            ) : (
              lines.map((l) => (
                <div key={l.id} className={`step ${l.cls ?? ""}`}>
                  {l.text}
                </div>
              ))
            )}
          </div>
          <div style={{ marginTop: 12, display: "flex", gap: 10 }}>
            {phase === "idle" || phase === "error" ? (
              <button className="btn primary" onClick={startAgent}>
                {phase === "error" ? "Restart agent" : "Start agent →"}
              </button>
            ) : null}
            {phase === "running" ? <button className="btn" disabled>agent running…</button> : null}
          </div>

          <div className="honesty-note">{TRUST_NOTE}</div>
        </div>

        {/* ---------- right: payment card ---------- */}
        <div className="panel">
          <h2>Payment</h2>
          {!product && phase !== "captured" ? (
            <p className="sub">The agent&rsquo;s chosen product appears here once it picks one.</p>
          ) : null}

          {product ? (
            <>
              <div className={`stat-card ${phase === "link_ready" ? "pulse" : ""}`}>
                <div className="k">Chosen by agent</div>
                <div style={{ fontSize: 16, fontWeight: 650 }}>{product.title}</div>
                <div className="mono" style={{ color: "var(--muted)", fontSize: 12 }}>
                  {product.id} · tier: {product.tier}
                </div>
                <div style={{ fontSize: 22, fontWeight: 700, marginTop: 6 }}>
                  {inr(product.price_inr)}
                </div>
              </div>

              <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 10 }}>
                <button
                  className="btn primary"
                  onClick={onPay}
                  disabled={!link}
                  title={link ? undefined : "payment link not created yet"}
                >
                  Pay {inr(product.price_inr)} (test mode)
                </button>
                {phase === "running" ? <span className="chip gray">creating link…</span> : null}
                {phase === "link_ready" ? (
                  <span className="chip blue">awaiting payment — complete the test payment</span>
                ) : null}
              </div>

              {waitingLong && phase !== "captured" ? (
                <div className="banner amber" style={{ marginTop: 12 }}>
                  Webhook is late — verifying via API poll…
                </div>
              ) : null}

              {phase === "captured" ? (
                <div className="banner teal" style={{ marginTop: 12 }}>
                  ✓ {CAPTURED_BANNER}
                </div>
              ) : null}

              <p style={{ fontSize: 11.5, color: "var(--faint)", marginTop: 10 }}>
                Target: capture confirmed within ~5 s of payment. Test-mode Razorpay link — no
                real money moves.
              </p>
            </>
          ) : null}

          {phase === "captured" && !product ? (
            <div className="banner teal">✓ {CAPTURED_BANNER}</div>
          ) : null}

          {error ? (
            <ErrorBox code={error.code} message={error.message}>
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <button className="btn small" onClick={startAgent}>
                  Retry link
                </button>
                <Link href={`/audit/${runId}/results`} className="btn small" style={{ alignSelf: "center" }}>
                  Back to results
                </Link>
              </div>
            </ErrorBox>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
