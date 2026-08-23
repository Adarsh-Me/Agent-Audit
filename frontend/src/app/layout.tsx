// React Imports
import type { ReactNode } from 'react'

// Next Imports
import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'

// Third-party Imports
import { NuqsAdapter } from 'nuqs/adapters/next/app'

// Component Imports
import Providers from '@/components/Providers'
import { TooltipProvider } from '@/components/ui/tooltip'

// Util Imports
import { cn } from '@/lib/utils'

// Style Imports
import './globals.css'
import ScrollToTop from '@/components/layout/ScrollToTop'

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin']
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin']
})

export const metadata: Metadata = {
  title: {
    default: 'AgentAudit — AI-Buy-Readiness Audit',
    template: '%s · AgentAudit'
  },
  description:
    'Can AI shopping agents actually see, choose, and buy from your catalog? AgentAudit runs 640 randomized, controlled shopping trials with real LLM agents and measures choice behavior with confidence intervals.',
  metadataBase: new URL(`${process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'}`)
}

const RootLayout = ({ children }: Readonly<{ children: ReactNode }>) => {
  return (
    <html
      lang='en'
      className={cn(geistSans.variable, geistMono.variable, 'flex min-h-full w-full antialiased')}
      data-scroll-behavior='smooth'
      suppressHydrationWarning
    >
      <body className='flex min-h-full w-full flex-auto flex-col'>
        <NuqsAdapter>
          <Providers sidebarDefaultOpen={true}>
            <TooltipProvider>{children}</TooltipProvider>
          </Providers>
        </NuqsAdapter>

        <ScrollToTop />
      </body>
    </html>
  )
}

export default RootLayout
