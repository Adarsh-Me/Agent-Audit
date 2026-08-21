"use client";

/**
 * Score dial — pure SVG ring using stroke-dasharray. No chart libraries.
 */

export function Dial(props: {
  /** normalized 0–1 */
  frac: number;
  size?: number;
  color?: string;
  trackColor?: string;
  children?: React.ReactNode;
}) {
  const size = props.size ?? 150;
  const stroke = 11;
  const r = (size - stroke) / 2 - 4;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, props.frac));
  return (
    <div className="dial-wrap">
      <svg width={size} height={size} role="img" aria-label="score dial">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={props.trackColor ?? "var(--panel-2)"}
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={props.color ?? "var(--teal)"}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${clamped * c} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div
        style={{
          marginTop: -(size / 2 + 18),
          marginBottom: size / 2 - 22,
          textAlign: "center",
        }}
      >
        {props.children}
      </div>
    </div>
  );
}

/** Score dial with centered number + label underneath the ring. */
export function ScoreDial(props: {
  score: number;
  lo?: number;
  hi?: number;
  size?: number;
  label?: string;
}) {
  const frac = Math.max(0, Math.min(1, props.score / 100));
  const color = props.score >= 80 ? "var(--green)" : props.score >= 60 ? "var(--teal)" : "var(--amber)";
  return (
    <Dial frac={frac} size={props.size ?? 150} color={color}>
      <div style={{ paddingTop: (props.size ?? 150) * 0.18 }}>
        <div className="dial-num">{props.score.toFixed(1)}</div>
        {props.lo !== undefined && props.hi !== undefined ? (
          <div className="ci-range" style={{ fontSize: 12 }} title="95% confidence interval, persona-cluster bootstrap, B = 2,000">
            [{props.lo.toFixed(1)} – {props.hi.toFixed(1)}]
          </div>
        ) : null}
      </div>
    </Dial>
  );
}
