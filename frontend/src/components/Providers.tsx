// React Imports
import type { ReactNode } from 'react'

// Component Imports
import { ThemeProvider } from './ThemeProvider'
import { SidebarProvider } from './ui/sidebar'
import { TooltipProvider } from './ui/tooltip'

type Props = {
  children: ReactNode
  sidebarDefaultOpen?: boolean
}

const Providers = ({ children, sidebarDefaultOpen }: Props) => {
  return (
    <ThemeProvider attribute='class' defaultTheme='dark' enableSystem={false}>
      <TooltipProvider>
        <SidebarProvider defaultOpen={sidebarDefaultOpen}>{children}</SidebarProvider>
      </TooltipProvider>
    </ThemeProvider>
  )
}

export default Providers
