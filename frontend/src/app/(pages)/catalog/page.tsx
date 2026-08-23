'use client'

import { Fragment, useEffect, useMemo, useState } from 'react'
import { ChevronDown } from 'lucide-react'

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table'
import { personaLabel } from '@/lib/glossary'
import { ErrorBox, PanelSkeleton, StatCard, TierChip } from '@/components/agentaudit/bits'
import {
  ApiError,
  getCatalog,
  getEvidence,
  type CatalogResponse,
  type EvidenceResponse
} from '@/lib/api'
import { inr } from '@/lib/format'
import { getLastRun } from '@/lib/runs'

interface CheckItem {
  label: string
  ok: boolean
  fix?: string
}

/** Legibility checklist per impl-plan §3.4, fix order: JSON-LD → price → title → description → availability */
function checklistFor(p: CatalogResponse['products'][number]): CheckItem[] {
  const sd = (p.structured_data ?? {}) as Record<string, unknown>
  const fields = Array.isArray(sd.fields_present)
    ? (sd.fields_present as string[]).map(f => String(f).toLowerCase())
    : []
  return [
    {
      label: 'JSON-LD Product schema',
      ok: sd.jsonld_present === true,
      fix: 'Add JSON-LD Product schema so parsers can read the listing'
    },
    {
      label: 'Machine-readable price',
      ok: fields.includes('price') || sd.price_fresh === true,
      fix: 'Expose the price in structured data — agents skip unverifiable prices'
    },
    { label: 'Descriptive title', ok: p.title.trim().length > 8 },
    {
      label: 'Substantive description',
      ok: (p.description ?? '').trim().length > 60,
      fix: 'Expand the description — thin copy loses tie-breaker comparisons'
    },
    {
      label: 'Availability stated',
      ok: fields.includes('availability'),
      fix: 'Declare stock status (InStock / OutOfStock) in the feed'
    }
  ]
}

function Quote({ q }: { q: { model: string; persona_id: string; text: string } }) {
  return (
    <blockquote className='border-l-2 border-primary/40 pl-3'>
      <p className='text-sm italic'>&ldquo;{q.text}&rdquo;</p>
      <footer className='text-muted-foreground mt-1 font-mono text-[11px]'>
        {q.model} · {personaLabel(q.persona_id)}
      </footer>
    </blockquote>
  )
}

