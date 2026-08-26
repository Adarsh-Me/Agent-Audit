'use client'

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card'

const PROVEN = [
  'Complete audit matrix executed live, end-to-end, against real imported Shopify catalogs',
  'Measured: walk-away rate (agents buying nothing), demand concentration, position bias with statistical significance tests, wording sensitivity',
  'Every headline figure shows its 95% likely range — computed from 2,000 bootstrap resamples',
  'Failure handling: server-restart recovery, AI-provider circuit breaker, labeled stop reasons — partial runs never render as complete',
  'Razorpay payment-link plumbing with verified webhooks and duplicate protection (test mode)',
  'One-click import from any public Shopify storefront feeds the same audit within minutes — no scraping, no login',
  'Live progress over server-sent events: every mission streams to the dashboard as it lands, with per-model answer rates',
  'AI-provider outages degrade gracefully — throttled or interrupted missions are recorded with labeled reasons and stay fully auditable',
  'Identical re-runs are served from the response cache at $0 marginal cost; only changed catalogs re-bill'
]

export function LimitationsFooter() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className='text-base'>Proven with live data</CardTitle>
        <CardDescription>
          Bounded claims, verbatim from the build state — everything below has
          been demonstrated end-to-end on live data, not mocked.
        </CardDescription>
      </CardHeader>
      <CardContent className='flex flex-col gap-4'>
        <ul className='grid gap-2 md:grid-cols-2'>
          {PROVEN.map(item => (
            <li key={item} className='flex items-start gap-2 text-sm'>
              <span className='mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-400'>✓</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <p className='text-muted-foreground border-t pt-3 text-xs leading-relaxed'>
          Scope: the audit measures the association between listing quality and
          agent choice under the scenario assumptions you set — correlation, not
          causation. Store imports are point-in-time snapshots of the public
          product feed.
        </p>
      </CardContent>
    </Card>
  )
}
