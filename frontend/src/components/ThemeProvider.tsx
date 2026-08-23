'use client'

// React Imports
import type { ComponentProps } from 'react'

// Third-party Imports
import { ThemeProvider as NextThemesProvider } from 'next-themes'

export const ThemeProvider = ({ children, ...props }: ComponentProps<typeof NextThemesProvider>) => {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>
}
