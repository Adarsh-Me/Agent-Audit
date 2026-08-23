'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useCallback, useEffect, useRef, useState } from 'react'

import { ExternalLinkIcon, PlayIcon, ShieldCheckIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card'
import { ErrorBox } from '@/components/agentaudit/bits'
import { cn } from '@/lib/utils'
import {
  ApiError,
  createPaymentLink,
  getCatalog,
  getPaymentStatus,
  type CatalogProduct,
  type PaymentLinkResponse
} from '@/lib/api'
import { inr } from '@/lib/format'

interface ConsoleLine {
  id: number
  text: string
  cls?: 'tool' | 'ok' | 'reason'
}

type PayPhase = 'idle' | 'running' | 'link_ready' | 'captured' | 'error'

const TRUST_NOTE =
  'The agent never saw a Razorpay key. The backend created this link; the agent only received a URL.'
const CAPTURED_BANNER = 'Payment captured — agent-to-ledger loop closed.'

export default function CheckoutPage() {
  const params = useParams<{ runId: string }>()
  const runId = params.runId

  const [lines, setLines] = useState<ConsoleLine[]>([])
  const [phase, setPhase] = useState<PayPhase>('idle')
  const [product, setProduct] = useState<CatalogProduct | null>(null)
  const [link, setLink] = useState<PaymentLinkResponse | null>(null)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const [waitingSince, setWaitingSince] = useState<number | null>(null)
  const [, forceTick] = useState(0)

  const lineIdRef = useRef(0)
  const runningRef = useRef(false)
  const pollRef = useRef<number | null>(null)

  const addLine = useCallback((text: string, cls?: ConsoleLine['cls']) => {
    lineIdRef.current += 1
    setLines(prev => [...prev, { id: lineIdRef.current, text, cls }])
  }, [])

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  // webhook-badge poller: GET /api/payments/{run_id}/status every 1 s until captured
  const startPolling = useCallback(() => {
    if (pollRef.current !== null) return
    setWaitingSince(Date.now())
    pollRef.current = window.setInterval(async () => {
      try {
        const st = await getPaymentStatus(runId)
        if (st.captured) {
          stopPolling()
          setPhase('captured')
        } else if (st.payments[0]?.status === 'failed') {
          stopPolling()
          setError({ code: 'E-PAY', message: 'Payment failed — retry the test payment.' })
        }
      } catch {
        /* keep polling until timeout */
      }
    }, 1000)
  }, [runId, stopPolling])

  useEffect(() => () => stopPolling(), [stopPolling])

  // re-render once a second while waiting (for the late-webhook notice)
  useEffect(() => {
    if (phase !== 'link_ready') return
    const t = window.setInterval(() => forceTick(n => n + 1), 1000)
    return () => window.clearInterval(t)
  }, [phase])

  async function ensureLink(sku: string): Promise<PaymentLinkResponse> {
    if (link) return link
    addLine('step 4  tool: create_payment_link → POST /api/payments/link', 'tool')
    const res = await createPaymentLink(runId, sku)
    addLine(`        → ${res.short_url || '(no url returned)'}  ✓`, 'ok')
    setLink(res)
    setPhase('link_ready')
    startPolling()
    return res
  }

  async function startAgent() {
    if (runningRef.current) return
    runningRef.current = true
    setError(null)
    setLines([])
    setProduct(null)
    setLink(null)
    setPhase('running')

    try {
      // step 1 — real catalog read
      addLine('step 1  tool: list_products', 'tool')
      await sleep(500)
      const catalog = await getCatalog()
      addLine(`        → ${catalog.count} products received`, 'ok')

      // step 2 — scripted Deal-Hunter reasoning
      await sleep(600)
      addLine(
        'step 2  reasoning (P07 · Deal Hunter): "Best value-for-money item…"',
        'reason'
      )
      addLine('        comparing price vs. described specs across catalog…', 'reason')

      // deterministic choice rule: cheapest rich-tier listing with a structured price,
      // else cheapest overall — logged honestly as a scripted stand-in for the live agent
      const candidates = catalog.products.filter(
        p => p.structured_data && Object.keys(p.structured_data).length > 0
      )
      const pool = candidates.length > 0 ? candidates : catalog.products
      const rich = pool.filter(p => p.tier === 'rich')
      const chosen = [...(rich.length > 0 ? rich : pool)].sort(
        (a, b) => a.price_inr - b.price_inr
      )[0]
      if (!chosen) throw new ApiError('E-CAT', 'Catalog has no products to buy.', 0)

      await sleep(600)
      addLine(`step 3  tool: get_product → id: "${chosen.id}"`, 'tool')
      addLine(`        ${chosen.title} — ${inr(chosen.price_inr)} (${chosen.tier})`)
      setProduct(chosen)

      await sleep(500)
      await ensureLink(chosen.id)

      await sleep(400)
      addLine('step 5  hand to human → open the payment page and pay (test mode)')
      runningRef.current = false
    } catch (err) {
      runningRef.current = false
      setPhase('error')
      if (err instanceof ApiError) {
        setError({ code: err.code, message: err.message })
        addLine(`        error ${err.code}: ${err.message}`)
      } else {
        setError({ code: 'E-UNK', message: 'Agent run failed unexpectedly.' })
      }
    }
  }

  function onPay() {
    if (!link || !link.short_url) {
      setError({ code: 'E502', message: 'No payment link available — restart the agent.' })
      return
    }
    window.open(link.short_url, '_blank', 'noopener,noreferrer')
  }

  const waitingLong = waitingSince !== null && Date.now() - waitingSince > 60_000

  return (
    <div className='flex flex-col gap-6'>
      <div className='flex flex-wrap items-baseline gap-3'>
        <h1 className='text-xl font-semibold tracking-tight'>Agent checkout proof</h1>
        <span className='text-muted-foreground text-sm'>
          run <span className='font-mono text-xs'>{runId.slice(0, 8)}</span>
        </span>
      </div>

      <div className='grid gap-4 lg:grid-cols-2'>
        {/* ---------- left: agent console ---------- */}
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>Agent console</CardTitle>
            <CardDescription>
              Scripted P07 &ldquo;Deal Hunter&rdquo; walkthrough: choose a product, create a payment
              link, hand off to a human.
            </CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-4'>
            <div className='bg-muted/40 min-h-48 rounded-lg border p-3 font-mono text-xs leading-relaxed'>
              {lines.length === 0 ? (
                <span className='text-muted-foreground/70'>
                  idle — press “Start agent”
                </span>
              ) : (
                lines.map(l => (
                  <div
                    key={l.id}
                    className={cn(
                      'whitespace-pre-wrap',
                      l.cls === 'tool' && 'text-primary',
                      l.cls === 'ok' && 'text-emerald-600 dark:text-emerald-400',
                      l.cls === 'reason' && 'text-muted-foreground italic'
                    )}
                  >
                    {l.text}
                  </div>
                ))
              )}
            </div>
            <div className='flex flex-wrap gap-2'>
              {phase === 'idle' || phase === 'error' ? (
                <Button onClick={startAgent}>
                  <PlayIcon data-icon='inline-start' />
                  {phase === 'error' ? 'Restart agent' : 'Start agent'}
                </Button>
              ) : null}
              {phase === 'running' ? (
                <Button disabled>agent running…</Button>
              ) : null}
            </div>
            <p className='text-muted-foreground/80 flex items-start gap-2 rounded-md border p-3 text-xs'>
              <ShieldCheckIcon className='mt-0.5 size-3.5 shrink-0' />
              {TRUST_NOTE}
            </p>
          </CardContent>
        </Card>

        {/* ---------- right: payment card ---------- */}
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>Payment</CardTitle>
          </CardHeader>
          <CardContent className='flex flex-col gap-4'>
            {!product && phase !== 'captured' ? (
              <p className='text-muted-foreground text-sm'>
                The agent&rsquo;s chosen product appears here once it picks one.
              </p>
            ) : null}

            {product ? (
              <>
                <div
                  className={cn(
                    'rounded-lg border p-4',
                    phase === 'link_ready' && 'animate-pulse border-primary/50'
                  )}
                >
                  <div className='text-muted-foreground text-xs font-medium tracking-wide uppercase'>
                    Chosen by agent
                  </div>
                  <div className='mt-1 text-base font-semibold'>{product.title}</div>
                  <div className='text-muted-foreground font-mono text-[11px]'>
                    {product.id} · tier: {product.tier}
                  </div>
                  <div className='mt-2 text-2xl font-semibold tabular-nums'>
                    {inr(product.price_inr)}
                  </div>
                </div>

                <div className='flex flex-wrap items-center gap-3'>
                  <Button onClick={onPay} disabled={!link} title={link ? undefined : 'payment link not created yet'}>
                    <ExternalLinkIcon data-icon='inline-start' />
                    Pay {inr(product.price_inr)} (test mode)
                  </Button>
                  {phase === 'running' ? (
                    <Badge variant='outline' className='text-[11px]'>
                      creating link…
                    </Badge>
                  ) : null}
                  {phase === 'link_ready' ? (
                    <Badge
                      variant='outline'
                      className='border-sky-500/30 bg-sky-500/10 text-[11px] text-sky-600 dark:text-sky-400'
                    >
                      awaiting payment — complete the test payment
                    </Badge>
                  ) : null}
                </div>

                {waitingLong && phase !== 'captured' ? (
                  <div className='rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400'>
                    Webhook is late — verifying via API poll…
                  </div>
                ) : null}

                {phase === 'captured' ? (
                  <div className='flex items-start gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400'>
                    <ShieldCheckIcon className='mt-0.5 size-4 shrink-0' />
                    ✓ {CAPTURED_BANNER}
                  </div>
                ) : null}

                <p className='text-muted-foreground/70 text-[11px]'>
                  Target: capture confirmed within ~5 s of payment. Test-mode Razorpay link — no real
                  money moves. Money-action bounds: ₹2,000 cap · SKU whitelist · test-mode-only.
                </p>
              </>
            ) : null}

            {phase === 'captured' && !product ? (
              <div className='rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400'>
                ✓ {CAPTURED_BANNER}
              </div>
            ) : null}

            {error ? (
              <ErrorBox code={error.code} message={error.message}>
                <div className='mt-2 flex gap-2'>
                  <Button variant='outline' size='sm' onClick={startAgent}>
                    Retry link
                  </Button>
                  <Button variant='ghost' size='sm' render={<Link href={`/audit/${runId}/results`} />}>
                    Back to results
                  </Button>
                </div>
              </ErrorBox>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms))
}
