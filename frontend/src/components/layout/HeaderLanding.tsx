'use client'

// React Imports
import Link from 'next/link'
import { usePathname } from 'next/navigation'

// Component Imports
import ModeToggle from '@/components/layout/ModeToggle'
import Logo from '@/components/shared/Logo'
import { Button } from '@/components/ui/button'

import { cn } from '@/lib/utils'

/** Horizontal top-nav header for the landing/marketing page.
 *  In the same spirit as the reference dashboard header: wordmark left,
 *  horizontal nav center, actions (theme + CTA) right, on a sticky bar. */
const HeaderLanding = () => {
  const pathname = usePathname()

  const links = [
    { label: 'Home', href: '/' },
    { label: 'Catalog', href: '/catalog' }
  ]

  return (
    <header className='bg-card/80 sticky top-0 z-50 border-b backdrop-blur'>
      <div className='mx-auto flex h-16 max-w-6xl items-center justify-between gap-6 px-4 sm:px-6'>
        {/* wordmark */}
        <Link href='/' className='flex items-center gap-2'>
          <Logo className='[&_span]:text-lg' />
        </Link>

        {/* horizontal nav */}
        <nav className='hidden items-center gap-1 md:flex'>
          {links.map(link => {
            const active = pathname === link.href
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                  active
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                {link.label}
              </Link>
            )
          })}
        </nav>

        {/* actions */}
        <div className='flex items-center gap-2'>
          <Link
            href='https://github.com/Adarsh-Me/Agent-Audit'
            target='_blank'
            rel='noreferrer'
            className='text-muted-foreground hover:text-foreground hidden text-sm transition-colors sm:block'
          >
            GitHub
          </Link>
          <ModeToggle />
          <Button size='sm' render={<Link href='/' />}>
            Run a demo audit
          </Button>
        </div>
      </div>
    </header>
  )
}

export default HeaderLanding
