'use client'

import { useEffect, useMemo, useState, useSyncExternalStore } from 'react'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { CheckIcon, ClipboardCopyIcon } from 'lucide-react'

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
  Term,
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
import { AGENT_TOOLS, buildFixPrompt, copyText } from '@/lib/fixPrompt'
import { personaLabel } from '@/lib/glossary'
import { getRerunOf } from '@/lib/runs'

const PARTIAL_BANNER = 'Partial run — the spend cap was reached. Numbers below are real but incomplete.'

const STRIP_CAPTION =
  'How to read this: failure rate and demand concentration are measured from real agent trials; the traffic share is a scenario you set.'


/** Friendly wording for the confidence-interval tooltips that repeat page-wide. */
const CI_TIP = 'Likely range for the true value (95% confidence) — narrower means more certainty.'
const SLIDER_VALUES = [0.01, 0.05, 0.1, 0.2]
const DEFAULT_S_AGENT = 0.2

/** Fair share = 1/N (N=40 demo SKUs) = 2.5% */
const FAIR_SHARE = 1 / 40

export default function ResultsPage() {
  const params = useParams<{ id: string }>()
  const runId = params.id

  const [status, setStatus] = useState<AuditStatusResponse['status'] | 'loading'>('loading')
  const [abortReason, setAbortReason] = useState<string | null>(null)
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [preview, setPreview] = useState<RevenueResponse | null>(null)
  const [recoverable, setRecoverable] = useState<RevenueResponse['recoverable_inr']>(null)
  const [sAgent, setSAgent] = useState(DEFAULT_S_AGENT)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const [progress, setProgress] = useState<{ done: number; total: number | null } | null>(null)

  useEffect(() => {
    let alive = true

    async function load() {
      try {
        // wait for a terminal status before pulling computed metrics — but
        // break out if the run stops making progress (engine lost/stalled)
        // so recorded mid-data still renders
        let st: AuditStatusResponse
        let lastDone = -1
        let stalePolls = 0

        for (;;) {
          st = await getAudit(runId)
          if (!alive) return
          if (st.status === 'done' || st.status === 'partial' || st.status === 'failed') break
          setProgress({ done: st.trials_done, total: st.trials_total })
          if (st.trials_done === lastDone) stalePolls += 1
          else stalePolls = 0
          lastDone = st.trials_done
          if (stalePolls >= 45) break // ~90 s with zero new trials
          await new Promise(r => setTimeout(r, 2000))
        }

        if (!alive) return
        setStatus(st.status)
        setAbortReason(st.abort_reason ?? null)

        if (st.status === 'failed' && st.trials_done === 0) {
          return // nothing was measured — the banner says it all
        }

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

  // rerun linkage is external state (localStorage) — subscribe instead of
  // sync-setState-in-effect, which also picks up cross-tab writes for free
  const rerunId = useSyncExternalStore(
    subscribeToStorage,
    () => getRerunOf(runId),
    () => null
  )

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

  if (status === 'failed' && !report) {
    return (
      <div className='rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-700 dark:text-rose-400'>
        This run failed before any trial was recorded.{' '}
        {abortReason ? <span className='block pt-1'>Reason: {abortReason}</span> : null}{' '}
        <Link href='/' className='underline underline-offset-4'>Start a new audit</Link>.
      </div>
    )
  }

  if (!report) {
    // While a run is still executing, say so instead of showing anonymous
    // skeletons — the first suta.in live test left this page looking broken.
    if (status === 'loading' || status === 'running' || status === 'queued') {
      return (
        <div className='rounded-lg border border-primary/30 bg-primary/5 px-4 py-4 text-sm'>
          <p className='font-medium'>
            Audit in progress
            {progress ? (
              <span className='text-muted-foreground font-normal'>
                {' '}
                — {progress.done} of {progress.total ?? '?'} shopping missions recorded
              </span>
            ) : null}
            .
          </p>
          <p className='text-muted-foreground mt-1'>
            Results appear here the moment the run reaches a terminal state.{' '}
            <Link href={`/audit/${runId}`} className='underline underline-offset-4'>
              Watch it live →
            </Link>
          </p>
        </div>
      )
    }
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

      {status === 'failed' ? (
        <div className='rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-700 dark:text-rose-400'>
          <strong>This run stopped early — the numbers below come from the {report.trials.total}{' '}
          shopping missions completed before the stop.</strong>{' '}
          {abortReason ? <span>Reason: {abortReason}.</span> : null} Every figure is computed
          only from those completed missions and shows its likely range.
        </div>
      ) : null}

      {/* ---------- headline strip ---------- */}
      <Card>
        <CardContent className='flex flex-col gap-4 py-5'>
          <div className='grid items-center gap-6 md:grid-cols-2 xl:grid-cols-3'>
            <div className='flex min-w-0 items-center gap-4'>
              <ScoreDial score={report.score.value} lo={report.score.ci_low} hi={report.score.ci_high} size={104} />
              <div>
                <div className='text-muted-foreground text-xs font-medium tracking-wide uppercase'>
                  <Term tip='One number for how easily AI shopping agents can find, trust, and buy from your catalog. Higher = more agent-ready.'>
                    AgentReady Score
                  </Term>
                </div>
                <div
                  className='text-muted-foreground mt-1 font-mono text-xs'
                  title={CI_TIP}
                >
                  typical range [{report.score.ci_low.toFixed(1)} – {report.score.ci_high.toFixed(1)}]
                </div>
                <div className='mt-2 flex flex-wrap gap-1.5'>
                  <SourceChip kind='measured' label={`${report.trials.total} simulated shopping missions`} />
                  <StatusChip status={report.status} />
                </div>
              </div>
            </div>

            <div className='min-w-0 break-words'>
              <div className='text-muted-foreground text-xs font-medium tracking-wide uppercase'>
                Revenue at risk / month{' '}
                <Term tip='If AI agents drive the traffic share you pick below, this is the monthly revenue affected when agents cannot complete a purchase on your store.'>
                  @ {(sAgent * 100).toFixed(0)}% agent traffic
                </Term>
              </div>
              {baseRar ? (
                <>
                  <div
                    className='mt-1 text-2xl font-semibold tabular-nums'
                    title={CI_TIP}
                  >
                    {inr(baseRar.value * rarScale)}{' '}
                    <span className='text-muted-foreground font-mono text-sm font-normal'>
                      [{inr(baseRar.ci_low * rarScale)} – {inr(baseRar.ci_high * rarScale)}]
                    </span>
                  </div>
                  <div className='text-muted-foreground mt-1.5 text-xs'>
                    Driven by{' '}
                    <Term tip='The measured share of shopping missions where the AI agent bought nothing — e.g. no listing matched its client’s needs or it couldn’t verify price/availability.'>
                      walk-away rate {pct(report.coverage.f_task.value)}
                    </Term>{' '}
                    <span className='font-mono'>
                      [{pct(report.coverage.f_task.ci_low)} – {pct(report.coverage.f_task.ci_high)}]
                    </span>{' '}
                    <SourceChip kind='measured' /> · traffic share is your assumption{' '}
                    <SourceChip kind='assumed' />
                  </div>
                </>
              ) : null}
            </div>

            <div className='min-w-0 break-words'>
              <div className='text-muted-foreground text-xs font-medium tracking-wide uppercase'>
                Recoverable revenue
              </div>
              {recoverable ? (
                <>
                  <div
                    className='mt-1 text-2xl font-semibold text-emerald-600 tabular-nums dark:text-emerald-400'
                    title={CI_TIP}
                  >
                    {inr(recoverable.value)}/mo{' '}
                    <span className='text-muted-foreground font-mono text-sm font-normal'>
                      [{inr(recoverable.ci_low)} – {inr(recoverable.ci_high)}]
                    </span>
                  </div>
                  <div className='mt-1.5 flex flex-wrap items-center gap-1.5'>
                    <SourceChip kind='verified' label='proven by re-run after fixes' />
                    {rerunId ? (
                      <Link
                        href={`/delta/${rerunId}`}
                        className='text-primary text-xs underline underline-offset-4'
                      >
                        see before → after →
                      </Link>
                    ) : null}
                  </div>
                </>
              ) : (
                <>
                  <div className='text-muted-foreground/60 mt-1 text-2xl font-semibold'>—</div>
                  <div className='text-muted-foreground/70 text-xs'>
                    (appears once fixes are applied and a verification re-run completes)
                  </div>
                </>
              )}
            </div>
          </div>

          <Separator />

          <div className='text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-2 text-xs'>
            {STRIP_CAPTION}
            <span className='ml-auto flex items-center gap-2.5 whitespace-nowrap'>
              <span className='hidden sm:inline'>Agent share of your traffic:</span>
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

      {/* ---------- run details ---------- */}
      <Card>
        <CardHeader>
          <CardTitle>Run details</CardTitle>
        </CardHeader>
        <CardContent className='flex flex-col gap-4'>
          <div className='grid gap-3 sm:grid-cols-3'>
            <StatCard
              k='Shopping missions'
              v={`${report.trials.total}`}
              sub={`${report.trials.parse_ok} returned a usable choice · ${report.trials.forced} were must-pick scenarios`}
            />
            <StatCard k='AI cost' v={usd(report.cost_usd)} sub='provider spend, hard-capped — never silent overspend' />
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
                  <TableHead>AI model</TableHead>
                  <TableHead>
                    <Term tip='Share of this model&rsquo;s answers that could not be used (garbled, off-catalog, or provider errors). These trials are counted honestly, never dropped silently.'>
                      Unusable answers
                    </Term>
                  </TableHead>
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

          <Separator />

          {/* one-click handoff: the whole fix brief goes to the merchant's own AI agent */}
          <CopyFixPromptCard report={report} />
        </CardContent>
      </Card>

      {/* ---------- choice heat table ---------- */}
      <Card>
        <CardHeader>
          <CardTitle>Where agent demand landed</CardTitle>
          <CardDescription>
            How evenly AI shoppers spread their choices across your catalog.{' '}
            <Term tip='A concentration score from 0 to 1: near 0 means demand spreads evenly across products; near 1 means agents pile onto one or two listings and ignore the rest.'>
              Concentration:{' '}
              <Ci v={report.hhi_norm.value} lo={report.hhi_norm.ci_low} hi={report.hhi_norm.ci_high} fmt={num2} />
            </Term>{' '}
            — the higher it is, the more your sales depend on a couple of lucky listings.
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
                          title={CI_TIP}
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
            &ldquo;Invisible&rdquo; = even in the best case, these products would get a smaller
            share of agent choices than an equal split allows (1 in {Math.round(1 / FAIR_SHARE)}).
            {report.partial ? ` Figures computed on the ${report.trials.total} shopping missions completed before this run stopped.` : ''}
          </p>
        </CardContent>
      </Card>

      {/* ---------- invisible strip ---------- */}
      <Card>
        <CardHeader>
          <CardTitle>Products invisible to AI agents</CardTitle>
          <CardDescription>
            These listings get statistically fewer agent choices than an even split would give
            them — even at the optimistic end of the range. An AI shopper picking completely at
            random would out-sell them. Check the Catalog page for what&rsquo;s hiding them from
            agents.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {report.invisible_skus.length === 0 ? (
            <p className='text-sm text-emerald-600 dark:text-emerald-400'>None flagged in this run — every product is reachable by agents.</p>
          ) : (
            <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
              {report.invisible_skus.map(s => (
                <StatCard
                  key={s.sku}
                  k={s.sku}
                  v={
                    <span title={CI_TIP} className='font-mono'>
                      {pct(s.share.value)}{' '}
                      <span className='text-muted-foreground text-sm'>
                        [{pct(s.share.ci_low)} – {pct(s.share.ci_high)}]
                      </span>
                    </span>
                  }
                  sub={<span className='text-rose-600 dark:text-rose-400'>share of agent choices — best case still below fair</span>}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ---------- framing + stability + position ---------- */}
      <Card>
        <CardHeader>
          <CardTitle>Wording changes what agents pick</CardTitle>
          <CardDescription>
            We rewrote each listing&rsquo;s wording — same facts, different phrasing — and measured
            how agent choices moved. Average shift across rewritten listings:{' '}
            <Ci
              v={report.framing.mean_delta.value}
              lo={report.framing.mean_delta.ci_low}
              hi={report.framing.mean_delta.ci_high}
              fmt={pct}
            />
            . A large shift means your sales depend on how things are worded, not just what they
            are.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {movers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Chosen with original wording</TableHead>
                  <TableHead>Chosen with reworded version</TableHead>
                  <TableHead>Shift</TableHead>
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
            <p className='text-muted-foreground text-sm'>No wording-test data reported for this catalog.</p>
          )}
        </CardContent>
      </Card>

      <div className='grid gap-4 lg:grid-cols-2'>
        {/* ---------- stability ---------- */}
        <Card>
          <CardHeader>
            <CardTitle>Do different AI models agree?</CardTitle>
            <CardDescription>
              How closely each pair of AI models ranks your products (1.00 = identical taste, 0 =
              complete disagreement). Average agreement:{' '}
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
              above 0.8 models agree · 0.5–0.8 partial agreement · below 0.5 models disagree — low
              agreement means there is no single &ldquo;safe&rdquo; optimization for agent visibility.
            </p>
          </CardContent>
        </Card>

        {/* ---------- position bias ---------- */}
        <Card>
          <CardHeader>
            <CardTitle>Does listing position decide sales?</CardTitle>
            <CardDescription>
              We shuffled the listing order randomly and compared — if choices follow position,
              the first slots have an unfair advantage regardless of product quality.
            </CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-3'>
            <div className='grid grid-cols-3 gap-2 text-sm'>
              <div>
                <div className='text-muted-foreground text-xs uppercase'>
                  <Term tip='The combined share of agent choices that went to products shown in the first three positions.'>
                    Top-3 capture
                  </Term>
                </div>
                <Ci
                  v={report.position.top3_capture.value}
                  lo={report.position.top3_capture.ci_low}
                  hi={report.position.top3_capture.ci_high}
                  fmt={pct}
                  className='font-medium'
                />
              </div>
              <div>
                <div className='text-muted-foreground text-xs uppercase'>
                  <Term tip='How many times more likely a first-position product is picked compared to pure chance.'>
                    First-slot advantage
                  </Term>
                </div>
                <div className='tabular-nums'>{num1(report.position.lift)}×</div>
              </div>
              <div>
                <div className='text-muted-foreground text-xs uppercase'>
                  <Term tip='Statistical test: values below 0.05 mean the first-place advantage is real, not random luck.'>
                    Is it luck?
                  </Term>
                </div>
                <div className='tabular-nums'>
                  {report.position.p_value < 0.001
                    ? 'No (p < 0.001)'
                    : report.position.p_value < 0.05
                      ? `No (p = ${report.position.p_value.toFixed(2)})`
                      : 'Possibly'}
                </div>
              </div>
            </div>
            <SlotChart perSlot={report.position.per_slot} />
            <p className='text-muted-foreground/70 text-xs'>
              Each bar is one listing slot; dashed line = the fair share that slot would get by
              chance.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ---------- coverage ---------- */}
      <Card>
        <CardHeader>
          <CardTitle>How often agents buy nothing</CardTitle>
          <CardDescription>
            Share of shopping missions that ended with no purchase — the agent found nothing that
            matched its client&rsquo;s need, or couldn&rsquo;t verify it:{' '}
            <Ci
              v={report.coverage.f_task.value}
              lo={report.coverage.f_task.ci_low}
              hi={report.coverage.f_task.ci_high}
              fmt={pct}
              className='text-base font-semibold'
            />{' '}
            <SourceChip kind='measured' /> — this measured walk-away rate is what drives the
            revenue-at-risk estimate.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {report.coverage.nulls_by_persona.length > 0 ? (
            <div className='max-w-md'>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Shopper profile</TableHead>
                    <TableHead>Bought nothing</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[...report.coverage.nulls_by_persona]
                    .sort((a, b) => b.null_rate - a.null_rate)
                    .slice(0, 5)
                    .map(p => (
                      <TableRow key={p.persona_id}>
                        <TableCell className='text-xs'>
                          {personaLabel(p.persona_id)}{' '}
                          <span className='text-muted-foreground font-mono'>({p.persona_id})</span>
                        </TableCell>
                        <TableCell className='tabular-nums'>{pct(p.null_rate)}</TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </CardContent>
      </Card>

    </div>
  )
}

/** storage-event subscription for useSyncExternalStore (cross-tab safe). */
function subscribeToStorage(onChange: () => void): () => void {
  window.addEventListener('storage', onChange)

  return () => window.removeEventListener('storage', onChange)
}

/** One-click handoff: full fix brief → merchant's own AI coding agent. */
function CopyFixPromptCard({ report }: { report: ReportResponse }) {
  const [copied, setCopied] = useState<'idle' | 'ok' | 'fail'>('idle')

  async function onCopy() {
    const ok = await copyText(buildFixPrompt(report))

    setCopied(ok ? 'ok' : 'fail')
    if (ok) setTimeout(() => setCopied('idle'), 2600)
  }

  return (
    <div className='bg-muted/30 flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center'>
      <div className='min-w-0 flex-1'>
        <div className='flex items-center gap-2 text-sm font-medium'>
          <ClipboardCopyIcon className='text-primary size-4 shrink-0' />
          Fix it from here — hand this audit to your own AI agent
        </div>
        <p className='text-muted-foreground mt-1 text-xs leading-relaxed'>
          One click copies a complete fix brief: every measured problem (invisible products,
          weak listings, wording drift) plus step-by-step repair instructions and safety
          constraints. Paste it into {AGENT_TOOLS} and it applies the fixes to your store —
          then re-run this audit to verify the improvement.
        </p>
      </div>
      <div className='shrink-0'>
        <Button
          onClick={onCopy}
          title={`Copies the full fix brief for run ${report.run_id.slice(0, 8)} to your clipboard — nothing is uploaded anywhere.`}
        >
          {copied === 'ok' ? <CheckIcon /> : <ClipboardCopyIcon />}
          {copied === 'ok' ? 'Copied — paste into your agent' : 'Copy Prompt'}
        </Button>
        {copied === 'fail' ? (
          <p className='mt-1 max-w-48 text-right text-xs text-rose-600 dark:text-rose-400'>
            Copy failed — browser blocked clipboard access.
          </p>
        ) : null}
      </div>
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
