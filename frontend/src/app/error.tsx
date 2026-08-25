'use client'

// Segment-level error boundary — a render/handler crash on any page now
// keeps the app shell and shows the real error instead of swapping the whole
// document for Next's anonymous global-error page (what happened during the
// first suta.in live test: full-page dead end, zero diagnostics).
import { useEffect } from 'react'
import Link from 'next/link'

import { Button } from '@/components/ui/button'

export default function SegmentError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void
}) {
  useEffect(() => {
    console.error('[agentaudit] segment render error:', error)
  }, [error])

  return (
    <div className='flex min-h-[50vh] flex-col items-center justify-center gap-4 px-4 text-center'>
      <h2 className='text-lg font-semibold'>This panel hit a snag</h2>
      <p className='text-muted-foreground max-w-md text-sm leading-relaxed'>
        {error.message || 'An unexpected client error occurred.'}
        {error.digest ? (
          <span className='mt-1 block font-mono text-xs opacity-70'>digest: {error.digest}</span>
        ) : null}
      </p>
      <div className='flex gap-2'>
        <Button size='sm' onClick={reset}>
          Try again
        </Button>
        <Link
          href='/'
          className='inline-flex h-8 items-center rounded-md border px-3 text-sm font-medium hover:bg-muted/50'
        >
          Go home
        </Link>
      </div>
    </div>
  )
}
