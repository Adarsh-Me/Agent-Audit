'use client'

import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'

import { CheckIcon, ChevronRightIcon, XIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Separator } from '@/components/ui/separator'
import { ErrorBox, PanelSkeleton } from '@/components/agentaudit/bits'
import { cn } from '@/lib/utils'
import {
  ApiError,
  buildMirror,
  createAudit,
  generateRemediations,
  listRemediations,
  reviewRemediation,
  type RemediationListResponse,
  type RemediationRow
} from '@/lib/api'
import { rememberRerun } from '@/lib/runs'

function StatusBadge({ status }: { status: RemediationRow['status'] }) {
  const map: Record<string, string> = {
    approved: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    rejected: 'border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400',
    pending: 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400'
  }
  return (
    <Badge variant='outline' className={cn('h-5 text-xs', map[status])}>
      {status}
    </Badge>
  )
}

export default function FixesPage() {
  const params = useParams<{ id: string }>()
  const runId = params.id
  const router = useRouter()

  const [data, setData] = useState<RemediationListResponse | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const [actionErr, setActionErr] = useState<{ code: string; message: string } | null>(null)
  const [generating, setGenerating] = useState(false)
  const [building, setBuilding] = useState(false)
  const [acknowledgedReview, setAcknowledgedReview] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await listRemediations(runId)
      setData(res)
      setError(null)
      // pre-expand the first pending product so reviewers see a diff immediately
      if (res.remediations.length > 0) {
        setExpanded(new Set([res.remediations[0].id]))
      }
    } catch (err) {
      if (err instanceof ApiError) setError({ code: err.code, message: err.message })
      else setError({ code: 'E-UNK', message: 'Failed to load remediation plan.' })
    }
  }, [runId])

  useEffect(() => {
    void load()
  }, [load])

  async function onGenerate() {
    setGenerating(true)
    try {
      await generateRemediations(runId)
      await load()
    } catch (err) {
      if (err instanceof ApiError) setActionErr({ code: err.code, message: err.message })
    } finally {
      setGenerating(false)
    }
  }

  async function onReview(row: RemediationRow, status: 'approved' | 'rejected') {
    setActionErr(null)
    try {
      await reviewRemediation(row.id, status)
      setData(prev =>
        prev
          ? {
              ...prev,
              counts: {
                ...prev.counts,
                [status]: prev.counts[status] + 1,
                pending: prev.counts.pending - 1
              },
              remediations: prev.remediations.map(r =>
                r.id === row.id ? { ...r, status, reviewed_by: 'merchant' } : r
              )
            }
          : prev
      )
    } catch (err) {
      if (err instanceof ApiError) setActionErr({ code: err.code, message: err.message })
    }
  }

  async function onMirrorAndRerun() {
    if (!data) return
    setActionErr(null)
    setBuilding(true)
    try {
      const mirror = await buildMirror(runId) // E401 here if anything still pending
      const audit = await createAudit({
        catalog_source: 'mirror',
        catalog_id: mirror.mirror_catalog_id,
        parent_run_id: runId
      })
      rememberRerun(runId, audit.audit_id)
      router.push(`/audit/${audit.audit_id}`)
    } catch (err) {
      if (err instanceof ApiError) setActionErr({ code: err.code, message: err.message })
      else setActionErr({ code: 'E-UNK', message: 'Mirror/re-run failed.' })
      setBuilding(false)
    }
  }

  if (error) {
    return (
      <ErrorBox code={error.code} message={error.message}>
        <Link href={`/audit/${runId}/results`} className='text-sm underline underline-offset-4'>
          ← Back to results
        </Link>
      </ErrorBox>
    )
  }

  if (!data) return <PanelSkeleton lines={6} />

  const total = data.remediations.length
  const reviewed = data.counts.approved + data.counts.rejected
  const allReviewed = total > 0 && reviewed === total

  if (total === 0 && !generating) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Remediation plan</CardTitle>
          <CardDescription>
            No fixes proposed yet for this run. The generator flags starved-tier and low-legibility
            products and drafts title / description / structured-data rewrites — nothing is applied
            without your approval. For a live-store import, zero flags means every listing scored
            above the legibility threshold — a clean bill; the demo store deliberately contains
            starved listings so the full flow is visible.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={onGenerate} disabled={generating}>
            Generate remediation plan
          </Button>
          {actionErr ? (
            <div className='mt-4'>
              <ErrorBox code={actionErr.code} message={actionErr.message} />
            </div>
          ) : null}
        </CardContent>
      </Card>
    )
  }

  return (
    <div className='flex flex-col gap-4 pb-16'>
      <div className='flex flex-wrap items-baseline gap-3'>
        <h1 className='font-pixel text-2xl font-bold tracking-normal'>
          Remediation plan — {total} product{total === 1 ? '' : 's'},{' '}
          {data.remediations.reduce((n, r) => n + r.fixes.length, 0)} fixes
        </h1>
        <Badge
          variant='outline'
          className={cn(
            'h-5 text-xs',
            allReviewed
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
              : 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400'
          )}
        >
          {allReviewed ? 'ready to mirror' : 'pending review'}
        </Badge>
      </div>

      <p className='text-muted-foreground text-sm'>
        ⓘ LLM proposed · human approves · deterministic layer commits. Nothing touches your live
        catalog — approved edits are written to a mirrored copy that the verification re-run audits.
      </p>

      {actionErr ? <ErrorBox code={actionErr.code} message={actionErr.message} /> : null}

      {generating ? <PanelSkeleton lines={4} /> : null}

      {data.remediations.map(row => {
        const open = expanded.has(row.id)
        return (
          <Card key={row.id} size='sm' className={cn('transition-colors', open && 'border-primary/40')}>
            <div
              role='button'
              tabIndex={0}
              className='hover:bg-muted/40 flex cursor-pointer items-center gap-3 px-4 py-3'
              onClick={() =>
                setExpanded(prev => {
                  const next = new Set(prev)
                  if (next.has(row.id)) next.delete(row.id)
                  else next.add(row.id)
                  return next
                })
              }
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  setExpanded(prev => {
                    const next = new Set(prev)
                    if (next.has(row.id)) next.delete(row.id)
                    else next.add(row.id)
                    return next
                  })
                }
              }}
            >
              <ChevronRightIcon
                className={cn('size-4 shrink-0 transition-transform', open && 'rotate-90')}
              />
              <span className='font-mono text-xs'>{row.sku ?? row.product_id.slice(0, 8)}</span>
              <span className='min-w-0 flex-1 truncate text-sm font-medium'>
                {row.title ?? '(untitled)'}
              </span>
              <StatusBadge status={row.status} />
            </div>

            {open ? (
              <CardContent className='flex flex-col gap-4 pt-0'>
                <Separator />
                {row.fixes.map((fix, i) => (
                  <div key={`${row.id}-${i}`} className='flex flex-col gap-1.5'>
                    <div className='text-muted-foreground font-mono text-xs uppercase'>
                      {fix.field}
                    </div>
                    <div className='grid gap-2 md:grid-cols-2'>
                      <div className='rounded-md border border-rose-500/20 bg-rose-500/5 p-2.5 text-xs'>
                        <div className='text-muted-foreground/70 mb-1 text-[10px] uppercase'>
                          before
                        </div>
                        <div className='line-clamp-4 break-words font-mono'>
                          {fix.before || '(absent)'}
                        </div>
                      </div>
                      <div className='rounded-md border border-emerald-500/20 bg-emerald-500/5 p-2.5 text-xs'>
                        <div className='text-muted-foreground/70 mb-1 text-[10px] uppercase'>
                          after
                        </div>
                        <div className='line-clamp-4 break-words font-mono'>{fix.after}</div>
                      </div>
                    </div>
                    <p className='text-muted-foreground text-xs'>ⓘ {fix.rationale}</p>
                  </div>
                ))}

                {row.status === 'pending' ? (
                  <div className='flex flex-wrap items-center gap-3'>
                    <Button size='sm' onClick={() => onReview(row, 'approved')}>
                      <CheckIcon data-icon='inline-start' />
                      Approve
                    </Button>
                    <Button
                      size='sm'
                      variant='outline'
                      className='text-rose-600 dark:text-rose-400'
                      onClick={() => onReview(row, 'rejected')}
                    >
                      <XIcon data-icon='inline-start' />
                      Reject
                    </Button>
                    <label className='text-muted-foreground flex items-center gap-2 text-xs'>
                      <Checkbox
                        checked={acknowledgedReview}
                        onCheckedChange={v => setAcknowledgedReview(v === true)}
                      />
                      I have reviewed the proposed rewrites
                    </label>
                  </div>
                ) : (
                  <p className='text-muted-foreground text-xs'>
                    reviewed by {row.reviewed_by ?? 'merchant'}
                    {row.applied_at ? ` · applied ${new Date(row.applied_at).toLocaleString()}` : ''}
                  </p>
                )}
              </CardContent>
            ) : null}
          </Card>
        )
      })}

      {/* sticky review summary */}
      <div className='bg-background/95 sticky bottom-4 z-30 rounded-lg border px-4 py-3 shadow-lg backdrop-blur'>
        <div className='flex flex-wrap items-center gap-3'>
          <strong className='text-sm tabular-nums'>
            {reviewed} of {total} reviewed
          </strong>
          <span className='text-muted-foreground/80 text-xs'>
            mirror is built only from approved rows
          </span>
          <span className='ml-auto'>
            <Button
              disabled={!allReviewed || building || !acknowledgedReview}
              title={
                !acknowledgedReview
                  ? 'Tick “I have reviewed the proposed rewrites” first'
                  : !allReviewed
                    ? 'Approve or reject every row first (E401)'
                    : undefined
              }
              onClick={onMirrorAndRerun}
            >
              {building ? 'Building mirror…' : 'Build mirror & re-run →'}
            </Button>
          </span>
        </div>
      </div>
    </div>
  )
}
