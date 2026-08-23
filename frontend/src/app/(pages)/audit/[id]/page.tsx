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
import { rememberRun } from '@/lib/runs'
import { cn } from '@/lib/utils'

const PARTIAL_BANNER =
  'Partial run — cost cap hit. Numbers below are real but incomplete.'
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
  const [total, setTotal] = useState(640)
  const [costUsd, setCostUsd] = useState(0)
  const [etaS, setEtaS] = useState(0)
  const [ticker, setTicker] = useState<SseTrialEvent[]>([])
  const [transport, setTransport] = useState<'sse' | 'polling'>('sse')
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [stalled, setStalled] = useState(false)

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
        setTotal(s.trials_total ?? 640)
        setCostUsd(s.cost_usd)
        setEtaS(s.eta_s ?? 0)
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
          setTotal(s.trials_total ?? 640)
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
          <strong>No progress for {Math.round(STALL_AFTER_MS / 1000)}s — the engine task may have been
          interrupted</strong> (server restart or provider outage). {done} trials are recorded and
          auditable.{' '}
          <Link href={`/audit/${runId}/results`} className='underline underline-offset-4'>
            View the data audited so far →
          </Link>
        </div>
      ) : null}
      {status === 'failed' ? (
        <div className='rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-700 dark:text-rose-400'>
          Run failed — provider hard-fail. No charge beyond completed trials.{' '}
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
            <CardTitle className='font-mono text-base' title='run id (click to copy)'>
              <span
                className='cursor-pointer'
                onClick={() => navigator.clipboard?.writeText(runId).catch(() => {})}
              >
                {runId}
              </span>
            </CardTitle>
            <StatusChip status={status === 'loading' ? 'queued' : status} />
            {(status === 'running' || status === 'queued') && (
              <span className='text-muted-foreground font-mono text-xs tabular-nums'>
                elapsed {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}
              </span>
            )}
            <span className='ml-auto text-xs'>
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
              {done} / {total} trials · {Math.round(pctDone * 100)}%
            </span>
            {etaS > 0 ? (
              <span className='text-muted-foreground font-mono tabular-nums'>ETA ~{Math.round(etaS)}s</span>
            ) : null}
          </div>

          <Separator />

          <div className='grid gap-3 sm:grid-cols-3'>
            <StatCard k='Trials landed' v={done} sub={`of ${total} in the full matrix`} />
            <StatCard k='Spend so far' v={usd(costUsd)} sub='hard cap $30 → partial, never silent' />
            <StatCard
              k='Conditions'
              v='C1 · C2 · C3'
              sub='baseline / shuffled / reframed copy'
            />
          </div>
        </CardContent>
      </Card>

      <div className='grid gap-4 lg:grid-cols-2'>
        {/* ---------- live ticker ---------- */}
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>Live trial ticker</CardTitle>
            <CardDescription>
              Last 6 trials as they land. Amber rows chose &ldquo;nothing fits&rdquo;.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className='bg-muted/40 flex flex-col gap-1 rounded-lg border p-3 font-mono text-xs'>
              {ticker.length === 0 ? (
                <span className='text-muted-foreground/70'>waiting for trials…</span>
              ) : (
                ticker.map((t, i) => (
                  <div
                    key={`${i}-${t.ts ?? i}`}
                    className={cn(
                      'flex flex-wrap items-center gap-x-3 tabular-nums',
                      t.choice === null && 'text-amber-600 dark:text-amber-400'
                    )}
                  >
                    <span className='text-muted-foreground w-24 truncate'>{t.model}</span>
                    <span className='w-10'>{t.persona_id}</span>
                    <span className='text-muted-foreground w-16'>{t.condition}</span>
                    <span>→</span>
                    <span className={cn(t.choice === null && 'italic')}>
                      {t.choice ?? 'null (nothing fits)'}
                    </span>
                    <span className='text-muted-foreground/60 ml-auto'>{t.latency_ms}ms</span>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* ---------- explainer ---------- */}
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>What&rsquo;s happening</CardTitle>
            <CardDescription>The controlled experiment behind every number.</CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-3 text-sm'>
            <p>
              <strong>C1 baseline</strong>{' '}
              <span className='text-muted-foreground'>
                — catalog presented in its normal order, 3 replicate seeds.
              </span>
            </p>
            <p>
              <strong>C2 shuffled</strong>{' '}
              <span className='text-muted-foreground'>
                — randomized listing order isolates position bias.
              </span>
            </p>
            <p>
              <strong>C3 rewritten copy</strong>{' '}
              <span className='text-muted-foreground'>
                — information-equivalent rewrites isolate framing bias.
              </span>
            </p>
            <p className='text-muted-foreground'>
              1 in 3 trials may return &ldquo;nothing fits&rdquo; — that&rsquo;s the coverage
              metric.
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
