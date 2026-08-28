'use client'

// React Imports
import { type ComponentType } from 'react'

import { useEffect, useMemo, useState } from 'react'

// Next Imports
import Link from 'next/link'
import { usePathname } from 'next/navigation'

// Third-party Imports
import * as Icon from 'lucide-react'

// Type Imports
import type { NavItem } from '@/configs/navConfig'

// Component Imports
import { Sidebar, SidebarBody, SidebarLink } from '@/components/ui/sidebar-aceternity'

// Config Imports
import { navItems } from '@/configs/navConfig'
import themeConfig from '@/configs/themeConfig'

// Util Imports
import { cn } from '@/lib/utils'

import { getLastRun, getRerunOf } from '@/lib/runs'

type SidebarLinkData = { label: string; href: string; activePath?: string; icon: IconNameById }

// lucide-react dynamic icon name → component (same pattern the old sidebar used)
type IconNameById = keyof typeof Icon

// Flatten a group's items into the Aceternity link shape, keeping the active
// path (used to highlight the current route when the sidebar is collapsed).
function flattenItems(groups: NavItem[]): SidebarLinkData[] {
  const out: SidebarLinkData[] = []
  for (const group of groups) {
    for (const item of group.items) {
      // Only leaf items (with a href) become navigable links; parents with
      // childItems are skipped in the flat Aceternity layout.
      if ('childItems' in item) continue
      out.push({
        label: item.label,
        href: item.href,
        activePath: item.activePath,
        icon: item.icon
      })
    }
  }
  return out
}

function isLinkActive(href: string, activePath: string | undefined, pathname: string): boolean {
  if (activePath) return pathname.startsWith(activePath)
  return pathname === href
}

const SidebarLayout = () => {
  const pathname = usePathname()

  // Run-scoped nav links (Live Run / Results / Fixes / …) resolve from the last
  // audit id in localStorage — audit pages do not exist without a run, so they
  // stay hidden until one exists.
  const [runId, setRunId] = useState<string | null>(null)
  const [rerunId, setRerunId] = useState<string | null>(null)

  useEffect(() => {
    const sync = () => {
      setRunId(getLastRun())
      setRerunId(runId ? getRerunOf(runId) : null)
    }

    sync()
    // storage events fire in other tabs; same-tab writes are picked up on nav
    window.addEventListener('storage', sync)

    return () => window.removeEventListener('storage', sync)
  }, [runId])

  // Build the real nav from navItems plus, when a run exists, the run-scoped
  // pipeline links (Current Run + Verification).
  const navGroups = useMemo<NavItem[]>(() => {
    const groups: NavItem[] = [...navItems]

    if (runId) {
      groups.splice(1, 0, {
        groupLabel: 'Current Run',
        items: [
          { icon: 'LoaderIcon', label: 'Live Run', href: `/audit/${runId}`, activePath: `/audit/${runId}` },
          { icon: 'BarChart3Icon', label: 'Results', href: `/audit/${runId}/results`, activePath: `/audit/${runId}/results` },
          { icon: 'WrenchIcon', label: 'Fixes', href: `/audit/${runId}/fixes`, activePath: `/audit/${runId}/fixes` },
          { icon: 'IndianRupeeIcon', label: 'Revenue at Risk', href: `/audit/${runId}/revenue`, activePath: `/audit/${runId}/revenue` }
        ]
      })

      if (rerunId) {
        groups.splice(2, 0, {
          groupLabel: 'Verification',
          items: [
            { icon: 'GitCompareArrowsIcon', label: 'Delta', href: `/delta/${rerunId}`, activePath: `/delta/${rerunId}` }
          ]
        })
      }
    }

    return groups
  }, [runId, rerunId])

  const links = useMemo(() => flattenItems(navGroups), [navGroups])

  return (
    <Sidebar>
      <SidebarBody className='justify-between gap-10'>
        <div className='flex flex-col flex-1 overflow-y-auto overflow-x-hidden'>
          {/* logo / brand */}
          <BrandMark />
          <div className='mt-8 flex flex-col gap-2'>
            {links.map(link => {
              const Tag = link.icon ? (Icon[link.icon] as ComponentType) : null
              const active = isLinkActive(link.href, link.activePath, pathname)
              return (
                <SidebarLink
                  key={link.href}
                  link={{ label: link.label, href: link.href, icon: Tag ? <Tag /> : null }}
                  className={cn(active && 'bg-primary/10 text-primary rounded-md')}
                />
              )
            })}
          </div>
        </div>
        <div>
          <SidebarLink
            link={{
              label: themeConfig.templateName,
              href: themeConfig.homePageUrl,
              icon: <Icon.ScanSearchIcon className='h-6 w-6 flex-shrink-0' />
            }}
          />
        </div>
      </SidebarBody>
    </Sidebar>
  )
}

const BrandMark = () => {
  return (
    <Link
      href={themeConfig.homePageUrl}
      className='font-normal flex space-x-2 items-center text-sm text-black py-1 relative z-20 dark:text-white'
    >
      <div className='bg-primary/15 text-primary flex size-8 shrink-0 items-center justify-center rounded-lg border border-primary/25'>
        <Icon.ScanSearchIcon className='size-4' />
      </div>
      <span className='font-pixel text-base leading-none text-nowrap'>{themeConfig.templateName}</span>
    </Link>
  )
}

export default SidebarLayout
