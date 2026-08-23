'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'

import { ArrowRightIcon, FlaskConicalIcon, UploadIcon } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import {
  ApiError,
  createAudit,
  uploadCatalog,
  type UploadInvalidRow,
  type UploadResponse
} from '@/lib/api'
import { getLastRun, rememberRun } from '@/lib/runs'
import { ErrorBox } from '@/components/agentaudit/bits'

type Phase = 'idle' | 'uploading' | 'uploaded' | 'starting'

export default function LandingPage() {
  const router = useRouter()
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const [upload, setUpload] = useState<UploadResponse | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [lastRun, setLastRun] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    setLastRun(getLastRun())
  }, [])

  function startDemo() {
    setPhase('starting')
    setError(null)
    createAudit({ catalog_source: 'demo' })
      .then(res => {
        rememberRun(res.audit_id)
        router.push(`/audit/${res.audit_id}`)
      })
      .catch((err: unknown) => {
        setPhase('idle')
        if (err instanceof ApiError && err.code === 'E602') {
          setError({ code: err.code, message: 'Too many requests — retry in 60s' })
        } else if (err instanceof ApiError) {
          setError({ code: err.code, message: err.message })
        } else {
          setError({ code: 'E-UNK', message: 'Something went wrong starting the audit.' })
        }
      })
  }

  function sendFile(file: File) {
    const name = file.name.toLowerCase()
    if (!name.endsWith('.json') && !name.endsWith('.csv')) {
      setError({ code: 'E102', message: 'Only .json or .csv catalogs are accepted.' })
      return
    }
    setPhase('uploading')
    setError(null)
    uploadCatalog(file)
      .then(res => {
        setUpload(res)
        setPhase('uploaded')
      })
      .catch((err: unknown) => {
        setPhase('idle')
        if (err instanceof ApiError) setError({ code: err.code, message: err.message })
        else setError({ code: 'E-UNK', message: 'Upload failed.' })
      })
  }

  function startFromUpload() {
    if (!upload) return
    setPhase('starting')
    createAudit({ catalog_source: 'upload', catalog_id: upload.catalog_id })
      .then(res => {
        rememberRun(res.audit_id)
        router.push(`/audit/${res.audit_id}`)
      })
      .catch((err: unknown) => {
        setPhase('idle')
        if (err instanceof ApiError) setError({ code: err.code, message: err.message })
      })
  }

  return (
    <div className='flex flex-col gap-8'>
      {/* ---------- hero ---------- */}
      <section className='rounded-xl border bg-gradient-to-b from-primary/10 via-primary/5 to-transparent px-8 py-12'>
        <Badge variant='outline' className='border-primary/30 bg-primary/10 mb-6 h-6 px-2.5 text-xs text-[oklch(0.78_0.12_258)]'>
          <FlaskConicalIcon data-icon='inline-start' />
          640 randomized controlled trials · real LLM agents
        </Badge>
        <h1 className='max-w-3xl text-3xl leading-tight font-semibold tracking-tight text-balance sm:text-4xl'>
          Can AI shopping agents actually buy from you?
        </h1>
        <p className='text-muted-foreground mt-5 max-w-2xl text-base leading-relaxed text-pretty'>
          AgentAudit runs 640 controlled agent trials across your catalog and measures whether AI
          shoppers can see your products, choose them fairly, and carry a purchase through to
          payment.
        </p>
        <p className='text-muted-foreground mt-3 max-w-2xl text-sm leading-relaxed'>
          Merchants have SEO for Google&rsquo;s crawler. This is the equivalent check for the agents
          now choosing products on your customers&rsquo; behalf.
        </p>
        <div className='mt-8 flex flex-wrap items-center gap-4'>
          <Button size='lg' onClick={startDemo} disabled={phase === 'starting'}>
            {phase === 'starting' ? 'Queuing…' : 'Run the demo audit'}
            <ArrowRightIcon data-icon='inline-end' />
          </Button>
          <span className='text-muted-foreground font-mono text-xs'>
            ~2–15 min · $0 on pinned free models · hard cap $30/run
          </span>
        </div>
        {lastRun ? (
          <p className='text-muted-foreground mt-5 text-sm'>
            Resume last run{' '}
            <Link
              href={`/audit/${lastRun}/results`}
              className='text-primary font-mono text-xs underline underline-offset-4 hover:underline'
            >
              {lastRun.slice(0, 8)} →
            </Link>
          </p>
        ) : null}
      </section>

      {error ? (
        <ErrorBox code={error.code} message={error.message}>
          <Button variant='outline' size='sm' className='mt-2' onClick={startDemo}>
            Try again
          </Button>
        </ErrorBox>
      ) : null}

      {/* ---------- source cards ---------- */}
      <div className='grid gap-4 md:grid-cols-2'>
        <Card className='border-primary/40 transition-colors'>
          <CardHeader>
            <div className='flex items-center gap-2'>
              <CardTitle>Demo Store</CardTitle>
              <Badge className='h-5 text-xs'>RECOMMENDED</Badge>
            </div>
            <CardDescription className='leading-relaxed'>
              40 products · 4 categories · controlled data-quality tiers (rich / medium / starved).
              The fastest way to see every screen with real measured numbers.
            </CardDescription>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Upload catalog</CardTitle>
            <CardDescription className='leading-relaxed'>
              5–500 rows, JSON or CSV, ≤5 MB — per-row validation errors are shown before anything
              runs.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {phase === 'uploaded' && upload ? (
              <div className='flex flex-col gap-3'>
                <p className='text-sm text-emerald-600 dark:text-emerald-400'>
                  {upload.valid} of {upload.valid + upload.invalid.length} rows valid — continue with
                  valid rows?
                </p>
                {upload.invalid.length > 0 ? (
                  <ul className='text-muted-foreground max-h-32 space-y-1 overflow-auto pl-4 text-xs'>
                    {upload.invalid.slice(0, 8).map((r: UploadInvalidRow) => (
                      <li key={`${r.row}-${r.code}`} className='font-mono'>
                        Row {r.row}: {r.code} — {r.message}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <div className='flex gap-2'>
                  <Button size='sm' onClick={startFromUpload}>
                    Audit uploaded catalog
                    <ArrowRightIcon data-icon='inline-end' />
                  </Button>
                  <Button
                    variant='outline'
                    size='sm'
                    onClick={() => {
                      setUpload(null)
                      setPhase('idle')
                    }}
                  >
                    Pick another file
                  </Button>
                </div>
              </div>
            ) : (
              <div
                role='button'
                tabIndex={0}
                className={cn(
                  'text-muted-foreground hover:border-primary/50 hover:bg-muted/50 flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed py-10 text-sm transition-colors',
                  dragOver && 'border-primary bg-primary/5'
                )}
                onClick={() => fileInput.current?.click()}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') fileInput.current?.click()
                }}
                onDragOver={e => {
                  e.preventDefault()
                  setDragOver(true)
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={e => {
                  e.preventDefault()
                  setDragOver(false)
                  const f = e.dataTransfer.files?.[0]
                  if (f) sendFile(f)
                }}
              >
                <UploadIcon className='size-5 opacity-60' />
                {phase === 'uploading' ? (
                  'Validating rows…'
                ) : (
                  <>
                    Drag &amp; drop a <code className='font-mono text-xs'>.json</code> or{' '}
                    <code className='font-mono text-xs'>.csv</code> catalog here
                    <span className='text-xs opacity-70'>
                      click to browse · nothing runs until you approve
                    </span>
                  </>
                )}
              </div>
            )}
            <Input
              ref={fileInput}
              type='file'
              accept='.json,.csv'
              className='hidden'
              onChange={e => {
                const f = e.target.files?.[0]
                if (f) sendFile(f)
                e.target.value = ''
              }}
            />
          </CardContent>
        </Card>
      </div>

      {/* ---------- honesty strip ---------- */}
      <Alert>
        <AlertTitle>What this tool does not do</AlertTitle>
        <AlertDescription>
          No scraping of live storefronts and no access to your production site — audits run against
          a catalog snapshot you provide (or the demo store). Numbers come only from recorded trials
          in this run; nothing is estimated client-side. Every headline figure carries its
          confidence interval.
        </AlertDescription>
      </Alert>
    </div>
  )
}
