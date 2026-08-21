"use client";

import type { CSSProperties } from "react";

const CI_TOOLTIP = "95% confidence interval, persona-cluster bootstrap, B = 2,000";

/**
 * CI display convention (APPFLOW §1.2): `value [lo – hi]`, hover → bootstrap tooltip.
 * Every headline number renders through this or a Dial — no naked numbers.
 */
export function Ci(props: {
  v: number;
  lo: number;
  hi: number;
  fmt?: (n: number) => string;
  style?: CSSProperties;
}) {
  const f = props.fmt ?? ((n: number) => String(n));
  return (
    <span className="ci" title={CI_TOOLTIP} style={props.style}>
      {f(props.v)} <span className="ci-range">[{f(props.lo)} – {f(props.hi)}]</span>
    </span>
  );
}

/** Compact inline form for table cells. */
export function CiSmall(props: { v: number; lo: number; hi: number; fmt?: (n: number) => string }) {
  const f = props.fmt ?? ((n: number) => String(n));
  return (
    <span className="ci" title={CI_TOOLTIP}>
      <span className="ci-range">
        [{f(props.lo)} – {f(props.hi)}]
      </span>
    </span>
  );
}
