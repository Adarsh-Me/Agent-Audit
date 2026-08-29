// React Imports
import type { ReactNode } from 'react'

// Next Imports
import type { Metadata } from 'next'
import { Geist } from 'next/font/google'

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

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'

export const metadata: Metadata = {
  metadataBase: new URL(APP_URL),
  title: {
    default: 'AgentAudit — AI-Buy-Readiness Audit',
    template: '%s · AgentAudit'
  },
  description:
    'Can AI shopping agents actually see, choose, and buy from your catalog? AgentAudit runs 220 randomized, controlled shopping trials with real LLM agents and measures choice behavior with confidence intervals.',
  applicationName: 'AgentAudit',
  authors: [{ name: 'AgentAudit' }],
  keywords: [
    'ai readiness',
    'agentic commerce',
    'ai shopping agents',
    'buy readiness audit',
    'llm catalog audit',
    'agent-ready score'
  ],
  openGraph: {
    type: 'website',
    siteName: 'AgentAudit',
    title: 'AgentAudit — AI-Buy-Readiness Audit',
    description:
      'Can AI shopping agents actually buy from you? 220 controlled trials, real LLM agents, one AgentReady Score with confidence intervals.',
    url: APP_URL,
    images: [{ url: `${APP_URL}/images/og-image.png`, width: 1200, height: 630, alt: 'AgentAudit — AI-Buy-Readiness Audit' }]
  },
  twitter: {
    card: 'summary_large_image',
    title: 'AgentAudit — AI-Buy-Readiness Audit',
    description:
      '220 controlled shopping trials with real AI agents. One AgentReady Score — CI-bounded, honest, measured.',
    images: [`${APP_URL}/images/og-image.png`]
  },
  robots: { index: true, follow: true }
}

const RootLayout = ({ children }: Readonly<{ children: ReactNode }>) => {
  return (
    <html
      lang='en'
      className={cn(geistSans.variable, 'flex min-h-full w-full antialiased')}
      data-scroll-behavior='smooth'
      suppressHydrationWarning
    >
      <head>
        <link rel='preconnect' href='https://fonts.googleapis.com' />
        <link rel='preconnect' href='https://fonts.gstatic.com' crossOrigin='anonymous' />
        <link
          href='https://fonts.googleapis.com/css2?family=Geist+Pixel&family=Martian+Mono:wght@100..800&display=swap'
          rel='stylesheet'
        />
        <script
          type='application/ld+json'
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              '@context': 'https://schema.org',
              '@type': 'SoftwareApplication',
              name: 'AgentAudit',
              applicationCategory: 'BusinessApplication',
              operatingSystem: 'Web',
              description: 'AgentAudit runs 220 controlled AI shopping trials against an e-commerce catalog, then measures whether AI agents can see, choose, and buy products — emitting a single CI-bounded AgentReady Score with confidence intervals, revenue-at-risk, and human-gated remediation.',
              url: APP_URL,
              offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
              featureList: '220 controlled agent trials, six metrics with bootstrap confidence intervals, AgentReady Score, revenue-at-risk, human-gated remediation loop, remote MCP server',
              license: 'https://github.com/Adarsh-Me/Agent-Audit'
            })
          }}
        />
      </head>
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
