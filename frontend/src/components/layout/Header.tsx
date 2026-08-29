'use client'

// React Imports
import { Fragment } from 'react'

// Next Imports
import Image from 'next/image'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

// Component Imports
import ModeToggle from '@/components/layout/ModeToggle'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'

const Header = () => {
  const pathname = usePathname()

  const segments = pathname.split('/').filter(Boolean)

  return (
    <header className='bg-card/80 sticky top-0 z-50 border-b backdrop-blur'>
      <div className='mx-auto flex h-14 max-w-360 items-center justify-between gap-6 px-4 sm:px-6'>
        <div className='flex min-w-0 items-center gap-3'>
          <SidebarTrigger className='[&_svg]:size-5!' />
          <Separator orientation='vertical' className='hidden h-4! self-center sm:block' />
          {/* Brand-rooted breadcrumb — the bar reads intentionally even on /
              where there are no path segments to show. */}
          <Breadcrumb className='hidden min-w-0 sm:block'>
            <BreadcrumbList>
              <BreadcrumbItem>
                <span className='flex items-center gap-2'>
                  <Image
                    src='/favicon-512.png'
                    alt=''
                    width={18}
                    height={18}
                    className='size-4.5 shrink-0'
                  />
                  <span className='font-pixel text-sm'>AgentAudit</span>
                </span>
              </BreadcrumbItem>
              {segments.map((segment, index) => {
                const isLast = index === segments.length - 1
                const label = segment.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                const href = '/' + segments.slice(0, index + 1).join('/')

                return (
                  <Fragment key={href}>
                    <BreadcrumbSeparator />
                    <BreadcrumbItem>
                      <BreadcrumbPage>{label}</BreadcrumbPage>
                    </BreadcrumbItem>
                  </Fragment>
                )
              })}
            </BreadcrumbList>
          </Breadcrumb>
          {/* Mobile: breadcrumb is hidden — keep a compact wordmark so the bar
              still carries identity. */}
          <span className='font-pixel text-sm sm:hidden'>AgentAudit</span>
        </div>
        <div className='flex shrink-0 items-center gap-2'>
          <Button size='sm' render={<Link href='/' />}>
            New audit
          </Button>
          <ModeToggle />
        </div>
      </div>
    </header>
  )
}

export default Header
