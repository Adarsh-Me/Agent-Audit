import type { ImgHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

/**
 * Decorative Open Peeps SVG illustration served from /public/illustrations.
 * Defaults to empty alt (decorative) + lazy loading for below-the-fold use.
 */
export function Peep({ src, alt = '', loading = 'lazy', className, ...props }: ImgHTMLAttributes<HTMLImageElement> & { src: string }) {
  return (
    <img
      src={src}
      alt={alt}
      loading={loading}
      className={cn('h-auto w-full object-contain select-none opacity-90', className)}
      {...props}
    />
  )
}

export default Peep
