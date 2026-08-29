'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table'
import { ErrorBox, PanelSkeleton, SourceChip } from '@/components/agentaudit/bits'
import { Ci } from '@/components/agentaudit/ci'
import { ApiError, getRevenue, type RevenueResponse } from '@/lib/api'
import { inr, inrGrouped, parseInr } from '@/lib/format'
import { getRerunOf } from '@/lib/runs'

const SLIDER_VALUES = [0.01, 0.05, 0.1, 0.2]
const DEMO_DEFAULT_GMV = 800000

export default function RevenuePage() {
  const params = useParams<{ id: string }>()
  const runId = params.id

  const [sliderIdx, setSliderIdx] = useState(3) // default 20%
  const [gmvText, setGmvText] = useState(inrGrouped(DEMO_DEFAULT_GMV))
  const [gmvTouched, setGmvTouched] = useState(false)
  const [data, setData] = useState<RevenueResponse | null>(null)
  const [rerunId, setRerunId] = useState<string | null>(null)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const debounceRef = useRef<number | null>(null)

  useEffect(() => {
    setRerunId(getRerunOf(runId))
  }, [runId])

  useEffect(() => {
    let alive = true

    async function load() {
      try {
        const rev = await getRevenue(runId, {
          s_agent: SLIDER_VALUES[sliderIdx],
          gmv_inr: undefined, // first load: let the server label its own demo default
          delta_run_id: rerunId ?? undefined
        })
        if (!alive) return
        setData(rev)
        setError(null)
      } catch (err) {
        if (!alive) return
        if (err instanceof ApiError) setError({ code: err.code, message: err.message })
        else setError({ code: 'E-UNK', message: 'Failed to load revenue model.' })
      }
    }

    void load()
    return () => {
      alive = false
    }
  }, [runId, sliderIdx, rerunId])

  // refetch when GMV edited (debounced)
  function onGmvChange(text: string) {
    setGmvText(text)
    setGmvTouched(true)
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(async () => {
      const parsed = parseInr(text)
      if (!Number.isFinite(parsed)) return
      try {
        const rev = await getRevenue(runId, {
          s_agent: SLIDER_VALUES[sliderIdx],
          gmv_inr: parsed,
          delta_run_id: rerunId ?? undefined
        })
        setData(rev)
        setError(null)
      } catch (err) {
        if (err instanceof ApiError) setError({ code: err.code, message: err.message })
      }
    }, 450)
  }

  const gmvParsed = parseInr(gmvText)
  const gmvValid = Number.isFinite(gmvParsed)

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-baseline gap-3'>
        <h1 className='font-pixel text-2xl font-bold tracking-normal'>Revenue at Risk</h1>
        <span className='text-muted-foreground text-sm'>
          run <span className='font-mono text-xs'>{runId.slice(0, 8)}</span> ·{' '}
          <Link
            href={`/audit/${runId}/results`}
            className='text-primary text-xs underline underline-offset-4'
          >
            back to results
          </Link>
        </span>
      </div>

      {error ? (
        <ErrorBox code={error.code} message={error.message} />
      ) : !data ? (
        <PanelSkeleton lines={5} />
      ) : data.not_measurable ? (
        <Card className='border-amber-500/40'>
          <CardHeader>
            <CardTitle>Revenue at Risk — not measurable</CardTitle>
            <CardDescription>
              The walk-away rate could not be measured for this run.
            </CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-3'>
            <div className='text-3xl font-semibold tabular-nums'>—</div>
            <p className='text-muted-foreground text-sm'>{data.not_measurable_note}</p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* ---------- scenario controls ---------- */}
          <Card>
            <CardHeader>
              <CardTitle>Scenario inputs</CardTitle>
              <CardDescription>
                Two assumptions, clearly labeled — everything else on this page is measured.
              </CardDescription>
            </CardHeader>
            <CardContent className='grid gap-6 md:grid-cols-2'>
              <div>
                <label className='text-muted-foreground mb-2 flex flex-wrap items-center gap-2 text-sm font-medium' htmlFor='sagent-slider'>
                  Agent-traffic share <SourceChip kind='assumed' />
                  <strong className='text-foreground tabular-nums'>
                    {(SLIDER_VALUES[sliderIdx] * 100).toFixed(0)}%
                  </strong>
                  <span className='text-muted-foreground/70 text-xs'>you set this</span>
                </label>
                <input
                  id='sagent-slider'
                  type='range'
                  min={0}
                  max={3}
                  step={1}
                  value={sliderIdx}
                  onChange={e => setSliderIdx(Number(e.target.value))}
                  className='w-full max-w-sm accent-[var(--primary)]'
                />
                <div className='text-muted-foreground/70 mt-1 flex max-w-sm justify-between font-mono text-xs'>
                  {SLIDER_VALUES.map(v => (
                    <span key={v}>{(v * 100).toFixed(0)}%</span>
                  ))}
                </div>
              </div>

              <div>
                <label className='text-muted-foreground mb-2 flex items-center gap-2 text-sm font-medium' htmlFor='gmv-input'>
                  Monthly GMV
                  <span className='text-muted-foreground/70 text-xs'>
                    {gmvTouched ? 'you set this' : 'demo default'}
                  </span>
                </label>
                <Input
                  id='gmv-input'
                  type='text'
                  inputMode='numeric'
                  className='max-w-sm font-mono tabular-nums'
                  value={gmvText}
                  onChange={e => onGmvChange(e.target.value)}
                  aria-invalid={!gmvValid}
                />
                {!gmvValid ? (
                  <div className='mt-1.5 text-xs text-rose-600 dark:text-rose-400'>
                    E110 — enter a GMV above ₹10,000
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>

          {/* ---------- outputs ---------- */}
          <div className='grid gap-4 md:grid-cols-2'>
            <Card>
              <CardHeader>
                <CardTitle>Revenue at Risk</CardTitle>
                <CardDescription>
                  GMV × agent share × measured task-failure rate. Scenario output — it moves linearly
                  with the two assumptions above.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div
                  className='text-3xl font-semibold tabular-nums'
                  title='95% confidence interval, persona-cluster bootstrap, B = 2,000'
                >
                  {inr(data.revenue_at_risk_inr!.value)}/mo{' '}
                  <span className='text-muted-foreground font-mono text-sm font-normal'>
                    [{inr(data.revenue_at_risk_inr!.ci_low)} – {inr(data.revenue_at_risk_inr!.ci_high)}]
                  </span>
                </div>
                <div className='text-muted-foreground mt-3 text-xs'>
                  <SourceChip kind='scenario' /> adjusted by the walk-away rate{' '}
                  <Ci v={data.inputs.f_task.value!} lo={data.inputs.f_task.ci_low!} hi={data.inputs.f_task.ci_high!} fmt={n => n.toFixed(4)} />{' '}
                  <SourceChip kind='measured' label='[measured · live shopping missions]' />
                </div>
                {data.zero_measured_note ? (
                  <p className='text-emerald-600 mt-3 text-xs dark:text-emerald-400'>
                    {data.zero_measured_note}
                  </p>
                ) : null}
              </CardContent>
            </Card>

            {data.recoverable_inr ? (
              <Card className='border-emerald-500/40'>
                <CardHeader>
                  <CardTitle>Recoverable</CardTitle>
                  <CardDescription>
                    Recovered if the approved fixes hold up — verified by re-run.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div
                    className='text-3xl font-semibold text-emerald-600 tabular-nums dark:text-emerald-400'
                    title='95% confidence interval, persona-cluster bootstrap, B = 2,000'
                  >
                    {inr(data.recoverable_inr.value)}/mo{' '}
                    <span className='text-muted-foreground font-mono text-sm font-normal'>
                      [{inr(data.recoverable_inr.ci_low)} – {inr(data.recoverable_inr.ci_high)}]
                    </span>
                  </div>
                  <div className='text-muted-foreground mt-3 flex flex-wrap items-center gap-2 text-xs'>
                    ΔF {data.delta_f ? data.delta_f.value.toFixed(4) : '—'}{' '}
                    {data.delta_f ? (
                      <span className='font-mono'>
                        [{data.delta_f.ci_low.toFixed(4)} – {data.delta_f.ci_high.toFixed(4)}]
                      </span>
                    ) : null}{' '}
                    <SourceChip kind='verified' label='[measured ΔF]' />
                    {rerunId ? (
                      <Link
                        href={`/delta/${rerunId}`}
                        className='text-primary underline underline-offset-4'
                      >
                        see verification →
                      </Link>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>Recoverable</CardTitle>
                  <CardDescription>
                    Appears after a remediation re-run verifies how much risk the fixes actually
                    remove. No verified delta exists for this run yet.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Link
                    href={`/audit/${runId}/fixes`}
                    className='text-primary text-sm underline underline-offset-4'
                  >
                    Review fixes →
                  </Link>
                </CardContent>
              </Card>
            )}
          </div>

          {/* ---------- inputs ledger ---------- */}
          <Card>
            <CardHeader>
              <CardTitle>
                Inputs — every number is labeled by where it came from
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Input</TableHead>
                    <TableHead>Value</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Note</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell className='text-sm'>Monthly GMV</TableCell>
                    <TableCell className='font-mono text-xs tabular-nums'>
                      {inrGrouped(gmvValid ? gmvParsed : DEMO_DEFAULT_GMV)}
                    </TableCell>
                    <TableCell>
                      <SourceChip
                        kind='input'
                        label={data.inputs.gmv_inr.source === 'user' ? 'you set this' : 'demo default'}
                      />
                    </TableCell>
                    <TableCell className='text-muted-foreground max-w-72 text-xs'>
                      {data.inputs.gmv_inr.note}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className='text-sm'>Agent share (S)</TableCell>
                    <TableCell className='font-mono text-xs tabular-nums'>
                      {(data.inputs.s_agent.value * 100).toFixed(0)}%
                    </TableCell>
                    <TableCell>
                      <SourceChip kind='assumed' label='you set this' />
                    </TableCell>
                    <TableCell className='text-muted-foreground max-w-72 text-xs'>
                      {data.inputs.s_agent.note}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className='text-sm'>Walk-away rate (agents who bought nothing)</TableCell>
                    <TableCell className='font-mono text-xs tabular-nums'>
                      <Ci
                        v={(data.inputs.f_task.value ?? 0) * 100}
                        lo={(data.inputs.f_task.ci_low ?? 0) * 100}
                        hi={(data.inputs.f_task.ci_high ?? 0) * 100}
                        fmt={n => `${n.toFixed(1)}%`}
                      />
                    </TableCell>
                    <TableCell>
                      <SourceChip kind='measured' label='[measured · live shopping missions]' />
                    </TableCell>
                    <TableCell className='text-muted-foreground max-w-72 text-xs'>
                      {data.inputs.f_task.note}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
              <p className='text-muted-foreground/80 mt-3 rounded-md border p-3 text-xs'>
                {data.honesty_note}
              </p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
