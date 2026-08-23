'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'

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
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  BarTrack,
  ErrorBox,
  PanelSkeleton,
  SourceChip,
  StatCard,
  StatusChip,
  TierChip
} from '@/components/agentaudit/bits'
import { Ci } from '@/components/agentaudit/ci'
import { ScoreDial } from '@/components/agentaudit/dial'
import {
  ApiError,
  getAudit,
  getReport,
  getRevenue,
  type AuditStatusResponse,
  type InvisibleSku,
  type ReportResponse,
  type RevenueResponse
} from '@/lib/api'
import { inr, num1, num2, pct, usd } from '@/lib/format'
import { getRerunOf } from '@/lib/runs'

const PARTIAL_BANNER = 'Partial run — cost cap hit. Numbers below are real but incomplete.'
const STRIP_CAPTION =
  'Scenario model. Measured: task-failure rate, concentration, remediation delta. Assumed: agent-traffic share — you set it.'
const SLIDER_VALUES = [0.01, 0.05, 0.1, 0.2]
const DEFAULT_S_AGENT = 0.2
/** Fair share = 1/N (N=40 demo SKUs) = 2.5% */
const FAIR_SHARE = 1 / 40

export default function ResultsPage() {
  const params = useParams<{ id: string }>()
  const runId = params.id

  const [status, setStatus] = useState<AuditStatusResponse['status'] | 'loading'>('loading')
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [preview, setPreview] = useState<RevenueResponse | null>(null)
  const [recoverable, setRecoverable] = useState<RevenueResponse['recoverable_inr']>(null)
  const [rerunId, setRerunId] = useState<string | null>(null)
  const [sAgent, setSAgent] = useState(DEFAULT_S_AGENT)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)

  useEffect(() => {
    let alive = true

    async function load() {
      try {
        // wait for a terminal status before pulling computed metrics
        let st: AuditStatusResponse
        for (;;) {
          st = await getAudit(runId)
          if (!alive) return
          if (st.status === 'done' || st.status === 'partial' || st.status === 'failed') break
          await new Promise(r => setTimeout(r, 2000))
        }
        if (!alive) return
        if (st.status === 'failed') {
          setStatus('failed')
          return
        }
        setStatus(st.status)
        const rep = await getReport(runId)
        if (!alive) return
        setReport(rep)
        setPreview(rep.revenue_preview)
      } catch (err) {
        if (!alive) return
        if (err instanceof ApiError) setError({ code: err.code, message: err.message })
        else setError({ code: 'E-UNK', message: 'Failed to load results.' })
      }
    }

    void load()
    return () => {
      alive = false
    }
  }, [runId])

  useEffect(() => {
    setRerunId(getRerunOf(runId))
  }, [runId])

  useEffect(() => {
    if ((status !== 'done' && status !== 'partial') || !rerunId) return
    let alive = true
    getRevenue(runId, { s_agent: DEFAULT_S_AGENT, delta_run_id: rerunId })
      .then(rev => {
        if (alive) setRecoverable(rev.recoverable_inr)
      })
      .catch(() => {
        /* recoverable stays hidden — it only appears when a rerun delta exists */
      })
    return () => {
      alive = false
    }
  }, [runId, status, rerunId])

  const invisibleBySku = useMemo(() => {
    const m = new Map<string, InvisibleSku>()
    for (const inv of report?.invisible_skus ?? []) m.set(inv.sku, inv)
    return m
  }, [report])

  const movers = useMemo(
    () =>
      [...(report?.framing.per_product ?? [])]
        .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
        .slice(0, 5),
    [report]
  )

  if (error) {
    return (
      <ErrorBox code={error.code} message={error.message}>
        <Link href='/' className='text-sm underline underline-offset-4'>
          ← Back to setup
        </Link>
      </ErrorBox>
    )
  }

  if (status === 'failed') {
    return (
      <div className='rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-700 dark:text-rose-400'>
        This run failed. <Link href='/' className='underline underline-offset-4'>Start a new audit</Link>.
      </div>
    )
  }

  if (!report) {
    return (
      <div className='flex flex-col gap-4'>
        <PanelSkeleton lines={3} />
        <PanelSkeleton lines={5} />
        <PanelSkeleton lines={5} />
      </div>
    )
  }

  // RaR scales linearly with the slider (multiplication only — never a measured quantity)
  const baseRar = preview?.revenue_at_risk_inr
  const rarScale =
    baseRar && preview && preview.inputs.s_agent.value > 0
      ? sAgent / preview.inputs.s_agent.value
      : 0

  return (
    <div className='flex flex-col gap-6'>
      {report.partial || status === 'partial' ? (
        <div className='rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-400'>
          {PARTIAL_BANNER}
        </div>
      ) : null}

      {/* ---------- headline strip ---------- */}
      <Card className='sticky top-14 z-30'>
        <CardContent className='flex flex-col gap-4 py-5'>
          <div className='grid items-center gap-6 md:grid-cols-3'>
            <div className='flex items-center gap-4'>
              <ScoreDial score={report.score.value} lo={report.score.ci_low} hi={report.score.ci_high} size={104} />
              <div>
                <div className='text-muted-foreground text-xs font-medium tracking-wide uppercase'>
                  AgentReady Score
                </div>
                <div
                  className='text-muted-foreground mt-1 font-mono text-xs'
                  title='95% confidence interval, persona-cluster bootstrap, B = 2,000'
                >
                  [{report.score.ci_low.toFixed(1)} – {report.score.ci_high.toFixed(1)}]
                </div>
                <div className='mt-2 flex flex-wrap gap-1.5'>
                  <SourceChip kind='measured' label='640 trials' />
                  <StatusChip status={report.status} />
                </div>
              </div>
            </div>

            <div>
              <div className='text-muted-foreground text-xs font-medium tracking-wide uppercase'>
                Revenue at Risk /mo @ {(sAgent * 100).toFixed(0)}%
              </div>
              {baseRar ? (
                <>
                  <div
                    className='mt-1 text-2xl font-semibold tabular-nums'
                    title='95% confidence interval, persona-cluster bootstrap, B = 2,000'
                  >
                    {inr(baseRar.value * rarScale)}{' '}
                    <span className='text-muted-foreground font-mono text-sm font-normal'>
                      [{inr(baseRar.ci_low * rarScale)} – {inr(baseRar.ci_high * rarScale)}]
                    </span>
                  </div>
                  <div className='text-muted-foreground mt-1.5 text-xs'>
                    F_task {pct(report.coverage.f_task.value)}{' '}
                    <span className='font-mono'>
                      [{pct(report.coverage.f_task.ci_low)} – {pct(report.coverage.f_task.ci_high)}]
                    </span>{' '}
                    <SourceChip kind='measured' /> · S = {(sAgent * 100).toFixed(0)}%{' '}
                    <SourceChip kind='assumed' />
                  </div>
                </>
              ) : null}
            </div>

            <div>
              <div className='text-muted-foreground text-xs font-medium tracking-wide uppercase'>
                Recoverable
              </div>
              {recoverable ? (
                <>
                  <div
                    className='mt-1 text-2xl font-semibold text-emerald-600 tabular-nums dark:text-emerald-400'
                    title='95% confidence interval, persona-cluster bootstrap, B = 2,000'
                  >
                    {inr(recoverable.value)}/mo{' '}
                    <span className='text-muted-foreground font-mono text-sm font-normal'>
                      [{inr(recoverable.ci_low)} – {inr(recoverable.ci_high)}]
                    </span>
                  </div>
                  <div className='mt-1.5 flex flex-wrap items-center gap-1.5'>
                    <SourceChip kind='verified' label='verified re-run' />
                    {rerunId ? (
                      <Link
                        href={`/delta/${rerunId}`}
                        className='text-primary text-xs underline underline-offset-4'
                      >
                        see verification →
                      </Link>
                    ) : null}
                  </div>
                </>
              ) : (
                <>
                  <div className='text-muted-foreground/60 mt-1 text-2xl font-semibold'>—</div>
                  <div className='text-muted-foreground/70 text-xs'>(after remediation re-run)</div>
                </>
              )}
            </div>
          </div>

          <Separator />

          <div className='text-muted-foreground flex flex-wrap items-center gap-4 text-xs'>
            {STRIP_CAPTION}
            <span className='ml-auto flex items-center gap-2.5'>
              <input
                type='range'
                min={0}
                max={3}
                step={1}
                value={SLIDER_VALUES.indexOf(sAgent)}
                onChange={e => setSAgent(SLIDER_VALUES[Number(e.target.value)])}
                aria-label='agent-traffic share'
                className='w-32 accent-[var(--primary)]'
              />
              <span className='text-muted-foreground/70 font-mono text-xs'>
                1% · 5% · 10% · 20%
              </span>
            </span>
          </div>
        </CardContent>
      </Card>

      {/* ---------- choice heat table ---------- */}
      <Card>
        <CardHeader>
          <CardTitle className='text-base'>Choice heat map</CardTitle>
          <CardDescription>
            How agent demand spread across the catalog. Concentration (HHI, normalized):{' '}
            <Ci v={report.hhi_norm.value} lo={report.hhi_norm.ci_low} hi={report.hhi_norm.ci_high} fmt={num2} /> —
            higher means agents pile onto fewer products.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Demand share</TableHead>
                <TableHead className='min-w-28'>Legibility</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(report.legibility ?? []).map(row => {
                const inv = invisibleBySku.get(row.sku)
                const comp = row.composite ?? 0
                return (
                  <TableRow key={row.sku} className={inv ? 'bg-rose-500/5' : undefined}>
                    <TableCell className='font-mono text-xs'>
                      {inv ? <span className='mr-1 text-rose-500'>⚠</span> : null}
                      {row.sku}
                    </TableCell>
                    <TableCell className='max-w-52 truncate text-sm'>{row.title}</TableCell>
                    <TableCell>
                      <TierChip tier={row.tier} />
                    </TableCell>
                    <TableCell className='text-sm tabular-nums'>
                      {inv ? (
                        <span
                          className='inline-flex items-center gap-2'
                          title='95% confidence interval, persona-cluster bootstrap, B = 2,000'
                        >
                          <BarTrack value={Math.min(1, inv.share.value * 8)} tone='rose' style={{ width: 56 }} />
                          {pct(inv.share.value)}{' '}
                          <span className='text-muted-foreground font-mono text-xs'>
                            [{pct(inv.share.ci_low)} – {pct(inv.share.ci_high)}]
                          </span>
                        </span>
                      ) : (
                        <span className='text-muted-foreground/50'>—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className='flex items-center gap-2'>
                        <BarTrack value={comp} style={{ width: 64 }} />
                        <span className='text-muted-foreground font-mono text-xs'>
                          {row.composite !== null ? num2(comp) : 'n/a'}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      {inv ? (
                        <span className='text-xs text-rose-600 dark:text-rose-400'>⚠ Invisible</span>
                      ) : (
                        <span className='text-muted-foreground text-xs'>Visible</span>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
          <p className='text-muted-foreground/70 mt-3 text-xs'>
            Invisible = 95% CI upper bound below 2.5% fair share · demand share renders where the API
            reports it (invisible SKUs) · metric: hhi_norm
            {report.partial ? ` · computed on ${report.trials.total}/640 trials` : ''}
          </p>
        </CardContent>
      </Card>

      {/* ---------- invisible strip ---------- */}
      <Card>
        <CardHeader>
          <CardTitle className='text-base'>Invisible to agents</CardTitle>
          <CardDescription>
            Flagged because the upper bound of their 95% demand-share interval sits below fair share
            (1/N = 2.5%) — an agent picking uniformly at random would beat them.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {report.invisible_skus.length === 0 ? (
            <p className='text-sm text-emerald-600 dark:text-emerald-400'>None flagged in this run.</p>
          ) : (
            <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
              {report.invisible_skus.map(s => (
                <StatCard
                  key={s.sku}
                  k={s.sku}
                  v={
                    <span
                      title='95% confidence interval, persona-cluster bootstrap, B = 2,000'
                      className='font-mono'
                    >
                      {pct(s.share.value)}{' '}
                      <span className='text-muted-foreground text-sm'>
                        [{pct(s.share.ci_low)} – {pct(s.share.ci_high)}]
                      </span>
                    </span>
                  }
                  sub={<span className='text-rose-600 dark:text-rose-400'>CI-upper &lt; 1/N → invisible</span>}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ---------- framing + stability + position ---------- */}
      <Card>
        <CardHeader>
          <CardTitle className='text-base'>Framing sensitivity</CardTitle>
          <CardDescription>
            Rewriting listing copy (condition C3-A vs C3-B) shifts agent choices. Mean shift across
            the framing subset:{' '}
            <Ci
              v={report.framing.mean_delta.value}
              lo={report.framing.mean_delta.ci_low}
              hi={report.framing.mean_delta.ci_high}
              fmt={pct}
            />
          </CardDescription>
        </CardHeader>
        <CardContent>
          {movers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Share A (control copy)</TableHead>
                  <TableHead>Share B (variant copy)</TableHead>
                  <TableHead>Δ</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {movers.map(m => (
                  <TableRow key={m.sku}>
                    <TableCell className='font-mono text-xs'>{m.sku}</TableCell>
                    <TableCell className='tabular-nums'>{pct(m.share_a)}</TableCell>
                    <TableCell className='tabular-nums'>{pct(m.share_b)}</TableCell>
                    <TableCell className='tabular-nums'>
                      <span
                        className={
                          Math.abs(m.delta) > 0.05
                            ? 'text-amber-600 dark:text-amber-400'
                            : undefined
                        }
                      >
                        {m.delta >= 0 ? '+' : ''}
                        {pct(m.delta)}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className='text-muted-foreground text-sm'>No framing-subset data reported for this catalog.</p>
          )}
        </CardContent>
      </Card>

      <div className='grid gap-4 lg:grid-cols-2'>
        {/* ---------- stability ---------- */}
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>Stability across models</CardTitle>
            <CardDescription>
              Pairwise cosine similarity of product rankings between models. Mean:{' '}
              <Ci
                v={report.stability.mean.value}
                lo={report.stability.mean.ci_low}
                hi={report.stability.mean.ci_high}
                fmt={num2}
              />
            </CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-3'>
            <StabilityMatrix matrix={report.stability.matrix} />
            <p className='text-muted-foreground/70 text-xs'>
              aligned &gt; 0.8 · moderate 0.5–0.8 · divergent &lt; 0.5 · metric: stability.mean
            </p>
          </CardContent>
        </Card>

        {/* ---------- position bias ---------- */}
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>Position bias</CardTitle>
            <CardDescription>
              Agents favor what&rsquo;s listed first; randomized order (C2) isolates this.
            </CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-3'>
            <div className='grid grid-cols-3 gap-2 text-sm'>
              <div>
                <div className='text-muted-foreground text-xs uppercase'>Top-3 capture</div>
                <Ci
                  v={report.position.top3_capture.value}
                  lo={report.position.top3_capture.ci_low}
                  hi={report.position.top3_capture.ci_high}
                  fmt={pct}
                  className='font-medium'
                />
              </div>
              <div>
                <div className='text-muted-foreground text-xs uppercase'>Lift vs chance</div>
                <div className='tabular-nums'>{num1(report.position.lift)}×</div>
              </div>
              <div>
                <div className='text-muted-foreground text-xs uppercase'>Permutation p</div>
                <div className='tabular-nums'>
                  {report.position.p_value < 0.001
                    ? '< 0.001'
                    : report.position.p_value.toFixed(4)}
                </div>
              </div>
            </div>
            <SlotChart perSlot={report.position.per_slot} />
            <p className='text-muted-foreground/70 text-xs'>
              dashed line = 2.5% fair share per slot · metric: position.top3_capture
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ---------- coverage ---------- */}
      <Card>
        <CardHeader>
          <CardTitle className='text-base'>Coverage — &ldquo;nothing fits&rdquo; rate</CardTitle>
          <CardDescription>
            Share of agent tasks that ended with no purchase:{' '}
            <Ci
              v={report.coverage.f_task.value}
              lo={report.coverage.f_task.ci_low}
              hi={report.coverage.f_task.ci_high}
              fmt={pct}
              className='text-base font-semibold'
            />{' '}
            <SourceChip kind='measured' /> — this measured failure rate drives the Revenue-at-Risk
            model.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {report.coverage.nulls_by_persona.length > 0 ? (
            <div className='max-w-md'>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Persona</TableHead>
                    <TableHead>Null rate</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[...report.coverage.nulls_by_persona]
                    .sort((a, b) => b.null_rate - a.null_rate)
                    .slice(0, 5)
                    .map(p => (
                      <TableRow key={p.persona_id}>
                        <TableCell className='font-mono text-xs'>{p.persona_id}</TableCell>
                        <TableCell className='tabular-nums'>{pct(p.null_rate)}</TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* ---------- run details ---------- */}
      <Card>
        <CardHeader>
          <CardTitle className='text-base'>Run details</CardTitle>
        </CardHeader>
        <CardContent className='flex flex-col gap-4'>
          <div className='grid gap-3 sm:grid-cols-3'>
            <StatCard
              k='Trials'
              v={`${report.trials.total}`}
              sub={`${report.trials.parse_ok} parsed ok · ${report.trials.forced} forced-choice`}
            />
            <StatCard k='Cost' v={usd(report.cost_usd)} sub='billed provider spend' />
            <StatCard
              k='Run id'
              v={<span className='font-mono text-base'>{report.run_id.slice(0, 8)}</span>}
              sub={report.manifest_ref ?? 'live run'}
            />
          </div>
          <div className='max-w-md'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Model</TableHead>
                  <TableHead>Parse-failure rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.models_meta.map(m => (
                  <TableRow key={m.id}>
                    <TableCell className='font-mono text-xs'>{m.id}</TableCell>
                    <TableCell className='tabular-nums'>{pct(m.parse_failure_rate)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <Separator />

          <div className='flex flex-wrap gap-3'>
            <Button variant='outline' render={<Link href={`/checkout/${runId}`} />}>
              Watch an agent buy →
            </Button>
            <Button render={<Link href={`/audit/${runId}/fixes`} />}>Fix what&rsquo;s broken →</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function StabilityMatrix({ matrix }: { matrix: Record<string, number> }) {
  const entries = Object.entries(matrix)
  return (
    <div className='flex flex-col gap-2.5'>
      {entries.map(([pair, val]) => {
        const tone = val > 0.8 ? 'emerald' : val >= 0.5 ? 'primary' : 'rose'
        return (
          <div key={pair} className='grid grid-cols-[170px_1fr_44px] items-center gap-3 text-xs'>
            <span className='text-muted-foreground truncate font-mono'>{pair.replace('|', ' ↔ ')}</span>
            <BarTrack value={val} tone={tone as 'emerald' | 'primary' | 'rose'} />
            <span className='text-right font-mono tabular-nums'>{num2(val)}</span>
          </div>
        )
      })}
    </div>
  )
}

function SlotChart({ perSlot }: { perSlot: number[] }) {
  if (perSlot.length === 0) {
    return <p className='text-muted-foreground text-sm'>No per-slot data reported.</p>
  }
  const max = Math.max(...perSlot, FAIR_SHARE)
  return (
    <div className='relative flex h-24 items-end gap-[2px] border-l border-b pl-1'>
      <div
        className='border-muted-foreground/50 pointer-events-none absolute right-0 left-0 border-t border-dashed'
        style={{ bottom: `${(FAIR_SHARE / max) * 100}%` }}
      />
      {perSlot.map((v, i) => (
        <div
          key={i}
          title={`slot ${i + 1}: ${pct(v)}`}
          className={i < 3 ? 'bg-primary' : 'bg-muted-foreground/40'}
          style={{ flex: 1, height: `${Math.max(1, (v / max) * 100)}%` }}
        />
      ))}
    </div>
  )
}
