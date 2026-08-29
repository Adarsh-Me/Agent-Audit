// Route-level loading boundary — shown by the App Router during any
// server/data fetch for a route segment. Reuses the panel skeleton pattern
// so it matches the in-page loading states (PanelSkeleton) exactly.
import { PanelSkeleton } from '@/components/agentaudit/bits'

export default function Loading() {
  return (
    <div className='mx-auto size-full max-w-360 flex-1 px-4 py-8 sm:px-8'>
      <div className='flex flex-col gap-6'>
        <PanelSkeleton lines={2} className='max-w-2xl' />
        <div className='grid gap-4 md:grid-cols-2'>
          <PanelSkeleton lines={4} />
          <PanelSkeleton lines={4} />
        </div>
        <PanelSkeleton lines={6} />
      </div>
    </div>
  )
}
