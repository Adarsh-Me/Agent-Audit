"use client";

/** Small shared UI bits: skeletons, error box, tier/source chips, bars. */

export function Skeleton({ h = 14, w }: { h?: number; w?: string }) {
  return <div className="skel" style={{ height: h, width: w }} />;
}

export function PanelSkeleton({ lines = 4 }: { lines?: number }) {
  return (
    <div className="panel">
      <Skeleton h={16} w="40%" />
      <div style={{ display: "grid", gap: 8, marginTop: 14 }}>
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} w={`${90 - i * 12}%`} />
        ))}
      </div>
    </div>
  );
}

export function ErrorBox(props: {
  code?: string;
  message: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="errorbox">
      <span className="code">{props.code ?? "ERR"}</span>
      {props.message}
      {props.children}
    </div>
  );
}

export function TierChip({ tier }: { tier: string }) {
  return <span className={`chip tier-${tier}`}>{tier}</span>;
}

/** Revenue figure tag chips (APPFLOW §1.2): [measured] teal · [assumed] amber · [input] gray. */
export function SourceChip({ kind }: { kind: "measured" | "assumed" | "input" | string }) {
  const cls = kind === "measured" ? "teal" : kind === "assumed" ? "amber" : "gray";
  return <span className={`chip ${cls}`}>[{kind}]</span>;
}

export function Bar(props: {
  frac: number;
  color?: "teal" | "green" | "amber" | "rose" | "blue";
}) {
  const clamped = Math.max(0, Math.min(1, props.frac));
  return (
    <div className="bar-track">
      <div
        className={`bar-fill ${props.color ?? "teal"}`}
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  );
}

export function StatCard(props: { k: string; v: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="stat-card">
      <div className="k">{props.k}</div>
      <div className="v">{props.v}</div>
      {props.sub ? (
        <div style={{ color: "var(--muted)", fontSize: 11.5 }}>{props.sub}</div>
      ) : null}
    </div>
  );
}
