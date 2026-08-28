'use client'

import Link from 'next/link'
import { Fragment, useCallback, useEffect, useState } from 'react'

import {
  AlertTriangleIcon,
  ChevronRightIcon,
  ClockIcon,
  RefreshCwIcon
} from 'lucide-react'

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
import { ErrorBox, StatusChip, Term } from '@/components/agentaudit/bits'
import { Peep } from '@/components/Peep'
import { cn } from '@/lib/utils'
import { ApiError, listRuns, type RunSummaryRow } from '@/lib/api'
import { num1, pct, usd } from '@/lib/format'

const STALL_HINT =
  'Runs whose engine was interrupted (server restart, provider outage) keep every recorded mission — open one to see exactly what was measured before the stop.'

function since(iso: string | null): string {
  if (!iso) return '—'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${Math.round(s)}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

export function RunsDashboard({ refreshKey = 0 }: { refreshKey?: number }) {
  const [rows, setRows] = useState<RunSummaryRow[] | null>(null)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const load = useCallback(() => {
    listRuns(10)
      .then(res => {
        setRows(res.runs)
        setError(null)
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError({ code: err.code, message: err.message })
        else setError({ code: 'E-UNK', message: 'Failed to load runs.' })
      })
  }, [])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  return (
    <Card>
      <CardHeader>
        <div className='flex items-center gap-2'>
          <ClockIcon className='text-muted-foreground size-4' />
          <CardTitle className='text-base'>Recent runs</CardTitle>
          <Button
            variant='ghost'
            size='icon-sm'
            onClick={load}
            title='Refresh'
            className='ml-auto'
          >
            <RefreshCwIcon />
          </Button>
        </div>
        <CardDescription>
          Every audit on this backend — how far it got, what it found, and fixes to review.{' '}
          {STALL_HINT}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <ErrorBox code={error.code} message={error.message} />
        ) : rows === null ? (
          <p className='text-muted-foreground text-sm'>Loading runs…</p>
        ) : rows.length === 0 ? (
          <div className='flex flex-col items-center gap-6 py-8 text-center'>
            <Peep
              src='/illustrations/openpeeps/peep-13.svg'
              alt=''
              className='h-24 w-auto opacity-50'
            />
            <p className='text-muted-foreground text-sm'>
              No runs yet — start a demo audit or import a real store above.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className='w-8' />
                <TableHead>Run</TableHead>
                <TableHead>Catalog</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Early read-out</TableHead>
                <TableHead>Suggested fixes</TableHead>
                <TableHead className='text-right'>Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(row => {
                const open = expanded === row.run_id
                return (
                  <Fragment key={row.run_id}>
                    <TableRow
                      className='cursor-pointer'
                      onClick={() => setExpanded(open ? null : row.run_id)}
                    >
                      <TableCell>
                        <ChevronRightIcon
                          className={cn(
                            'text-muted-foreground size-3.5 transition-transform',
                            open && 'rotate-90'
                          )}
                        />
                      </TableCell>
                      <TableCell>
                        <div className='flex flex-col'>
                          <span className='font-mono text-xs'>{row.run_id.slice(0, 8)}</span>
                          <span className='text-muted-foreground/70 text-[11px]'>
                            {row.type === 'rerun' ? 'verification re-run' : 'audit'} ·{' '}
                            {since(row.started_at)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className='flex flex-col'>
                          <span className='max-w-40 truncate text-sm'>
                            {row.catalog.merchant ?? row.catalog.source ?? '—'}
                          </span>
                          <span className='text-muted-foreground/70 text-[11px]'>
                            {row.catalog.source} · {row.catalog.products ?? '?'} products
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <StatusChip status={row.status} />
                      </TableCell>
                      <TableCell className='font-mono text-xs tabular-nums'>
                        {row.trials_recorded}/{row.trials_total}
                        {row.summary ? (
                          <span className='text-muted-foreground/70 block'>
                            {row.summary.parse_ok} usable
                          </span>
                        ) : null}
                      </TableCell>
                      <TableCell className='text-sm tabular-nums'>
                        {row.summary ? (
                          <span>
                            <Term
                              tip='Store score from 0–100 — how easily AI agents can see, pick, and buy your products.'
                            >
                              AgentReady <strong>{num1(row.summary.score)}</strong>
                            </Term>{' '}
                            ·{' '}
                            <Term tip='Share of shopping missions where the agent gave up without buying anything.'>
                              walk-away {pct(row.summary.f_task)}
                            </Term>
                          </span>
                        ) : (
                          <span className='text-muted-foreground/50'>nothing measurable yet</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {row.fixes_needed > 0 ? (
                          <Badge
                            variant='outline'
                            className='h-5 border-amber-500/30 bg-amber-500/10 text-xs text-amber-600 dark:text-amber-400'
                          >
                            {row.fixes_needed} listings
                          </Badge>
                        ) : (
                          <span className='text-muted-foreground/50 text-xs'>—</span>
                        )}
                      </TableCell>
                      <TableCell className='text-right font-mono text-xs tabular-nums'>
                        {usd(row.cost_usd)}
                      </TableCell>
                    </TableRow>
                    {open ? (
                      <TableRow className='bg-muted/30 hover:bg-muted/30'>
                        <TableCell colSpan={8} className='px-6 py-4'>
                          <div className='flex flex-col gap-3'>
                            {row.status === 'failed' || row.status === 'partial' ? (
                              <div
                                className={cn(
                                  'flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm',
                                  row.status === 'failed'
                                    ? 'border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300'
                                    : 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300'
                                )}
                              >
                                <AlertTriangleIcon className='mt-0.5 size-4 shrink-0' />
                                <div>
                                  <strong className='capitalize'>
                                    Why this run {row.status === 'failed' ? 'failed' : 'stopped early'}
                                    :
                                  </strong>{' '}
                                  {row.abort_reason ?? 'no reason recorded'}
                                  {row.trials_recorded > 0 ? (
                                    <>
                                      {' '}
                                      <strong>{row.trials_recorded}</strong> of{' '}
                                      {row.trials_total} shopping missions were completed before
                                      the stop
                                      {row.summary
                                        ? ` (${row.summary.parse_ok} gave a usable answer)`
                                        : ''}
                                      .
                                    </>
                                  ) : null}
                                </div>
                              </div>
                            ) : null}

                            {row.summary ? (
                              <div className='grid gap-3 sm:grid-cols-3'>
                                <div className='rounded-lg border p-3'>
                                  <div className='text-muted-foreground text-[11px] uppercase'>
                                    AgentReady store score
                                  </div>
                                  <div className='mt-1 text-lg font-semibold tabular-nums'>
                                    {num1(row.summary.score)}
                                  </div>
                                  <div className='text-muted-foreground/70 mt-0.5 text-[11px]'>
                                    0–100 · how easily AI agents buy from you
                                  </div>
                                </div>
                                <div className='rounded-lg border p-3'>
                                  <div className='text-muted-foreground text-[11px] uppercase'>
                                    Walk-away rate
                                  </div>
                                  <div className='mt-1 text-lg font-semibold tabular-nums'>
                                    {pct(row.summary.f_task)}
                                  </div>
                                  <div className='text-muted-foreground/70 mt-0.5 text-[11px]'>
                                    missions where the agent bought nothing
                                  </div>
                                </div>
                                <div className='rounded-lg border p-3'>
                                  <div className='text-muted-foreground text-[11px] uppercase'>
                                    AI model health
                                  </div>
                                  <div className='mt-1 flex flex-col gap-0.5 font-mono text-[11px]'>
                                    {Object.entries(row.summary.models).map(([m, s]) => (
                                      <span key={m}>
                                        {m}: {s.parse_ok}/{s.attempts} missions answered
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            ) : null}

                            <div className='text-muted-foreground text-xs'>{row.summary?.note}</div>

                            <div className='flex flex-wrap gap-2'>
                              {row.summary ? (
                                <Button size='sm' render={<Link href={`/audit/${row.run_id}/results`} />}>
                                  {row.status === 'done'
                                    ? 'View results'
                                    : 'View data measured so far'}
                                </Button>
                              ) : null}
                              {row.status === 'done' || row.status === 'partial' ? (
                                <Button
                                  size='sm'
                                  variant='outline'
                                  render={<Link href={`/audit/${row.run_id}/fixes`} />}
                                >
                                  {row.fixes_needed > 0
                                    ? `Review ${row.fixes_needed} fix${row.fixes_needed === 1 ? '' : 'es'}`
                                    : 'Review fixes'}
                                </Button>
                              ) : null}
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </Fragment>
                )
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
