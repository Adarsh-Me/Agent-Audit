'use client'

import { useEffect, useMemo, useState } from 'react'

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
import { ErrorBox, PanelSkeleton, StatCard, TierChip } from '@/components/agentaudit/bits'
import { ApiError, getCatalog, type CatalogResponse } from '@/lib/api'
import { inr } from '@/lib/format'

export default function CatalogPage() {
  const [data, setData] = useState<CatalogResponse | null>(null)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const [query, setQuery] = useState('')
  const [tier, setTier] = useState<string>('all')

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

  if (error) return <ErrorBox code={error.code} message={error.message} />
  if (!data) return <PanelSkeleton lines={6} />

  const tiers = Array.from(new Set(data.products.map(p => p.tier)))
  const withStructured = data.products.filter(p => p.structured_data && Object.keys(p.structured_data).length > 0).length

  return (
    <div className='flex flex-col gap-6'>
      <div>
        <h1 className='text-xl font-semibold tracking-tight'>Catalog</h1>
        <p className='text-muted-foreground mt-1 text-sm'>
          What the agents actually see — {data.count} listings in the audited catalog
          {data.source === 'demo' ? ' (demo store)' : ''}.
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
            <CardTitle className='text-base'>Products</CardTitle>
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
                <TableHead>SKU</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Structured data</TableHead>
                <TableHead className='hidden md:table-cell'>Description</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map(p => (
                <TableRow key={p.id}>
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
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
