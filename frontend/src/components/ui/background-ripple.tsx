'use client'

// React Imports
import { useEffect, useMemo, useState } from 'react'

// Util Imports
import { cn } from '@/lib/utils'

const getInitialActiveSet = (totalCells: number, activeSquares: number) => {
  const safeActiveSquares = Math.max(1, Math.min(activeSquares, totalCells))
  const initialSet = new Set<number>()
  const step = Math.max(1, Math.floor(totalCells / safeActiveSquares))

  let cursor = 0

  while (initialSet.size < safeActiveSquares) {
    initialSet.add(cursor % totalCells)
    cursor += step + 1
  }

  return initialSet
}

const BackgroundRippleEffect = ({
  rows = 8,
  cols = 27,
  cellSize = 56.815,
  activeSquares = 18
}: {
  rows?: number
  cols?: number
  cellSize?: number
  activeSquares?: number
}) => {
  const [activeSet, setActiveSet] = useState<Set<number>>(() => {
    const totalCells = rows * cols

    // Keep server and client initial render deterministic to avoid hydration mismatch.
    return getInitialActiveSet(totalCells, activeSquares)
  })

  useEffect(() => {
    const totalCells = rows * cols
    const safeActiveSquares = Math.max(1, Math.min(activeSquares, totalCells))

    const pickRandomIndices = () => {
      const nextSet = new Set<number>()

      while (nextSet.size < safeActiveSquares) {
        nextSet.add(Math.floor(Math.random() * totalCells))
      }

      return nextSet
    }

    const intervalId = window.setInterval(() => {
      setActiveSet(pickRandomIndices())
    }, 2500)

    return () => window.clearInterval(intervalId)
  }, [rows, cols, activeSquares])

  return (
    <div
      className={cn(
        'absolute inset-0 h-full w-full object-center',
        '[--cell-border-color:color-mix(in_oklab,var(--accent),black_10%)] [--cell-fill-color:var(--accent)] [--cell-shadow-color:color-mix(in_oklab,var(--accent),black_43%)]',
        'dark:[--cell-border-color:color-mix(in_oklab,var(--accent),white_14%)] dark:[--cell-fill-color:color-mix(in_oklab,var(--accent),white_14%)] dark:[--cell-shadow-color:var(--accent)]'
      )}
    >
      <div className='relative flex h-auto w-auto justify-center overflow-hidden'>
        <div className='pointer-events-none absolute inset-0 z-2 h-full w-full overflow-hidden' />
        <DivGrid
          className='mask-radial-from-20% mask-radial-at-top opacity-600'
          rows={rows}
          cols={cols}
          cellSize={cellSize}
          borderColor='var(--cell-border-color)'
          fillColor='var(--cell-fill-color)'
          activeSet={activeSet}
        />
      </div>
    </div>
  )
}

type DivGridProps = {
  className?: string
  rows: number
  cols: number
  cellSize: number // in pixels
  borderColor: string
  fillColor: string
  activeSet: Set<number>
}

const DivGrid = ({
  className,
  rows = 7,
  cols = 30,
  cellSize = 56.815,
  borderColor = '#3f3f46',
  fillColor = 'rgba(14,165,233,0.3)',
  activeSet
}: DivGridProps) => {
  const cells = useMemo(() => Array.from({ length: rows * cols }, (_, idx) => idx), [rows, cols])

  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: `repeat(${cols}, ${cellSize}px)`,
    gridTemplateRows: `repeat(${rows}, ${cellSize}px)`,
    width: cols * cellSize,
    height: rows * cellSize,
    marginInline: 'auto'
  }

  return (
    <div className={cn('relative z-3', className)} style={gridStyle}>
      {cells.map(idx => {
        const isActive = activeSet.has(idx)

        return (
          <div
            key={idx}
            className={cn(
              'cell pointer-events-none relative border-[0.5px] opacity-40 transition-[transform,opacity,filter] duration-2500 ease-in-out will-change-transform dark:shadow-[0px_0px_40px_1px_var(--cell-shadow-color)_inset]'
            )}
            style={{
              backgroundColor: fillColor,
              borderColor: borderColor,
              opacity: isActive ? 0.8 : 0.4,
              filter: isActive ? 'brightness(1.08)' : 'brightness(1)',
              transform: isActive ? 'scale(1.07)' : 'scale(1)'
            }}
          />
        )
      })}
    </div>
  )
}

export { BackgroundRippleEffect }
