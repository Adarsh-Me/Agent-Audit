'use client'

import type { CSSProperties } from 'react'

import { cn } from '@/lib/utils'

const CI_TOOLTIP = '95% confidence interval, persona-cluster bootstrap, B = 2,000'

/**
 * CI display convention (APPFLOW §1.2): `value [lo – hi]`, hover → bootstrap tooltip.
 * Every headline number renders through this or a ScoreDial — no naked numbers.
 */
export function Ci({
  v,
  lo,
  hi,
  fmt,
  className,
  style
}: {
  v: number;
  lo: number;
  hi: number;
  fmt?: (n: number) => string;
  className?: string;
  style?: CSSProperties
}) {
  const f = fmt ?? ((n: number) => String(n))
  return (
    <span className={cn('tabular-nums', className)} title={CI_TOOLTIP} style={style}>
      {f(v)}{' '}
      <span className='text-muted-foreground font-mono text-[0.85em]'>
        [{f(lo)} – {f(hi)}]
      </span>
    </span>
  )
}

/** Compact interval-only form for table cells. */
export function CiSmall({
  lo,
  hi,
  fmt
}: {
  lo: number;
  hi: number;
  fmt?: (n: number) => string
}) {
  const f = fmt ?? ((n: number) => String(n))
  return (
    <span className='text-muted-foreground font-mono text-[0.85em]' title={CI_TOOLTIP}>
      [{f(lo)} – {f(hi)}]
    </span>
  )
}
