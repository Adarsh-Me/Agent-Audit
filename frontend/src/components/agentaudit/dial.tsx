'use client'

import type { ReactNode } from 'react'

/**
 * Score dial — pure SVG ring using stroke-dasharray. No chart libraries.
 * Ring color follows the AgentReady bands: ≥80 green, ≥60 accent, else muted.
 */
export function Dial({
  frac,
  size = 150,
  color = 'var(--primary)',
  children
}: {
  /** normalized 0–1 */
  frac: number;
  size?: number;
  color?: string;
  children?: ReactNode
}) {
  const stroke = 11
  const r = (size - stroke) / 2 - 4
  const c = 2 * Math.PI * r
  const clamped = Math.max(0, Math.min(1, frac))

  return (
    <div className='relative inline-block' style={{ width: size, height: size }}>
      <svg width={size} height={size} role='img' aria-label='score dial'>
        <circle cx={size / 2} cy={size / 2} r={r} fill='none' stroke='var(--muted)' strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill='none'
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap='round'
          strokeDasharray={`${clamped * c} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className='absolute inset-0 flex flex-col items-center justify-center text-center'>
        {children}
      </div>
    </div>
  )
}

/** Score dial with centered number + optional CI underneath. */
export function ScoreDial({
  score,
  lo,
  hi,
  size = 150
}: {
  score: number;
  lo?: number;
  hi?: number;
  size?: number
}) {
  const frac = Math.max(0, Math.min(1, score / 100))
  const color =
    score >= 80 ? 'var(--chart-2)' : score >= 60 ? 'var(--primary)' : 'var(--muted-foreground)'

  // CI sits below the ring, not inside it — inside collides with the number
  // once the dial drops to ~100px (results headline strip).
  return (
    <div className='inline-flex flex-col items-center'>
      <Dial frac={frac} size={size} color={color}>
        <div className='font-pixel text-2xl' style={{ fontSize: size / 5.5 }}>
          {score.toFixed(1)}
        </div>
      </Dial>
      {lo !== undefined && hi !== undefined ? (
        <div
          className='text-muted-foreground mt-1.5 font-mono text-[11px]'
          title='95% confidence interval, persona-cluster bootstrap, B = 2,000'
        >
          [{lo.toFixed(1)} – {hi.toFixed(1)}]
        </div>
      ) : null}
    </div>
  )
}
