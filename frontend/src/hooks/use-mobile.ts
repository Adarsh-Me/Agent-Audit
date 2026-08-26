import * as React from 'react'

const MOBILE_BREAKPOINT = 1280

export function useIsMobile() {
  // Hydration-safe: the first render must match the server (desktop layout).
  // The real viewport is only read after mount — never during render.
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)

    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    }

    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    mql.addEventListener('change', onChange)

    return () => mql.removeEventListener('change', onChange)
  }, [])

  return !!isMobile
}
