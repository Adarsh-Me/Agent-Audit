"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getLastRun } from "@/lib/runs";

export function TopBar() {
  const [runId, setRunId] = useState<string | null>(null);

  useEffect(() => {
    setRunId(getLastRun());
    const onStorage = () => setRunId(getLastRun());
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link href="/" className="brand">
          <span className="diamond">◆</span> AgentAudit
        </Link>
        <span className="run-chip">Track 01 · Agentic Commerce</span>
        <nav className="topnav">
          {runId ? (
            <>
              <Link href={`/audit/${runId}/results`}>Results</Link>
              <Link href={`/audit/${runId}/revenue`}>Revenue</Link>
              <Link href={`/audit/${runId}/fixes`}>Fixes</Link>
              <span className="run-chip" title="last audited run">
                run …{runId.slice(0, 8)}
              </span>
            </>
          ) : null}
        </nav>
      </div>
    </header>
  );
}

export function FooterBar() {
  return (
    <footer className="footerbar">
      <div className="footerbar-inner">
        Metrics: persona-cluster bootstrap 95% CI (B = 2,000; Wilson for F_task) · Runs
        recorded server-side · Demo numbers render only from API payloads — nothing is
        computed or invented client-side.
      </div>
    </footer>
  );
}
