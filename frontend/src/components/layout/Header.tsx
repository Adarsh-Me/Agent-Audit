'use client'

// Next Imports
import { Fragment } from 'react'

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
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'

const Header = () => {
  const pathname = usePathname()

  const segments = pathname.split('/').filter(Boolean)

  return (
    <header className='bg-card sticky top-0 z-50 border-b'>
      <div className='mx-auto flex max-w-360 items-center justify-between gap-6 px-4 py-2 sm:px-6'>
        <div className='flex items-center gap-4'>
          <SidebarTrigger className='[&_svg]:size-5!' />
          <Separator orientation='vertical' className='hidden h-4! data-vertical:self-center sm:block' />
          <Breadcrumb className='hidden sm:block'>
            <BreadcrumbList>
              {segments.map((segment, index) => {
                const isLast = index === segments.length - 1
                const label = segment.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                const href = '/' + segments.slice(0, index + 1).join('/')

                return (
                  <Fragment key={href}>
                    <BreadcrumbItem>
                      {isLast ? <BreadcrumbPage>{label}</BreadcrumbPage> : <BreadcrumbPage>{label}</BreadcrumbPage>}
                    </BreadcrumbItem>
                    {!isLast && <BreadcrumbSeparator />}
                  </Fragment>
                )
              })}
            </BreadcrumbList>
          </Breadcrumb>
        </div>
        <div className='flex items-center gap-1.5'>
          <ModeToggle />
        </div>
      </div>
    </header>
  )
}

export default Header
