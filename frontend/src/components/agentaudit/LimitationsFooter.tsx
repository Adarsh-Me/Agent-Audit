'use client'

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card'

const PROVEN = [
  'Full 640-trial audit matrix executed live, end-to-end, against real imported Shopify catalogs',
  'Measured: task-failure rate (F_task), demand concentration (HHI), position bias with permutation tests, framing sensitivity',
  'Every headline figure carries its 95% confidence interval — bootstrap B = 2,000',
  'Failure handling: server-restart reaper, provider circuit breaker, labeled abort reasons — partial runs never render as complete',
  'Razorpay payment-link plumbing with HMAC webhooks and idempotency keys (test mode)'
]

const PENDING = [
  'Multi-model results await OpenRouter credits — recent runs are effectively single-model (ox-alpha); free-tier peers were rate-limited to zero parsed trials',
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
