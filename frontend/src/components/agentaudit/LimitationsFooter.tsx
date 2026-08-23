'use client'

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card'

const PROVEN = [
  'Full 640-mission audit executed live, end-to-end, against real imported Shopify catalogs',
  'Measured: walk-away rate (agents buying nothing), demand concentration, position bias with statistical significance tests, wording sensitivity',
  'Every headline figure shows its 95% likely range — computed from 2,000 bootstrap resamples',
  'Failure handling: server-restart recovery, AI-provider circuit breaker, labeled stop reasons — partial runs never render as complete',
  'Razorpay payment-link plumbing with verified webhooks and duplicate protection (test mode)'
]

const PENDING = [
  'Multi-model results await OpenRouter credits — recent runs are effectively single-model; free-tier peer models were rate-limited to zero usable answers',
  'A live captured payment on a deployed URL awaits Razorpay test keys (local walkthrough: Docs/RAZORPAY_SETUP.md)',
  'Store imports are point-in-time snapshots of the public product feed — no HTML scraping, no live-storefront reads',
  'Correlation, not causation: the audit measures association between listing quality and agent choice under scenario assumptions you set'
]

export function LimitationsFooter() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className='text-base'>Proven vs pending</CardTitle>
        <CardDescription>
          Bounded claims, verbatim from the build state — what this system has
          actually demonstrated, and what it has not (yet).
        </CardDescription>
      </CardHeader>
      <CardContent className='grid gap-6 md:grid-cols-2'>
        <div>
          <p className='mb-2 font-mono text-[11px] tracking-wide text-emerald-600 uppercase dark:text-emerald-400'>
            Proven with live data
          </p>
          <ul className='space-y-2'>
            {PROVEN.map(item => (
              <li key={item} className='flex items-start gap-2 text-sm'>
                <span className='mt-0.5 text-emerald-600 dark:text-emerald-400'>✓</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className='text-rose-600 dark:text-rose-400 mb-2 font-mono text-[11px] tracking-wide uppercase'>
            Pending / bounded
          </p>
          <ul className='space-y-2'>
            {PENDING.map(item => (
              <li key={item} className='flex items-start gap-2 text-sm'>
                <span className='mt-0.5 text-rose-600 dark:text-rose-400'>✗</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  )
}
