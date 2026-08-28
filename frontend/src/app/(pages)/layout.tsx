'use client'

// React Imports
import { Suspense } from 'react'
import type { ReactNode } from 'react'

// Next Imports
import { usePathname } from 'next/navigation'

// Component Imports
import Footer from '@/components/layout/Footer'
import Header from '@/components/layout/Header'
import Sidebar from '@/components/layout/Sidebar'
import { SidebarInset } from '@/components/ui/sidebar'
import { Toaster } from '@/components/ui/sonner'

const PagesLayout = ({ children }: Readonly<{ children: ReactNode }>) => {
  const pathname = usePathname()

  // The landing page (/) is a marketing homepage with its own top-nav header
  // (HeaderLanding); hide the app's left sidebar + breadcrumb bar there so the
  // top-nav-only layout matches the reference.
  const isLanding = pathname === '/'

  return (
    <div className='flex h-full w-full min-w-0'>
      {!isLanding ? (
        <Suspense>
          <Sidebar />
        </Suspense>
      ) : null}
      <SidebarInset className='flex flex-1 flex-col'>
        <Header />
        <main className='mx-auto size-full max-w-360 flex-1 px-4 py-8 sm:px-8'>{children}</main>
        <Toaster />
        <Footer />
      </SidebarInset>
    </div>
  )
}

export default PagesLayout
