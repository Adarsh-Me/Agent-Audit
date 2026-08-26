'use client'

import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useCallback, useEffect, useRef, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card'
import { Progress, ProgressTrack, ProgressIndicator } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { ErrorBox, StatCard, StatusChip } from '@/components/agentaudit/bits'
import {
  ApiError,
  getAudit,
  streamUrl,
  type AuditStatusResponse,
  type SseTrialEvent
} from '@/lib/api'
import { usd } from '@/lib/format'
import { conditionShort, personaLabel } from '@/lib/glossary'
import { rememberRun } from '@/lib/runs'
import { cn } from '@/lib/utils'

const PARTIAL_BANNER =
  'Partial run — the spend cap was reached. Numbers below are real but incomplete.'

/** "162s" → "2m 42s" — merchants shouldn't parse raw seconds. */
function fmtEta(totalSeconds: number): string {
  if (totalSeconds >= 3600) return `~${Math.floor(totalSeconds / 3600)}h ${Math.round((totalSeconds % 3600) / 60)}m`
  if (totalSeconds >= 60) return `~${Math.floor(totalSeconds / 60)}m ${Math.round(totalSeconds % 60)}s`
  return `~${Math.round(totalSeconds)}s`
}
const MAX_SSE_FAILURES = 3
const POLL_MS = 3000
/** No recorded progress for this long while "running" ⇒ the engine task is
 * gone (server restart) or wedged — surface it instead of spinning forever. */
const STALL_AFTER_MS = 120_000

