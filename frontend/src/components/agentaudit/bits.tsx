'use client'

import type { CSSProperties, ReactNode } from 'react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

/** Value tile used across dashboards: small label, big formatted value, sub-line. */
export function StatCard({
  k,
  v,
  sub,
  className
}: {
  k: ReactNode
  v: ReactNode;
  sub?: ReactNode;
  className?: string
}) {
  return (
    <Card size='sm' className={cn('gap-0 py-4', className)}>
      <CardContent className='px-4'>
        <div className='text-muted-foreground text-xs font-medium tracking-wide uppercase'>{k}</div>
        <div className='mt-1.5 text-2xl font-semibold tabular-nums'>{v}</div>
        {sub ? <div className='text-muted-foreground mt-1 text-xs'>{sub}</div> : null}
      </CardContent>
    </Card>
  )
}

/** SCHEMA §7 error envelope rendered as an alert — code always visible. */
export function ErrorBox({
  code,
  message,
  children
}: {
  code: string;
  message: string;
  children?: ReactNode
}) {
  return (
    <Alert variant='destructive'>
      <AlertTitle className='font-mono text-sm'>
        {code} — {message}
      </AlertTitle>
      {children ? <AlertDescription>{children}</AlertDescription> : null}
    </Alert>
  )
}

export function PanelSkeleton({ lines = 4, className }: { lines?: number; className?: string }) {
  return (
    <Card className={cn('gap-2 py-5', className)}>
      <CardContent className='flex flex-col gap-3 px-5'>
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className={cn('h-4', i % 3 === 0 ? 'w-2/5' : 'w-full')} />
        ))}
      </CardContent>
    </Card>
  )
}

/**
 * Source labeling (PRD §19 claim discipline): every rupee/assumption chip names
 * where the number came from — measured / assumed / input / scenario.
 */
export type SourceKind = 'measured' | 'assumed' | 'input' | 'scenario' | 'verified'

const SOURCE_STYLES: Record<SourceKind, string> = {
  measured: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  assumed: 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400',
  input: 'border-sky-500/30 bg-sky-500/10 text-sky-600 dark:text-sky-400',
  scenario: 'border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-400',
  verified: 'border-emerald-500/40 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
}

export function SourceChip({ kind, label }: { kind: SourceKind; label?: string }) {
  return (
    <Badge variant='outline' className={cn('h-5 px-1.5 text-[11px]', SOURCE_STYLES[kind])}>
      {label ?? `[${kind}]`}
    </Badge>
  )
}

/** Catalog tier chip — legibility tier of a listing (rich / medium / starved). */
export function TierChip({ tier }: { tier: string }) {
  const map: Record<string, string> = {
    rich: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    medium: 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400',
    starved: 'border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400'
  }
  return (
    <Badge variant='outline' className={cn('h-5 px-1.5 text-[11px]', map[tier] ?? '')}>
      {tier}
    </Badge>
  )
}

/** Run status chip — queued/running/done/partial/failed. */
export function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    queued: 'border-sky-500/30 bg-sky-500/10 text-sky-600 dark:text-sky-400',
    running: 'border-sky-500/40 bg-sky-500/15 text-sky-600 dark:text-sky-300',
    done: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    partial: 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400',
    failed: 'border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400'
  }
  return (
    <Badge variant='outline' className={cn('h-5 px-1.5 text-[11px]', map[status] ?? '')}>
      {status === 'running' || status === 'queued' ? '● ' : ''}
      {status}
    </Badge>
  )
}

/** Horizontal share bar (0–1 normalized) used inside tables and cards. */
export function BarTrack({
  value,
  tone = 'primary',
  style
}: {
  /** 0–1; values above 1 are clamped */
  value: number;
  tone?: 'primary' | 'emerald' | 'rose' | 'muted';
  style?: CSSProperties
}) {
  const tones: Record<string, string> = {
    primary: 'bg-primary',
    emerald: 'bg-emerald-500',
    rose: 'bg-rose-500',
    muted: 'bg-muted-foreground/40'
  }
  return (
    <div className='bg-muted h-1.5 w-full overflow-hidden rounded-full' style={style}>
      <div
        className={cn('h-full rounded-full transition-all', tones[tone])}
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
      />
    </div>
  )
}
