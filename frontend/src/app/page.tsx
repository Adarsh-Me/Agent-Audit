"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import {
  ApiError,
  createAudit,
  uploadCatalog,
  type UploadInvalidRow,
  type UploadResponse,
} from "@/lib/api";
import { rememberRun } from "@/lib/runs";
import { ErrorBox } from "@/components/Bits";

type Phase = "idle" | "uploading" | "uploaded" | "starting";

export default function LandingPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement | null>(null);

  function startDemo() {
    setPhase("starting");
    setError(null);
    createAudit({ catalog_source: "demo" })
      .then((res) => {
        rememberRun(res.audit_id);
        router.push(`/audit/${res.audit_id}`);
      })
      .catch((err: unknown) => {
        setPhase("idle");
        if (err instanceof ApiError && err.code === "E602") {
          setError({ code: err.code, message: "Too many requests — retry in 60s" });
        } else if (err instanceof ApiError) {
          setError({ code: err.code, message: err.message });
        } else {
          setError({ code: "E-UNK", message: "Something went wrong starting the audit." });
        }
      });
  }

  function sendFile(file: File) {
    const name = file.name.toLowerCase();
    if (!name.endsWith(".json") && !name.endsWith(".csv")) {
      setError({ code: "E102", message: "Only .json or .csv catalogs are accepted." });
      return;
    }
    setPhase("uploading");
    setError(null);
    uploadCatalog(file)
      .then((res) => {
        setUpload(res);
        setPhase("uploaded");
      })
      .catch((err: unknown) => {
        setPhase("idle");
        if (err instanceof ApiError) setError({ code: err.code, message: err.message });
        else setError({ code: "E-UNK", message: "Upload failed." });
      });
  }

  function startFromUpload() {
    if (!upload) return;
    setPhase("starting");
    createAudit({ catalog_source: "upload", catalog_id: upload.catalog_id })
      .then((res) => {
        rememberRun(res.audit_id);
        router.push(`/audit/${res.audit_id}`);
      })
      .catch((err: unknown) => {
        setPhase("idle");
        if (err instanceof ApiError) setError({ code: err.code, message: err.message });
      });
  }

  return (
    <div>
      <section className="hero">
        <h1>Can AI shopping agents actually buy from you?</h1>
        <p>
          AgentAudit runs 640 controlled agent trials across your catalog and measures
          whether AI shoppers can see your products, choose them fairly, and carry a
          purchase through to payment.
        </p>
        <p style={{ fontSize: 13.5 }}>
          Merchants have SEO for Google&rsquo;s crawler. This is the equivalent check for
          the agents now choosing products on your customers&rsquo; behalf.
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 18 }}>
          <button
            className="btn primary"
            onClick={startDemo}
            disabled={phase === "starting"}
          >
            {phase === "starting" ? "Queuing…" : "Run the demo audit →"}
          </button>
          <span
            style={{
              alignSelf: "center",
              color: "var(--faint)",
              fontSize: 12,
              fontFamily: "var(--mono)",
            }}
          >
            ~2–15 min · est. $12 · hard cap $30/run
          </span>
        </div>
      </section>

      {error ? (
        <ErrorBox code={error.code} message={error.message}>
          <div>
            <button className="btn small" style={{ marginTop: 8 }} onClick={startDemo}>
              Try again
            </button>
          </div>
        </ErrorBox>
      ) : null}

      <div className="grid-2">
        {/* Card A — demo */}
        <div className="source-card active">
          <h3 style={{ margin: "0 0 6px" }}>
            Demo Store{" "}
            <span className="chip teal" style={{ marginLeft: 6 }}>
              RECOMMENDED
            </span>
          </h3>
          <p className="sub" style={{ marginBottom: 0 }}>
            40 products · 4 categories · controlled data-quality tiers (rich / medium /
            starved). The fastest way to see every screen with real measured numbers.
          </p>
        </div>

        {/* Card B — upload (F2 inline state on this page) */}
        <div className="source-card" style={{ cursor: "default" }}>
          <h3 style={{ margin: "0 0 10px" }}>Upload catalog</h3>
          {phase === "uploaded" && upload ? (
            <div>
              <p className="sub" style={{ color: "var(--pos)" }}>
                {upload.valid} of {upload.valid + upload.invalid.length} rows valid —
                continue with valid rows?
              </p>
              {upload.invalid.length > 0 ? (
                <ul style={{ margin: "0 0 10px", paddingLeft: 18, color: "var(--muted)", fontSize: 12.5 }}>
                  {upload.invalid.slice(0, 8).map((r: UploadInvalidRow) => (
                    <li key={`${r.row}-${r.code}`}>
                      Row {r.row}: {r.code} — {r.message}
                    </li>
                  ))}
                </ul>
              ) : null}
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn primary small" onClick={startFromUpload}>
                  Audit uploaded catalog →
                </button>
                <button
                  className="btn small"
                  onClick={() => {
                    setUpload(null);
                    setPhase("idle");
                  }}
                >
                  Pick another file
                </button>
              </div>
            </div>
          ) : (
            <div
              className={`dropzone ${dragOver ? "over" : ""}`}
              onClick={() => fileInput.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const f = e.dataTransfer.files?.[0];
                if (f) sendFile(f);
              }}
            >
              {phase === "uploading" ? (
                "Validating rows…"
              ) : (
                <>
                  Drag &amp; drop a <code>.json</code> or <code>.csv</code> catalog here
                  <div style={{ fontSize: 11.5, marginTop: 4 }}>
                    per-row validation errors are shown before anything runs
                  </div>
                </>
              )}
            </div>
          )}
          <input
            ref={fileInput}
            type="file"
            accept=".json,.csv"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) sendFile(f);
              e.target.value = "";
            }}
          />
        </div>
      </div>

      {/* honesty strip */}
      <div className="panel" style={{ marginTop: 20 }}>
        <h3>What this tool does not do</h3>
        <p className="sub" style={{ marginBottom: 0 }}>
          No scraping of live storefronts and no access to your production site — audits
          run against a catalog snapshot you provide (or the demo store). Numbers come
          only from recorded trials in this run; nothing is estimated client-side. Every
          headline figure carries its confidence interval.
        </p>
      </div>
    </div>
  );
}