export default function ProgressPage() {
  const params = useParams<{ id: string }>()
  const runId = params.id
  const router = useRouter()

  const [status, setStatus] = useState<AuditStatusResponse['status'] | 'loading'>('loading')
  const [done, setDone] = useState(0)
  const [total, setTotal] = useState(220)
  const [costUsd, setCostUsd] = useState(0)
  const [etaS, setEtaS] = useState(0)
  const [ticker, setTicker] = useState<SseTrialEvent[]>([])
  const [transport, setTransport] = useState<'sse' | 'polling'>('sse')
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [stalled, setStalled] = useState(false)
  const [meta, setMeta] = useState<{ merchant: string | null; startedAt: string | null; reason: string | null }>(
    { merchant: null, startedAt: null, reason: null }
  )

  const startedAtRef = useRef<number>(Date.now())
  const navigatedRef = useRef(false)
  const lastProgressRef = useRef<number>(Date.now())

  const finishToResults = useCallback(
    (finalStatus: AuditStatusResponse['status']) => {
      if (navigatedRef.current) return
      setStatus(finalStatus)
      if (finalStatus === 'done' || finalStatus === 'partial') {
        navigatedRef.current = true
        // APPFLOW F2: auto-redirect after 1.5 s
        window.setTimeout(() => router.push(`/audit/${runId}/results`), 1500)
      }
    },
    [router, runId]
  )

  // Initial status load
  useEffect(() => {
    let alive = true
    getAudit(runId)
      .then(s => {
        if (!alive) return
        rememberRun(s.run_id)
        setDone(s.trials_done)
        setTotal(s.trials_total ?? 220)
        setCostUsd(s.cost_usd)
        setEtaS(s.eta_s ?? 0)
        setMeta({ merchant: s.merchant ?? null, startedAt: s.started_at ?? null, reason: s.reason ?? null })
        if (s.status === 'queued' || s.status === 'running') {
          setStatus(s.status)
          startedAtRef.current = Date.now()
        } else {
          finishToResults(s.status)
        }
      })
      .catch((err: unknown) => {
        if (!alive) return
        setStatus('failed')
        if (err instanceof ApiError) setError({ code: err.code, message: err.message })
        else setError({ code: 'E-UNK', message: 'Failed to load run.' })
      })
    return () => {
      alive = false
    }
  }, [runId, finishToResults])

  // SSE with polling fallback
  useEffect(() => {
    if (status !== 'queued' && status !== 'running') return
    let es: EventSource | null = null
    let pollTimer: number | null = null
    let failures = 0
    let closed = false

    const startPolling = () => {
      if (closed || pollTimer !== null) return
      setTransport('polling')
      const tick = async () => {
        try {
          const s = await getAudit(runId)
          setDone(prev => {
            if (s.trials_done > prev) {
              lastProgressRef.current = Date.now()
              setStalled(false)
            }
            return s.trials_done
          })
          setTotal(s.trials_total ?? 220)
          setCostUsd(s.cost_usd)
          setEtaS(s.eta_s ?? 0)
          if (s.status !== 'running' && s.status !== 'queued') {
            closed = true
            finishToResults(s.status)
            return
          }
        } catch {
          /* keep polling */
        }
        pollTimer = window.setTimeout(tick, POLL_MS)
      }
      void tick()
    }

    try {
      es = new EventSource(streamUrl(runId))

      es.addEventListener('progress', ev => {
        try {
          const d = JSON.parse((ev as MessageEvent).data) as { done: number; total: number; cost_usd: number }
          setDone(d.done)
          setTotal(d.total)
          setCostUsd(d.cost_usd)
          setEtaS(Math.max(0, d.total - d.done) * 0.35)
          lastProgressRef.current = Date.now()
          setStalled(false)
        } catch {
          /* malformed event ignored */
        }
      })

      es.addEventListener('trial', ev => {
        try {
          const t = JSON.parse((ev as MessageEvent).data) as SseTrialEvent
          setTicker(prev => [...prev.slice(-5), t])
        } catch {
          /* malformed event ignored */
        }
      })

      es.addEventListener('complete', ev => {
        try {
          const d = JSON.parse((ev as MessageEvent).data) as { status: AuditStatusResponse['status'] }
          es?.close()
          closed = true
          finishToResults(d.status)
        } catch {
          /* fall through to polling */
        }
      })

      // heartbeat comments arrive without a named event — EventSource keeps the
      // connection alive automatically; nothing to handle explicitly.
      es.onerror = () => {
        failures += 1
        if (failures >= MAX_SSE_FAILURES && !closed) {
          es?.close()
          startPolling()
        }
      }
    } catch {
      startPolling()
    }

    return () => {
      closed = true
      es?.close()
      if (pollTimer !== null) window.clearTimeout(pollTimer)
    }
  }, [runId, status, finishToResults])

  // elapsed timer + stall watcher
  useEffect(() => {
    if (status !== 'running' && status !== 'queued') return
    const t = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000))
      if (Date.now() - lastProgressRef.current > STALL_AFTER_MS) setStalled(true)
    }, 1000)
    return () => window.clearInterval(t)
  }, [status])

  if (error) {
    return (
      <ErrorBox code={error.code} message={error.message}>
        <Link href='/' className='text-sm underline underline-offset-4'>
          ← Back to setup
        </Link>
      </ErrorBox>
    )
  }

  const pctDone = total > 0 ? Math.min(1, done / total) : 0

  return (
    <div className='flex flex-col gap-6'>
      {status === 'partial' ? (
        <div className='rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-400'>
          {PARTIAL_BANNER}
        </div>
      ) : null}
      {stalled && (status === 'running' || status === 'queued') ? (
        <div className='rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-400'>
          <strong>No progress for {Math.round(STALL_AFTER_MS / 1000)}s — the engine may have been
          interrupted</strong> (server restart or AI-provider outage). {done} shopping missions are
          recorded and auditable.{' '}
          <Link href={`/audit/${runId}/results`} className='underline underline-offset-4'>
            View the data audited so far →
          </Link>
        </div>
      ) : null}
      {status === 'failed' ? (
        <div className='rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-700 dark:text-rose-400'>
          <strong>This run stopped early.</strong>{' '}
          {meta.reason ?? 'The AI provider reported an unrecoverable error.'} You are only charged
          for shopping missions that already completed.{' '}
          <Link href='/' className='underline underline-offset-4'>
            Start a new audit
          </Link>{' '}
          to retry.
        </div>
      ) : null}

      {/* ---------- progress panel ---------- */}
      <Card>
        <CardHeader>
          <div className='flex flex-wrap items-center gap-3'>
            <div className='min-w-0'>
              <CardTitle className='font-pixel text-xl font-bold tracking-normal' title='the store this audit ran against'>
                {meta.merchant ?? 'Audit run'}
              </CardTitle>
              <div className='mt-1 flex flex-wrap items-center gap-2'>
                <StatusChip status={status === 'loading' ? 'queued' : status} />
                <span
                  className='text-muted-foreground cursor-pointer font-mono text-[11px]'
                  title='run id (click to copy)'
                  onClick={() => navigator.clipboard?.writeText(runId).catch(() => {})}
                >
                  {runId.slice(0, 8)}
                </span>
                {(status === 'running' || status === 'queued') && (
                  <span className='text-muted-foreground font-mono text-xs tabular-nums'>
                    elapsed {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}
                  </span>
                )}
              </div>
            </div>
            <span className='ml-auto text-right text-xs'>
              {meta.startedAt ? (
                <span className='text-muted-foreground block font-mono text-[11px] tabular-nums'>
                  {new Date(meta.startedAt).toLocaleString('en-IN', {
                    day: '2-digit',
                    month: 'short',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </span>
              ) : null}
              {transport === 'polling' ? (
                <Badge variant='outline' className='border-amber-500/40 text-amber-600 dark:text-amber-400'>
                  reconnecting… (polling every 3s)
                </Badge>
              ) : (
                <span className='text-muted-foreground'>live stream</span>
              )}
            </span>
          </div>
        </CardHeader>
        <CardContent className='flex flex-col gap-4'>
          <Progress value={pctDone * 100}>
            <ProgressTrack className='h-2.5'>
              <ProgressIndicator style={{ width: `${pctDone * 100}%` }} />
            </ProgressTrack>
          </Progress>
          <div className='flex justify-between text-xs'>
            <span className='font-mono tabular-nums'>
              {done} of {total} shopping missions · {Math.round(pctDone * 100)}%
            </span>
            {etaS > 0 ? (
              <span className='text-muted-foreground font-mono tabular-nums'>
                {fmtEta(etaS)} remaining
              </span>
            ) : null}
          </div>

          <Separator />

          <div className='grid gap-3 sm:grid-cols-3'>
            <StatCard k='Missions completed' v={done} sub={`of ${total} in the full experiment`} />
            <StatCard k='AI spend so far' v={usd(costUsd)} sub='hard-capped at $30 — stops honestly, never overspends' />
            <StatCard
              k='Three ways listings are shown'
              v='Order · Shuffle · Reworded'
              sub='each isolates a different visibility problem'
            />
          </div>
        </CardContent>
      </Card>

      <div className='grid gap-4 lg:grid-cols-2'>
        {/* ---------- live ticker ---------- */}
        <Card>
          <CardHeader>
            <CardTitle>Live shopper feed</CardTitle>
            <CardDescription>
              Each row is one simulated shopper finishing a mission. Amber rows said
              &ldquo;nothing fits&rdquo;.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className='bg-muted/40 flex flex-col gap-1 rounded-lg border p-3 font-mono text-xs'>
              {ticker.length === 0 ? (
                <span className='text-muted-foreground/70'>waiting for shoppers…</span>
              ) : (
                ticker.map((t, i) => (
                  <div
                    key={`${i}-${t.ts ?? i}`}
                    className={cn(
                      'flex flex-wrap items-center gap-x-3 tabular-nums',
                      t.choice === null && 'text-amber-600 dark:text-amber-400'
                    )}
                  >
                    <span className='text-muted-foreground w-28 truncate' title={t.model}>
                      {t.model}
                    </span>
                    <span className='w-32 truncate' title={`shopper type ${t.persona_id}`}>
                      {personaLabel(t.persona_id)}
                    </span>
                    <span className='text-muted-foreground w-28 truncate' title={t.condition}>
                      {conditionShort(t.condition)}
                    </span>
                    <span>→</span>
                    <span className={cn('truncate', t.choice === null && 'italic')}>
                      {t.choice ?? 'bought nothing'}
                    </span>
                    <span
                      className='text-muted-foreground/60 ml-auto'
                      title='how long the AI took to decide'
                    >
                      {(t.latency_ms / 1000).toFixed(1)}s
                    </span>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* ---------- explainer ---------- */}
        <Card>
          <CardHeader>
            <CardTitle>What&rsquo;s happening</CardTitle>
            <CardDescription>The controlled experiment behind every number.</CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-3 text-sm'>
            <p>
              <strong>Normal order</strong>{' '}
              <span className='text-muted-foreground'>
                — your catalog exactly as it appears today, shown three times for reliability{' '}
                <span className='font-mono'>(C1)</span>.
              </span>
            </p>
            <p>
              <strong>Shuffled order</strong>{' '}
              <span className='text-muted-foreground'>
                — same catalog, random order. Reveals whether listing position decides what agents
                buy <span className='font-mono'>(C2)</span>.
              </span>
            </p>
            <p>
              <strong>Reworded copy</strong>{' '}
              <span className='text-muted-foreground'>
                — same facts, different wording. Reveals whether phrasing steers agent choices{' '}
                <span className='font-mono'>(C3)</span>.
              </span>
            </p>
            <p className='text-muted-foreground'>
              Some shoppers are allowed to say &ldquo;nothing fits&rdquo; — how often that happens
              is your walk-away rate: the share of AI customers who give up on your store.
            </p>
          </CardContent>
        </Card>
      </div>

      {navigatedRef.current && (status === 'done' || status === 'partial') ? (
        <p className='text-center text-sm'>
          Redirecting…{' '}
          <Link href={`/audit/${runId}/results`} className='text-primary underline underline-offset-4'>
            View results now →
          </Link>
        </p>
      ) : null}
    </div>
  )
}