export default function CatalogPage() {
  const [data, setData] = useState<CatalogResponse | null>(null)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const [query, setQuery] = useState('')
  const [tier, setTier] = useState<string>('all')
  const [openSku, setOpenSku] = useState<string | null>(null)
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null)

  useEffect(() => {
    let alive = true
    getCatalog()
      .then(res => {
        if (!alive) return
        setData(res)
      })
      .catch((err: unknown) => {
        if (!alive) return
        if (err instanceof ApiError) setError({ code: err.code, message: err.message })
        else setError({ code: 'E-UNK', message: 'Failed to load catalog.' })
      })

    // Agent Evidence binds to the most recent run — absent silently until one exists
    const runId = getLastRun()
    if (runId) {
      getEvidence(runId)
        .then(res => {
          if (!alive) return
          setEvidence(res)
        })
        .catch(() => {
          /* no evidence for that run — panel degrades to the checklist only */
        })
    }
    return () => {
      alive = false
    }
  }, [])

  const filtered = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    return data.products.filter(p => {
      if (tier !== 'all' && p.tier !== tier) return false
      if (!q) return true
      return (
        p.title.toLowerCase().includes(q) ||
        p.id.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q)
      )
    })
  }, [data, query, tier])

  const evidenceBySku = useMemo(
    () => new Map((evidence?.products ?? []).map(e => [e.sku, e])),
    [evidence]
  )

  if (error) return <ErrorBox code={error.code} message={error.message} />
  if (!data) return <PanelSkeleton lines={6} />

  const tiers = Array.from(new Set(data.products.map(p => p.tier)))
  const withStructured = data.products.filter(p => p.structured_data && Object.keys(p.structured_data).length > 0).length

  return (
    <div className='flex flex-col gap-6'>
      <div>
        <h1 className='font-pixel text-2xl font-bold tracking-normal'>Catalog</h1>
        <p className='text-muted-foreground mt-1 text-sm'>
          What the agents actually see — {data.count} listings in the audited catalog
          {data.source === 'demo' ? ' (demo store)' : ''}. Click any row for its
          legibility checklist and verbatim agent reasoning.
        </p>
      </div>

      <div className='grid gap-3 sm:grid-cols-4'>
        <StatCard k='Products' v={data.count} />
        <StatCard k='Tiers' v={tiers.length} sub={tiers.join(' · ')} />
        <StatCard k='Structured data' v={`${withStructured}/${data.count}`} sub='listings with JSON-LD-style fields' />
        <StatCard
          k='Price range'
          v={
            <span className='font-mono text-base'>
              {inr(Math.min(...data.products.map(p => p.price_inr)))}–
              {inr(Math.max(...data.products.map(p => p.price_inr)))}
            </span>
          }
        />
      </div>

      <Card>
        <CardHeader>
          <div className='flex flex-wrap items-center gap-3'>
            <CardTitle>Products</CardTitle>
            <div className='ml-auto flex flex-wrap items-center gap-2'>
              <Input
                placeholder='Search title, sku, description…'
                className='h-8 w-64 max-w-full'
                value={query}
                onChange={e => setQuery(e.target.value)}
              />
              <Select value={tier} onValueChange={v => setTier(v ?? 'all')}>
                <SelectTrigger className='h-8 w-32'>
                  <SelectValue placeholder='Tier' />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value='all'>All tiers</SelectItem>
                  {tiers.map(t => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <CardDescription>
            {filtered.length} of {data.count} listings shown.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className='w-8' aria-label='Expand' />
                <TableHead>SKU</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Structured data</TableHead>
                <TableHead className='hidden md:table-cell'>Description</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map(p => {
                const checks = checklistFor(p)
                const failed = checks.filter(c => !c.ok)
                const ev = evidenceBySku.get(p.id)
                const open = openSku === p.id
                return (
                  <Fragment key={p.id}>
                    <TableRow
                      className='cursor-pointer'
                      onClick={() => setOpenSku(open ? null : p.id)}
                    >
                      <TableCell>
                        <ChevronDown
                          className={`size-4 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`}
                        />
                      </TableCell>
                      <TableCell className='font-mono text-xs'>{p.id}</TableCell>
                      <TableCell className='max-w-44 truncate text-sm font-medium'>{p.title}</TableCell>
                      <TableCell className='font-mono text-xs tabular-nums'>{inr(p.price_inr)}</TableCell>
                      <TableCell>
                        <TierChip tier={p.tier} />
                      </TableCell>
                      <TableCell className='text-xs'>
                        {p.structured_data && Object.keys(p.structured_data).length > 0 ? (
                          <span className='text-emerald-600 dark:text-emerald-400'>✓ present</span>
                        ) : (
                          <span className='text-muted-foreground'>absent</span>
                        )}
                      </TableCell>
                      <TableCell className='text-muted-foreground hidden max-w-72 truncate text-xs md:table-cell'>
                        {p.description}
                      </TableCell>
                    </TableRow>
                    {open && (
                      <TableRow>
                        <TableCell colSpan={7} className='bg-muted/30 p-0'>
                          <div className='grid gap-6 p-4 md:grid-cols-2'>
                            <div>
                              <p className='mb-2 font-mono text-[11px] tracking-wide uppercase'>
                                Legibility checklist
                              </p>
                              <ul className='space-y-1.5'>
                                {checks.map(c => (
                                  <li key={c.label} className='flex items-start gap-2 text-sm'>
                                    <span
                                      className={
                                        c.ok
                                          ? 'text-emerald-600 dark:text-emerald-400'
                                          : 'text-rose-600 dark:text-rose-400'
                                      }
                                    >
                                      {c.ok ? '✓' : '✗'}
                                    </span>
                                    <span>
                                      {c.label}
                                      {!c.ok && c.fix && (
                                        <span className='text-muted-foreground'> — {c.fix}</span>
                                      )}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                              {failed.length > 0 && (
                                <div className='mt-3 flex flex-wrap gap-1.5'>
                                  {[...failed]
                                    .sort((a, b) =>
                                      checks.findIndex(c => c.label === a.label) -
                                      checks.findIndex(c => c.label === b.label))
                                    .map(c => (
                                      <Badge key={c.label} variant='outline' className='text-[11px]'>
                                        fix: {c.label.toLowerCase()}
                                      </Badge>
                                    ))}
                                </div>
                              )}
                            </div>
                            <div>
                              <p className='mb-2 font-mono text-[11px] tracking-wide uppercase'>
                                Agent evidence
                                {ev ? ` · picked ${ev.picks}×` : ''}
                              </p>
                              {ev && ev.quotes.length > 0 ? (
                                <div className='space-y-3'>
                                  {ev.quotes.map((q, i) => (
                                    <Quote key={i} q={q} />
                                  ))}
                                </div>
                              ) : (
                                <p className='text-muted-foreground text-sm'>
                                  No agent quotes for this product yet — run an audit,
                                  then this panel shows real model reasoning about it.
                                </p>
                              )}
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {evidence && evidence.declines.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Why agents walk away</CardTitle>
            <CardDescription>
              Verbatim reasoning from shopping missions where the agent bought nothing — the
              demand these listings are losing outright.
            </CardDescription>
          </CardHeader>
          <CardContent className='grid gap-4 md:grid-cols-2'>
            {evidence.declines.map((q, i) => (
              <Quote key={i} q={q} />
            ))}
          </CardContent>
        </Card>
      )}

      {!evidence && (
        <p className='text-muted-foreground text-center text-xs'>
          Agent evidence appears after your first audit run — it quotes real AI
          reasoning from the controlled shopping missions.
        </p>
      )}
    </div>
  )
}
