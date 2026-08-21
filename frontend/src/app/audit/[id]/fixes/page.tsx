"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  buildMirror,
  createAudit,
  generateRemediations,
  listRemediations,
  reviewRemediation,
  type RemediationListResponse,
  type RemediationRow,
} from "@/lib/api";
import { rememberRerun } from "@/lib/runs";
import { ErrorBox, PanelSkeleton } from "@/components/Bits";

export default function FixesPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const router = useRouter();

  const [data, setData] = useState<RemediationListResponse | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [actionErr, setActionErr] = useState<{ code: string; message: string } | null>(null);
  const [generating, setGenerating] = useState(false);
  const [building, setBuilding] = useState(false);
  const [acknowledgedReview, setAcknowledgedReview] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await listRemediations(runId);
      setData(res);
      setError(null);
      // pre-expand the first pending product so reviewers see a diff immediately
      if (res.remediations.length > 0) {
        setExpanded(new Set([res.remediations[0].id]));
      }
    } catch (err) {
      if (err instanceof ApiError) setError({ code: err.code, message: err.message });
      else setError({ code: "E-UNK", message: "Failed to load remediation plan." });
    }
  }, [runId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onGenerate() {
    setGenerating(true);
    try {
      await generateRemediations(runId);
      await load();
    } catch (err) {
      if (err instanceof ApiError) setActionErr({ code: err.code, message: err.message });
    } finally {
      setGenerating(false);
    }
  }

  async function onReview(row: RemediationRow, status: "approved" | "rejected") {
    setActionErr(null);
    try {
      await reviewRemediation(row.id, status);
      setData((prev) =>
        prev
          ? {
              ...prev,
              counts: {
                ...prev.counts,
                [status]: prev.counts[status] + 1,
                pending: prev.counts.pending - 1,
              },
              remediations: prev.remediations.map((r) =>
                r.id === row.id
                  ? { ...r, status, reviewed_by: "merchant" }
                  : r,
              ),
            }
          : prev,
      );
    } catch (err) {
      if (err instanceof ApiError) setActionErr({ code: err.code, message: err.message });
    }
  }

  async function onMirrorAndRerun() {
    if (!data) return;
    setActionErr(null);
    setBuilding(true);
    try {
      const mirror = await buildMirror(runId); // E401 here if anything still pending
      const audit = await createAudit({
        catalog_source: "mirror",
        catalog_id: mirror.mirror_catalog_id,
        parent_run_id: runId,
      });
      rememberRerun(runId, audit.audit_id);
      router.push(`/audit/${audit.audit_id}`);
    } catch (err) {
      if (err instanceof ApiError) setActionErr({ code: err.code, message: err.message });
      else setActionErr({ code: "E-UNK", message: "Mirror/re-run failed." });
      setBuilding(false);
    }
  }

  if (error) {
    return (
      <ErrorBox code={error.code} message={error.message}>
        <Link href={`/audit/${runId}/results`}>← Back to results</Link>
      </ErrorBox>
    );
  }

  if (!data) return <PanelSkeleton lines={6} />;

  const total = data.remediations.length;
  const reviewed = data.counts.approved + data.counts.rejected;
  const allReviewed = total > 0 && reviewed === total;

  if (total === 0 && !generating) {
    return (
      <div className="panel">
        <h2>Remediation plan</h2>
        <p className="sub">
          No fixes proposed yet for this run. The generator flags starved-tier and
          low-legibility products and drafts title / description / structured-data rewrites —
          nothing is applied without your approval.
        </p>
        <button className="btn primary" onClick={onGenerate} disabled={generating}>
          Generate remediation plan
        </button>
        {actionErr ? <ErrorBox code={actionErr.code} message={actionErr.message} /> : null}
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>
          Remediation plan — {total} product{total === 1 ? "" : "s"},{" "}
          {data.remediations.reduce((n, r) => n + r.fixes.length, 0)} fixes
        </h1>
        <span className={`chip ${allReviewed ? "green" : "amber"}`}>
          {allReviewed ? "ready to mirror" : "Pending review"}
        </span>
      </div>

      <p className="sub">
        ⓘ LLM proposed · human approves · deterministic layer commits. Nothing touches your
        live catalog — approved edits are written to a mirrored copy that the verification
        re-run audits.
      </p>

      {actionErr ? (
        <ErrorBox code={actionErr.code} message={actionErr.message} />
      ) : null}

      {generating ? <PanelSkeleton lines={4} /> : null}

      {data.remediations.map((row) => {
        const open = expanded.has(row.id);
        return (
          <div key={row.id} className="fix-product">
            <div
              className="fix-head"
              onClick={() =>
                setExpanded((prev) => {
                  const next = new Set(prev);
                  if (next.has(row.id)) next.delete(row.id);
                  else next.add(row.id);
                  return next;
                })
              }
            >
              <span>{open ? "▾" : "▸"}</span>
              <span className="mono">{row.sku ?? row.product_id.slice(0, 8)}</span>
              <span>{row.title ?? "(untitled)"}</span>
              <span style={{ marginLeft: "auto" }}>
                <StatusChip status={row.status} />
              </span>
            </div>
            {open ? (
              <div className="fix-body">
                {row.fixes.map((fix, i) => (
                  <div key={`${row.id}-${i}`}>
                    <div className="diff-row">
                      <div className="diff-field">{fix.field}</div>
                      <div className="diff-before">{fix.before || "(absent)"}</div>
                      <div className="diff-after">{fix.after}</div>
                    </div>
                    <div className="rationale" style={{ marginTop: 2 }}>
                      ⓘ {fix.rationale}
                    </div>
                  </div>
                ))}
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  {row.status === "pending" ? (
                    <>
                      <button className="btn small primary" onClick={() => onReview(row, "approved")}>
                        Approve
                      </button>
                      <button className="btn small danger" onClick={() => onReview(row, "rejected")}>
                        Reject
                      </button>
                      <label style={{ alignSelf: "center", fontSize: 12.5, color: "var(--muted)", display: "flex", gap: 6 }}>
                        <input
                          type="checkbox"
                          checked={acknowledgedReview}
                          onChange={(e) => setAcknowledgedReview(e.target.checked)}
                        />
                        I have reviewed the proposed rewrites
                      </label>
                    </>
                  ) : (
                    <span style={{ fontSize: 12.5, color: "var(--muted)" }}>
                      reviewed by {row.reviewed_by ?? "merchant"}
                      {row.applied_at ? ` · applied ${new Date(row.applied_at).toLocaleString()}` : ""}
                    </span>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        );
      })}

      {/* sticky review summary */}
      <div className="sticky-review">
        <strong>
          {reviewed} of {total} reviewed
        </strong>
        <span style={{ color: "var(--faint)", fontSize: 12.5 }}>
          mirror is built only from approved rows
        </span>
        <span style={{ marginLeft: "auto" }}>
          <button
            className="btn primary"
            disabled={!allReviewed || building || !acknowledgedReview}
            title={
              !acknowledgedReview
                ? "Tick “I have reviewed the proposed rewrites” first"
                : !allReviewed
                  ? "Approve or reject every row first (E401)"
                  : undefined
            }
            onClick={onMirrorAndRerun}
          >
            {building ? "Building mirror…" : "Build mirror & re-run →"}
          </button>
        </span>
      </div>
    </div>
  );
}

function StatusChip({ status }: { status: RemediationRow["status"] }) {
  if (status === "approved") return <span className="chip green">approved</span>;
  if (status === "rejected") return <span className="chip rose">rejected</span>;
  return <span className="chip amber">pending</span>;
}
