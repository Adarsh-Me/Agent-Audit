'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useState } from 'react'

import { ArrowRightIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table'
import { BarTrack, ErrorBox, PanelSkeleton, SourceChip } from '@/components/agentaudit/bits'
import { Ci } from '@/components/agentaudit/ci'
import { ScoreDial } from '@/components/agentaudit/dial'
import { ApiError, getDelta, getMetrics, type DeltaResponse } from '@/lib/api'
import { inr, num1, num2, pct } from '@/lib/format'

const HONEST_FALLBACK_TITLE = 'Delta within statistical noise.'
const HONEST_FALLBACK_BODY =
  'The before/after confidence intervals overlap, so we cannot claim this remediation moved agent demand on this catalog. The persistent gap is consistent with model-side bias documented in ACES (2025) — which is itself the finding. We do not tune seeds to manufacture a bigger number.'

interface DialCis {
  original: { lo: number; hi: number }
  rerun: { lo: number; hi: number }
}

export default function DeltaPage() {
  const params = useParams<{ rerunId: string }>()
  const rerunId = params.rerunId

  const [delta, setDelta] = useState<DeltaResponse | null>(null)
  const [cis, setCis] = useState<DialCis | null>(null)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const d = await getDelta(rerunId)
        if (!alive) return
        setDelta(d)
        // delta endpoint reports point scores only; pull each run's metrics for the CIs
        try {
          const [before, after] = await Promise.all([
            getMetrics(d.original_run_id),
            getMetrics(d.rerun_run_id)
          ])
          if (!alive) return
          if ('score' in before && 'score' in after) {
            setCis({
              original: { lo: before.score.ci_low, hi: before.score.ci_high },
              rerun: { lo: after.score.ci_low, hi: after.score.ci_high }
            })
          }
        } catch {
          /* dials still render from delta points; CI rows show when available */
        }
      } catch (err) {
        if (!alive) return
        if (err instanceof ApiError) setError({ code: err.code, message: err.message })
        else setError({ code: 'E-UNK', message: 'Failed to load delta.' })
      }
    })()
    return () => {
      alive = false
    }
  }, [rerunId])

  if (error) {
    return (
      <ErrorBox code={error.code} message={error.message}>
        <Link href='/' className='text-sm underline underline-offset-4'>
          ← Back to setup
        </Link>
      </ErrorBox>
    )
  }

  if (!delta) return <PanelSkeleton lines={6} />

  // Non-overlap in the improvement direction ⇒ distinguishable; else render the honest panel.
  const ciOverlap =
    delta.f_task.after.ci_low < delta.f_task.before.ci_high &&
    delta.verdict.startsWith('coverage failure fell')
  const maxAbsChange = Math.max(...delta.per_sku_changes.map(c => c.abs_change), 0.0001)

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-baseline gap-3'>
        <h1 className='font-pixel text-2xl font-bold tracking-normal'>
          Verification — did the fixes work?
        </h1>
        <Badge
          variant='outline'
          className='h-5 border-sky-500/30 bg-sky-500/10 text-xs text-sky-600 dark:text-sky-400'
        >
          verified re-run
        </Badge>
      </div>
      <p className='text-muted-foreground -mt-3 text-sm'>
        Same trial protocol against the mirrored catalog. Original run{' '}
        <span className='font-mono text-xs'>{delta.original_run_id.slice(0, 8)}</span> vs re-run{' '}
        <span className='font-mono text-xs'>{delta.rerun_run_id.slice(0, 8)}</span>.
      </p>

      {/* ---------- score dials ---------- */}
      <Card>
        <CardContent className='flex flex-col items-center gap-4 py-6'>
          <div className='grid w-full items-center gap-6 md:grid-cols-2'>
            <div className='flex flex-col items-center gap-2'>
              <ScoreDial
                score={delta.score.before}
                lo={cis?.original.lo}
                hi={cis?.original.hi}
                size={150}
              />
              <div className='text-muted-foreground text-xs font-medium tracking-wide uppercase'>
                Before · AgentReady
              </div>
            </div>
            <div className='flex flex-col items-center gap-2'>
              <ScoreDial
                score={delta.score.after}
                lo={cis?.rerun.lo}
                hi={cis?.rerun.hi}
                size={150}
              />
              <div className='text-muted-foreground text-xs font-medium tracking-wide uppercase'>
                After · AgentReady
              </div>
            </div>
          </div>
          <p className='text-base tabular-nums'>
            <strong>
              {num1(delta.score.before)} → {num1(delta.score.after)}
            </strong>{' '}
            {!cis ? (
              <span className='text-muted-foreground text-xs'>
                (CI from run metrics unavailable)
              </span>
            ) : null}
          </p>
        </CardContent>
      </Card>

      {/* ---------- coverage delta + money ---------- */}
      <div className='grid gap-4 lg:grid-cols-2'>
        <Card>
          <CardHeader>
            <CardTitle>Coverage failure rate F_task</CardTitle>
          </CardHeader>
          <CardContent className='flex flex-col gap-4'>
            <Table>
              <TableBody>
                <TableRow>
                  <TableCell className='text-muted-foreground text-sm'>Before</TableCell>
                  <TableCell className='text-right' title='Wilson 95% confidence interval'>
                    <Ci v={delta.f_task.before.value} lo={delta.f_task.before.ci_low} hi={delta.f_task.before.ci_high} fmt={pct} className='font-medium' />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className='text-muted-foreground text-sm'>After</TableCell>
                  <TableCell className='text-right' title='Wilson 95% confidence interval'>
                    <Ci v={delta.f_task.after.value} lo={delta.f_task.after.ci_low} hi={delta.f_task.after.ci_high} fmt={pct} className='font-medium' />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className='text-sm font-medium'>ΔF</TableCell>
                  <TableCell
                    className='text-right'
                    title='95% confidence interval, persona-cluster bootstrap, B = 2,000'
                  >
                    <span className='font-semibold tabular-nums'>
                      {(delta.f_task.delta.value * 100).toFixed(1)} pts
                    </span>{' '}
                    <span className='text-muted-foreground font-mono text-xs'>
                      [{(delta.f_task.delta.ci_low * 100).toFixed(1)} –{' '}
                      {(delta.f_task.delta.ci_high * 100).toFixed(1)}]
                    </span>{' '}
                    <SourceChip kind='measured' />
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <p className='text-sm'>
              Verdict: <strong>{delta.verdict}</strong>
            </p>
            <p className='text-muted-foreground/80 rounded-md border p-3 text-xs'>
              {delta.honest_note}
            </p>
          </CardContent>
        </Card>

        <Card className='border-emerald-500/30'>
          <CardHeader>
            <CardTitle>Money recovered</CardTitle>
          </CardHeader>
          <CardContent className='flex flex-col gap-4'>
            {delta.recoverable_inr ? (
              <>
                <div
                  className='text-3xl font-semibold text-emerald-600 tabular-nums dark:text-emerald-400'
                  title='95% confidence interval, persona-cluster bootstrap, B = 2,000'
                >
                  {inr(delta.recoverable_inr.value)}/mo{' '}
                  <span className='text-muted-foreground font-mono text-sm font-normal'>
                    [{inr(delta.recoverable_inr.ci_low)} – {inr(delta.recoverable_inr.ci_high)}]
                  </span>
                </div>
                <p className='text-muted-foreground text-sm'>
                  {delta.recoverable_inr.note ??
                    'recoverable if approved fixes are applied (verified by re-run)'}
                </p>
              </>
            ) : (
              <p className='text-muted-foreground text-sm'>No recoverable estimate reported.</p>
            )}
            <Button render={<Link href={`/checkout/${delta.original_run_id}`} />}>
              Prove it can buy
              <ArrowRightIcon data-icon='inline-end' />
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* ---------- per-SKU changes ---------- */}
      <Card>
        <CardHeader>
          <CardTitle>Per-product demand shift — top movers</CardTitle>
          <CardDescription>
            Biggest absolute share changes between the two runs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Share before</TableHead>
                <TableHead>Share after</TableHead>
                <TableHead>|Δ|</TableHead>
                <TableHead className='w-[30%]'>Change</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {delta.per_sku_changes.map(c => {
                const gained = c.share_after >= c.share_before
                return (
                  <TableRow key={c.sku}>
                    <TableCell className='font-mono text-xs'>{c.sku}</TableCell>
                    <TableCell className='tabular-nums'>{num2(c.share_before * 100)}%</TableCell>
                    <TableCell className='tabular-nums'>{num2(c.share_after * 100)}%</TableCell>
                    <TableCell className='tabular-nums'>{num2(c.abs_change * 100)}%</TableCell>
                    <TableCell>
                      <BarTrack
                        value={c.abs_change / maxAbsChange}
                        tone={gained ? 'emerald' : 'rose'}
                      />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
          <p className='text-muted-foreground/70 mt-3 text-xs'>
            shares are pooled across models/conditions
            {delta.per_sku_changes.length >= 15 ? ' · top 15 shown' : ''}
          </p>
        </CardContent>
      </Card>

      {/* ---------- honest fallback ---------- */}
      {ciOverlap ? (
        <div className='rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-400'>
          <strong>{HONEST_FALLBACK_TITLE}</strong>
          <br />
          {HONEST_FALLBACK_BODY}
        </div>
      ) : null}
    </div>
  )
}
